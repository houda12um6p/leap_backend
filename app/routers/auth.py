from fastapi import APIRouter, Depends
from pydantic import BaseModel as _Base
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.user import User
from ..schemas.user import Token, UserCreate, UserLogin, UserResponse
from ..services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse)
def register(user_data: UserCreate, db: Session = Depends(get_db)) -> User:
    auth_service = AuthService(db)
    user = auth_service.register_user(user_data)
    return user


@router.post("/login", response_model=Token)
def login(login_data: UserLogin, db: Session = Depends(get_db)) -> dict[str, str]:
    auth_service = AuthService(db)
    user = auth_service.authenticate_user(login_data)
    access_token = auth_service.create_access_token_for_user(user)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)) -> User:
    return current_user


class ForgotPasswordRequest(_Base):
    email: str


@router.post("/forgot-password")
def forgot_password(
    body: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Always returns 200 regardless of whether the email exists.
    This prevents user enumeration attacks.
    In production this would send a reset email.
    """
    user = db.query(User).filter(User.email == body.email).first()
    if user:
        # TODO: send reset email via SMTP when configured
        pass
    return {
        "message": "If this address exists, you will receive "
                   "an email with reset instructions."
    }
