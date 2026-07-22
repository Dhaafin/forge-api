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
from app.models.chat_session import AIChatSession
from app.models.chat_message import AIChatMessage

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
    if not settings.AI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Coach service configuration error: AI API key is missing."
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

    # 6. Call AI API
    headers = {
        "Authorization": f"Bearer {settings.AI_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://forge.gym",  # Optional
        "X-Title": "Forge Gym API"           # Optional
    }
    
    payload = {
        "model": settings.AI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": 1000
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.AI_BASE_URL}/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"AI provider API error: {response.text}"
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
        model_used=settings.AI_MODEL,
        tokens_prompt=tokens_prompt,
        tokens_completion=tokens_completion
    )
    
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    
    return new_log


async def parse_workout_notes_with_ai(raw_text: str) -> dict:
    import json
    
    if not settings.AI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI service configuration error: AI API key is missing."
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
        "      \"inferred_target_muscle\": \"The main muscle targeted (Must be one of: Chest, Back, Legs, Shoulders, Arms, Core, Cardio, Full Body)\",\n"
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
        "Authorization": f"Bearer {settings.AI_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://forge.gym",
        "X-Title": "Forge Gym API"
    }
    
    payload = {
        "model": settings.AI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Parse the following workout notes:\n\n{raw_text}"}
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 1000
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.AI_BASE_URL}/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"AI provider API error: {response.text}"
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
    if not settings.AI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI service configuration error: AI API key is missing."
        )

    headers = {
        "Authorization": f"Bearer {settings.AI_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://forge.gym",
        "X-Title": "Forge Gym API"
    }

    payload = {
        "model": settings.AI_EMBEDDING_MODEL,
        "input": text
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.AI_BASE_URL}/embeddings",
                headers=headers,
                json=payload
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"AI Embeddings provider API error: {response.text}"
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


async def generate_chat_session_title(first_message: str) -> str:
    if not settings.AI_API_KEY:
        return "Gym Session"

    headers = {
        "Authorization": f"Bearer {settings.AI_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://forge.gym",
        "X-Title": "Forge Gym API"
    }

    system_prompt = (
        "You are a helpful assistant. Generate a short, concise, and professional title "
        "(max 4 words, strictly in English) for a chat session based on the user's first message. "
        "Do not include any quotes, punctuation, or extra text. Just return the title."
    )

    payload = {
        "model": settings.AI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": first_message}
        ],
        "max_tokens": 50
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{settings.AI_BASE_URL}/chat/completions",
                headers=headers,
                json=payload
            )
            if response.status_code == 200:
                data = response.json()
                title = data["choices"][0]["message"]["content"].strip().replace('"', '')
                return title
    except Exception:
        pass
    return "Gym Session"


async def summarize_older_chat_history(messages_to_summarize: list) -> str:
    if not settings.AI_API_KEY or not messages_to_summarize:
        return ""

    headers = {
        "Authorization": f"Bearer {settings.AI_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://forge.gym",
        "X-Title": "Forge Gym API"
    }

    conversation_text = ""
    for m in messages_to_summarize:
        role = "User" if m.sender == "user" else "Coach"
        conversation_text += f"{role}: {m.content}\n"

    system_prompt = (
        "You are an expert fitness assistant. Summarize the following conversation history "
        "briefly in 1-2 paragraphs (strictly in English). Focus on what the user wants, "
        "their fitness goals, or any exercises mentioned. Keep it concise."
    )

    payload = {
        "model": settings.AI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": conversation_text}
        ],
        "max_tokens": 400
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{settings.AI_BASE_URL}/chat/completions",
                headers=headers,
                json=payload
            )
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return ""


def compile_user_profile_context(db: Session, user: User) -> str:
    recent_workouts = (
        db.query(WorkoutSession)
        .filter(WorkoutSession.user_id == user.id)
        .order_by(WorkoutSession.start_time.desc())
        .limit(3)
        .all()
    )
    
    workout_summary = []
    for ws in recent_workouts:
        exercises = set(s.exercise.name for s in ws.sets if s.exercise)
        exercises_str = ", ".join(exercises) if exercises else "No exercises logged"
        date_str = ws.start_time.strftime("%Y-%m-%d")
        workout_summary.append(f"- {ws.title or 'Workout'} on {date_str} ({ws.duration_minutes or 0} min): {exercises_str}")
        
    workout_history_str = "\n".join(workout_summary) if workout_summary else "No workouts logged yet."
    
    # Format optional profile parameters for AI coach personalization
    weight_str = f"{user.weight_kg} kg" if user.weight_kg else "Not set"
    height_str = f"{user.height_cm} cm" if user.height_cm else "Not set"
    
    profile_context = (
        f"User Profile:\n"
        f"- Name: {user.name}\n"
        f"- Preferred Unit: {user.preferred_unit}\n"
        f"- Weight: {weight_str}\n"
        f"- Height: {height_str}\n"
        f"- Goal: {user.fitness_goal or 'Not set'}\n"
        f"- Experience Level: {user.experience_level or 'Not set'}\n"
        f"- Injuries/Limitations: {user.injuries_or_limitations or 'None'}\n"
        f"- Registered on: {user.created_at.strftime('%Y-%m-%d')}\n"
        f"- Recent Workout History:\n{workout_history_str}\n"
    )
    return profile_context


