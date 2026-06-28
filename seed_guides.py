import sys
import httpx
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.exercise_guide import ExerciseGuide
from app.core.config import settings

def get_embedding_sync(text: str) -> list[float]:
    if not settings.AI_API_KEY:
        raise Exception("AI_API_KEY is not configured in environment.")

    headers = {
        "Authorization": f"Bearer {settings.AI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.AI_EMBEDDING_MODEL,
        "input": text
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{settings.AI_BASE_URL}/embeddings",
            headers=headers,
            json=payload
        )
        if response.status_code != 200:
            raise Exception(f"Failed to generate embedding: {response.text}")
        return response.json()["data"][0]["embedding"]

def seed_exercise_guides():
    print("Starting exercise guides seeding process...")
    db: Session = SessionLocal()

    guides_data = [
        {
            "exercise_name": "Barbell Bench Press",
            "target_muscle": "Chest",
            "description": (
                "The Barbell Bench Press is a classic compound exercise targeting the chest (pectoralis major), "
                "shoulders (anterior deltoids), and triceps. To perform: lie flat on a bench, grip the barbell "
                "slightly wider than shoulder width, lower the bar slowly to your mid-chest while keeping your "
                "elbows at a 45-degree angle, and push the bar back up until your arms are fully extended."
            )
        },
        {
            "exercise_name": "Incline Dumbbell Press",
            "target_muscle": "Chest",
            "description": (
                "The Incline Dumbbell Press targets the upper portion of the chest (clavicular head of pectoralis major), "
                "anterior deltoids, and triceps. To perform: set the bench to a 30-45 degree incline, hold dumbbells "
                "at chest level, press the weights upward until arms are locked, then lower them under control until "
                "you feel a stretch in your chest muscles."
            )
        },
        {
            "exercise_name": "Barbell Deadlift",
            "target_muscle": "Back",
            "description": (
                "The Barbell Deadlift is a premier compound movement that strengthens the entire posterior chain, "
                "specifically the lower and upper back, glutes, hamstrings, and core. To perform: stand with feet hip-width "
                "apart under a barbell, bend at the hips and knees, grab the bar with a flat back, engage your core, "
                "and lift by driving your hips forward and standing tall. Keep the bar close to your body throughout."
            )
        },
        {
            "exercise_name": "Lat Pulldown",
            "target_muscle": "Back",
            "description": (
                "The Lat Pulldown targets the latissimus dorsi (lats) to build upper back width. To perform: sit at the "
                "pulldown station, grip the bar wider than shoulder width, lean back slightly, pull the bar down toward "
                "your upper chest by driving your elbows down and back, and squeeze your shoulder blades together. "
                "Return the bar slowly to the starting position."
            )
        },
        {
            "exercise_name": "Barbell Squat",
            "target_muscle": "Legs",
            "description": (
                "The Barbell Squat is the king of leg exercises, targeting the quadriceps, glutes, hamstrings, and core. "
                "To perform: rest the barbell on your upper back, stand with feet shoulder-width apart, lower your hips "
                "back and down as if sitting in a chair, keep your chest up and back flat, go down until thighs are "
                "parallel to the ground, then drive back up to a standing position."
            )
        },
        {
            "exercise_name": "Dumbbell Bicep Curl",
            "target_muscle": "Arms",
            "description": (
                "The Dumbbell Bicep Curl is an isolation movement focusing on the biceps brachii. To perform: stand tall "
                "holding dumbbells at your sides, keep your elbows locked close to your chest, curl the weights up "
                "while rotating your palms upward, squeeze the biceps at the peak, and slowly lower the weights."
            )
        },
        {
            "exercise_name": "Overhead Barbell Press",
            "target_muscle": "Shoulders",
            "description": (
                "The Overhead Barbell Press (Military Press) is a compound exercise that targets the shoulders (deltoids), "
                "triceps, and core. To perform: stand with feet shoulder-width apart, rest the barbell on your collarbones, "
                "press the bar straight up overhead, lock your arms, and pull your head slightly forward as the bar passes "
                "your face. Lower the bar back to your chest under control."
            )
        },
        {
            "exercise_name": "Dumbbell Lateral Raise",
            "target_muscle": "Shoulders",
            "description": (
                "The Dumbbell Lateral Raise is an isolation exercise targeting the lateral deltoids to build shoulder width. "
                "To perform: stand with dumbbells at your sides, slightly bend your elbows, raise the weights out to your "
                "sides until arms are parallel to the floor, pause briefly, then slowly lower the weights back down."
            )
        }
    ]

    try:
        count_added = 0
        for item in guides_data:
            existing = db.query(ExerciseGuide).filter(ExerciseGuide.exercise_name == item["exercise_name"]).first()
            if not existing:
                print(f"Generating embedding for {item['exercise_name']}...")
                embedding = get_embedding_sync(item["description"])
                new_guide = ExerciseGuide(
                    exercise_name=item["exercise_name"],
                    target_muscle=item["target_muscle"],
                    description=item["description"],
                    embedding=embedding
                )
                db.add(new_guide)
                count_added += 1
        
        if count_added > 0:
            db.commit()
            print(f"Seeding completed! Injected {count_added} exercise guides with embeddings.")
        else:
            print("All guides already exist. Seeding skipped.")

    except Exception as e:
        db.rollback()
        print(f"Error occurred during seeding: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    seed_exercise_guides()
