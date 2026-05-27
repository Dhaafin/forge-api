from fastapi import FastAPI
from app.api.v1.endpoints import auth

app = FastAPI(
    title="Forge Gym API",
    description="Backend engine for Forge",
    version="1.0.0",
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])

@app.get("/")
def read_root():
    return{
        "status": "online",
        "message": "Welcome to Forge API",
    }