async def generate_rag_stream_response(query: str, db: Session, user: User, session_id: UUID):
    # 1. Fetch Chat Session and verify ownership
    chat_session = db.query(AIChatSession).filter(
        AIChatSession.id == session_id,
        AIChatSession.user_id == user.id
    ).first()
    
    if not chat_session:
        yield "Error: Chat session not found or unauthorized."
        return

    # 2. Save User Message to Database
    user_msg = AIChatMessage(
        session_id=session_id,
        sender="user",
        content=query
    )
    db.add(user_msg)
    db.commit()

    # 3. If this is the first message in the session, generate a title using LLM
    first_msg_check = db.query(AIChatMessage).filter(AIChatMessage.session_id == session_id).count()
    if first_msg_check == 1:
        new_title = await generate_chat_session_title(query)
        chat_session.title = new_title
        db.commit()

    # 4. Generate query embedding
    query_embedding = await get_embedding(query)

    # 5. Retrieve top matching guides
    guides = retrieve_relevant_guides(db, query_embedding, limit=3)

    # 6. Construct Context blocks
    context_blocks = []
    for g in guides:
        context_blocks.append(f"Exercise: {g.exercise_name}\nTarget Muscle: {g.target_muscle}\nDescription: {g.description}")
    context_str = "\n\n---\n\n".join(context_blocks)

    # 7. Compile dynamic user profile context
    user_profile_context = compile_user_profile_context(db, user)

    # 8. Load past chat messages
    past_messages = (
        db.query(AIChatMessage)
        .filter(AIChatMessage.session_id == session_id)
        .order_by(AIChatMessage.created_at.asc())
        .all()
    )

    # Separate messages into older (to summarize) and newer (to pass as chat history)
    recent_messages = past_messages[-6:]
    older_messages = past_messages[:-6]

    older_summary_str = ""
    if older_messages:
        older_summary_str = await summarize_older_chat_history(older_messages)

    # 9. Build Prompt
    system_prompt = (
        "You are an expert personal AI Gym Coach for the Forge Gym Tracker Platform.\n"
        "Answer the user's questions about exercises, fitness, or workouts using ONLY the provided exercise guides context.\n"
        "If the answer cannot be found or inferred from the context, state politely that you do not know the answer and focus only on what is verified.\n"
        "Keep your response concise, athletic, friendly, and encouraging. Write strictly in English.\n\n"
        f"Exercise Guides Context:\n{context_str}\n\n"
        f"{user_profile_context}\n"
    )
    if older_summary_str:
        system_prompt += f"\nSummary of older conversation:\n{older_summary_str}\n"

    api_messages = [{"role": "system", "content": system_prompt}]
    
    for m in recent_messages[:-1]:
        role = "user" if m.sender == "user" else "assistant"
        api_messages.append({"role": role, "content": m.content})
        
    api_messages.append({"role": "user", "content": query})

    headers = {
        "Authorization": f"Bearer {settings.AI_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://forge.gym",
        "X-Title": "Forge Gym API"
    }

    payload = {
        "model": settings.AI_MODEL,
        "messages": api_messages,
        "stream": True,
        "max_tokens": 1000
    }

    full_ai_response = []

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream(
                "POST",
                f"{settings.AI_BASE_URL}/chat/completions",
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
                                full_ai_response.append(text)
                                yield text
                        except Exception:
                            pass
                            
        # 10. Save AI Response to Database
        ai_response_text = "".join(full_ai_response)
        if ai_response_text:
            ai_msg = AIChatMessage(
                session_id=session_id,
                sender="ai",
                content=ai_response_text
            )
            db.add(ai_msg)
            db.commit()

    except httpx.RequestError as exc:
        yield f"Network error communicating with AI provider: {str(exc)}"


