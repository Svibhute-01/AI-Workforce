from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import User
from ..schemas import AuthResponse, LoginRequest, UserCreate, UserResponse
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return AuthResponse(access_token=create_access_token(str(user.id)), user=user)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return AuthResponse(access_token=create_access_token(str(user.id)), user=user)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user