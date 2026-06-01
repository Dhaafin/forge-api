from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_swagger_ui_html
from contextlib import asynccontextmanager
import secrets

from app.core.scheduler import scheduler, start_scheduler
from app.api.v1.endpoints import auth, workouts, ai_coach

security = HTTPBasic()

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, "dhaafinm")
    correct_password = secrets.compare_digest(credentials.password, "wertyer5321")
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Basic"},
        )

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    if scheduler.running:
        scheduler.shutdown()
        print("🛑 APScheduler Background Engine successfully stopped.")

app = FastAPI(
    title="Forge Gym API",
    description="Backend engine for Forge Gym Tracker Platform",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(workouts.router, prefix="/api/v1/workouts", tags=["Workouts Core"])
app.include_router(ai_coach.router, prefix="/api/v1/ai", tags=["AI Coach"])

@app.get("/", dependencies=[Depends(verify_credentials)])
def read_root():
    return {
        "status": "online",
        "message": "Welcome to Forge API",
    }

@app.get("/docs", include_in_schema=False, dependencies=[Depends(verify_credentials)])
async def custom_swagger():
    return get_swagger_ui_html(openapi_url="/openapi.json", title="Forge API Docs")

@app.get("/openapi.json", include_in_schema=False, dependencies=[Depends(verify_credentials)])
async def custom_openapi():
    return app.openapi()