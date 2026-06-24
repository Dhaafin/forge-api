import httpx
from sqlalchemy.orm import Session
from uuid import UUID
from fastapi import HTTPException, status
from app.core.config import settings
from app.models.workout_session import WorkoutSession
from app.models.workout_set import WorkoutSet
from app.models.ai_coach_log import AICoachLog
from app.models.user import User
from app.models.exercise_guide import ExerciseGuide

async def generate_coach_analysis(session_id: UUID, db: Session, user: User) -> AICoachLog:
    # 1. Cache Check
    cached_log = db.query(AICoachLog).filter(AICoachLog.session_id == session_id).first()
    if cached_log:
        return cached_log

    # 2. Retrieve Workout Session
    session = db.query(WorkoutSession).filter(
        WorkoutSession.id == session_id,
        WorkoutSession.user_id == user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout session not found or unauthorized."
        )

    # 3. Check API Key
    if not settings.OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Coach service configuration error: OpenRouter API key is missing."
        )

    # 4. Compile Session Stats & Format Data
    total_volume = 0.0
    exercise_groups = {}
    pr_list = []

    for workout_set in session.sets:
        vol = workout_set.weight_kg * workout_set.reps
        total_volume += vol
        
        ex_id = str(workout_set.exercise_id)
        if ex_id not in exercise_groups:
            exercise_groups[ex_id] = {
                "name": workout_set.exercise.name if workout_set.exercise else "Unknown Exercise",
                "target_muscle": workout_set.exercise.target_muscle if workout_set.exercise else "Unknown",
                "sets": []
            }
        
        set_info = {
            "set_number": workout_set.set_number,
            "weight_kg": workout_set.weight_kg,
            "reps": workout_set.reps,
            "set_type": workout_set.set_type,
            "is_pr": workout_set.is_pr
        }
        exercise_groups[ex_id]["sets"].append(set_info)
        
        if workout_set.is_pr:
            pr_list.append(f"{exercise_groups[ex_id]['name']} ({workout_set.weight_kg}kg for {workout_set.reps} reps)")

    # Format exercise list details for prompt
    exercises_formatted = []
    for ex_data in exercise_groups.values():
        ex_str = f"- {ex_data['name']} (Target: {ex_data['target_muscle']}):\n"
        for s in ex_data["sets"]:
            pr_suffix = " [NEW PERSONAL RECORD!]" if s["is_pr"] else ""
            ex_str += f"  * Set {s['set_number']}: {s['weight_kg']}kg x {s['reps']} reps ({s['set_type']}){pr_suffix}\n"
        exercises_formatted.append(ex_str)
        
    exercises_block = "\n".join(exercises_formatted)

    # 5. Build Prompt
    system_prompt = (
        "You are an expert, NASM-certified AI Gym Coach for the Forge Gym Tracker Platform.\n"
        "Your task is to provide a concise, encouraging, and scientifically sound analysis of the user's workout session.\n"
        "Write your entire response strictly in English. Use a supportive, athletic, and friendly tone.\n\n"
        "Please address the following points in at most 3 short paragraphs:\n"
        "1. Summarize the session (workout name, duration, and calculated total volume).\n"
        "2. Congratulate the user for any Personal Records (PRs) achieved (highlighting the exercise name, weight, and reps).\n"
        "3. Offer one concrete, actionable suggestion for progressive overload in their next session (e.g., adding weight/reps or focusing on form)."
    )

    user_prompt = (
        f"Workout Session Name: {session.title or 'Gym Session'}\n"
        f"Duration: {session.duration_minutes or 0} minutes\n"
        f"Total Volume Lifted: {total_volume} kg\n"
        f"Personal Records Broken: {', '.join(pr_list) if pr_list else 'None'}\n\n"
        f"Exercise Log Details:\n{exercises_block}"
    )

    # 6. Call OpenRouter API
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://forge.gym",  # Optional
        "X-Title": "Forge Gym API"           # Optional
    }
    
    payload = {
        "model": settings.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"OpenRouter API error: {response.text}"
                )
                
            data = response.json()
            ai_message = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            tokens_prompt = usage.get("prompt_tokens")
            tokens_completion = usage.get("completion_tokens")
            
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Network error communicating with AI service provider: {str(exc)}"
        )

    # 7. Save to Database & Return
    new_log = AICoachLog(
        user_id=user.id,
        session_id=session_id,
        prompt=user_prompt,
        response=ai_message,
        model_used=settings.OPENROUTER_MODEL,
        tokens_prompt=tokens_prompt,
        tokens_completion=tokens_completion
    )
    
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    
    return new_log


