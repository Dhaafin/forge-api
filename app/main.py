from fastapi import FastAPI

app = FastAPI(
    title="Forge Gym API",
    description="Backend engine for Forge",
    version="1.0.0",
)

@app.get("/")
def read_root():
    return{
        "status": "online",
        "message": "Welcome to Forge API",
    }