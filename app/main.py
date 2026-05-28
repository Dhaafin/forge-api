from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.core.scheduler import scheduler, start_scheduler
from app.api.v1.endpoints import auth, workouts 

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_scheduler()
    yield
    # Shutdown
    if scheduler.running:
        scheduler.shutdown()
        print("🛑 APScheduler Background Engine successfully stopped.")

app = FastAPI(
    title="Forge Gym API",
    description="Backend engine for Forge Gym Tracker Platform",
    version="1.0.0",
    lifespan=lifespan # Lifespan handler
)

# Routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(workouts.router, prefix="/api/v1/workouts", tags=["Workouts Core"]) 

@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "Welcome to Forge API",
    }