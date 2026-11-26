from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Notification, StudentProfile, User
from app.schemas import AuthResponse, UserLoginRequest, UserRegisterRequest
from app.security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _serialize_user(user: User, profile: StudentProfile | None) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_demo": user.is_demo,
        "primary_target_exam": profile.primary_target_exam if profile else "UPSC_CSE",
        "display_name": profile.display_name if profile else user.full_name,
    }


@router.post("/register", response_model=AuthResponse)
def register(payload: UserRegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        is_demo=False,
    )
    db.add(user)
    db.flush()

    profile = StudentProfile(
        user_id=user.id,
        display_name=payload.full_name.strip(),
        primary_target_exam=payload.primary_target_exam,
        secondary_target_exams=[],
        preferred_exams=[payload.primary_target_exam],
    )
    db.add(profile)
    db.add(
        Notification(
            user_id=user.id,
            title="Welcome to GovPath AI — Start with a Diagnostic",
            message="Take a 10-question diagnostic assessment to replace baseline zero-evidence estimates with your actual competency profile.",
            category="assessment",
            action_route="/assessments",
        )
    )
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.email)
    return {"access_token": token, "token_type": "bearer", "user": _serialize_user(user, profile)}


@router.post("/login", response_model=AuthResponse)
def login(payload: UserLoginRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    token = create_access_token(user.id, user.email)
    return {"access_token": token, "token_type": "bearer", "user": _serialize_user(user, profile)}


@router.post("/demo", response_model=AuthResponse)
def demo_login(db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == "demo@govpath.ai").first()
    if not user:
        raise HTTPException(status_code=404, detail="Demo account not initialized")
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    token = create_access_token(user.id, user.email)
    return {"access_token": token, "token_type": "bearer", "user": _serialize_user(user, profile)}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    return _serialize_user(current_user, profile)
