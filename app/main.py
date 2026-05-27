from fastapi import FastAPI
from app.api.v1.endpoints import auth, workouts 

app = FastAPI(
    title="Forge Gym API",
    description="Backend engine for Forge Gym Tracker Platform",
    version="1.0.0",
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