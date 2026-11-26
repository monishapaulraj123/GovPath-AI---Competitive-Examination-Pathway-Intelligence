from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.routers import assessments, auth, counsellor, exams, intelligence, planning, profile
from app.seed import seed_database

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="GovPath AI API",
    description="Agentic AI-Based Adaptive Government Examination Readiness, Knowledge Transfer and Career Pathway Optimization System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(exams.router)
app.include_router(assessments.router)
app.include_router(intelligence.router)
app.include_router(planning.router)
app.include_router(counsellor.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "GovPath AI Backend"}
