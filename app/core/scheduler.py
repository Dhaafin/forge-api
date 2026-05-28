from apscheduler.schedulers.background import BackgroundScheduler
from datetime import timedelta, datetime

from app.core.database import SessionLocal
from app.models.user import User
from app.models.workout_session import WorkoutSession

scheduler = BackgroundScheduler()

def check_inactive_users_and_remind():
    """
    Automatic Cron Job that runs daily
    Detecting users that haven't documented a workout for more than 3 days
    """
    db = SessionLocal()
    try:
        print(f"[{datetime.now()}] 🔍 Running Daily Reminder Engine...")
        three_days_ago = datetime.utcnow() - timedelta(days=3)
        
        # Check all active users
        active_users = db.query(User).filter(User.is_active == True).all()
        
        for user in active_users:
            last_session = db.query(WorkoutSession).\
                filter(WorkoutSession.user_id == user.id).\
                filter(WorkoutSession.start_time >= three_days_ago).\
                first()
                
            if not last_session:
                # Push notifications
                print(f"⚠️ ALERT: Member {user.name} ({user.email}) sudah 3 hari tidak latihan! Memicu Push Notif...")
                
    except Exception as e:
        print(f"❌ Error in scheduler job: {str(e)}")
    finally:
        db.close()

def start_scheduler():
    """
    Runs Daemon Scheduler
    """
    if not scheduler.running:
        # Create a checker for 3 days
        scheduler.add_job(check_inactive_users_and_remind, 'interval', hours=24, id='daily_gym_reminder')
        scheduler.start()
        print("⏰ APScheduler Background Engine successfully started!")