async def parse_workout_notes_with_ai(raw_text: str) -> dict:
    import json
    
    if not settings.OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI service configuration error: OpenRouter API key is missing."
        )

    system_prompt = (
        "You are an expert workout notes parser for the Forge Gym Platform.\n"
        "Your task is to parse a raw text workout note and extract the workout details into a clean, structured JSON format.\n"
        "Ignore supersets or treat them as separate exercises (do not try to nest them under each other).\n\n"
        "You MUST return ONLY a valid JSON object matching this schema:\n"
        "{\n"
        "  \"title\": \"Name of the workout session/day (e.g., Pull Day, Push Day)\",\n"
        "  \"date\": \"The date of the session formatted as YYYY-MM-DD if found, otherwise null\",\n"
        "  \"exercises\": [\n"
        "    {\n"
        "      \"raw_name\": \"Original exercise name (e.g. Lat Pulldowns)\",\n"
        "      \"inferred_target_muscle\": \"The main muscle targeted (e.g. Lats, Chest, Quads, Biceps, Triceps, Shoulders, Back, Hamstrings, Calves, Abs)\",\n"
        "      \"sets\": [\n"
        "        {\n"
        "          \"set_number\": 1,\n"
        "          \"weight_kg\": 30.0,\n"
        "          \"reps\": 12,\n"
        "          \"set_type\": \"normal\"\n"
        "        }\n"
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- For weight like '2/3kg', choose the higher value (e.g., 3.0).\n"
        "- For weight like '30kg', use 30.0. Weight must be a float.\n"
        "- If no weight is provided, default to 0.0.\n"
        "- Reps must be an integer.\n"
        "- If a line has multiple exercises (e.g. superset), split them into separate exercise objects.\n"
        "- Return ONLY the JSON object, no Markdown backticks, no other text."
    )

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://forge.gym",
        "X-Title": "Forge Gym API"
    }
    
    payload = {
        "model": settings.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Parse the following workout notes:\n\n{raw_text}"}
        ],
        "response_format": {"type": "json_object"}
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"OpenRouter API error: {response.text}"
                )
                
            data = response.json()
            ai_message = data["choices"][0]["message"]["content"]
            
            parsed_data = json.loads(ai_message)
            return parsed_data
            
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_542_GATEWAY_TIMEOUT if hasattr(status, "HTTP_542_GATEWAY_TIMEOUT") else status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Network error communicating with AI service provider: {str(exc)}"
        )
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to parse AI response as JSON: {str(exc)}"
        )


async def get_embedding(text: str) -> list[float]:
    if not settings.OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI service configuration error: OpenRouter API key is missing."
        )

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://forge.gym",
        "X-Title": "Forge Gym API"
    }

    payload = {
        "model": "openai/text-embedding-3-small",
        "input": text
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers=headers,
                json=payload
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"OpenRouter Embeddings API error: {response.text}"
                )
            data = response.json()
            return data["data"][0]["embedding"]
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Network error communicating with AI embeddings provider: {str(exc)}"
        )


def retrieve_relevant_guides(db: Session, query_embedding: list[float], limit: int = 3) -> list[ExerciseGuide]:
    from sqlalchemy import select
    stmt = (
        select(ExerciseGuide)
        .order_by(ExerciseGuide.embedding.cosine_distance(query_embedding))
        .limit(limit)
    )
    result = db.execute(stmt)
    return result.scalars().all()


async def generate_rag_stream_response(query: str, db: Session, user: User):
    # 1. Generate query embedding
    query_embedding = await get_embedding(query)

    # 2. Retrieve top matching guides
    guides = retrieve_relevant_guides(db, query_embedding, limit=3)

    # 3. Construct Context and Prompt
    context_blocks = []
    for g in guides:
        context_blocks.append(f"Exercise: {g.exercise_name}\nTarget Muscle: {g.target_muscle}\nDescription: {g.description}")
    context_str = "\n\n---\n\n".join(context_blocks)

    system_prompt = (
        "You are an expert personal AI Gym Coach for the Forge Gym Tracker Platform.\n"
        "Answer the user's questions about exercises, fitness, or workouts using ONLY the provided exercise guides context.\n"
        "If the answer cannot be found or inferred from the context, state politely that you do not know the answer and focus only on what is verified.\n"
        "Keep your response concise, athletic, friendly, and encouraging. Write strictly in English.\n\n"
        f"Exercise Guides Context:\n{context_str}"
    )

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://forge.gym",
        "X-Title": "Forge Gym API"
    }

    payload = {
        "model": settings.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ],
        "stream": True
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream(
                "POST",
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    yield f"Error calling AI service: {error_body.decode()}"
                    return

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            import json
                            chunk = json.loads(data_str)
                            text = chunk["choices"][0]["delta"].get("content", "")
                            if text:
                                yield text
                        except Exception:
                            pass
    except httpx.RequestError as exc:
        yield f"Network error communicating with AI provider: {str(exc)}"

