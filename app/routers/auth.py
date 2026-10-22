import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import Token, UserCreate, UserRead
from app.security import AdminUser, CurrentUser, authenticate_user, create_access_token, hash_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/token", response_model=Token, summary="Obtain a JWT access token")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: Annotated[Session, Depends(get_db)]) -> Token:
    user = authenticate_user(db, form.username, form.password)
    if user is None:
        logger.warning("Failed login for username=%s", form.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expires_in = create_access_token(user)
    logger.info("User %s logged in", user.username)
    return Token(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserRead, summary="Current user")
def me(user: CurrentUser) -> User:
    return user


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED, summary="Create a user (admin)")
def create_user(payload: UserCreate, admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> User:
    if db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    user = User(username=payload.username, hashed_password=hash_password(payload.password), role=payload.role.value)
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Admin %s created user %s with role %s", admin.username, user.username, user.role)
    return user
