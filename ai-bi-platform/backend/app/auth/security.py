"""JWT authentication and role-based authorisation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database.session import get_db
from app.models.warehouse import AppUser

import bcrypt
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

ROLES = ("admin", "analyst", "viewer")


def hash_password(raw: str) -> str:
       # bcrypt has a 72-byte limit; truncate defensively.
       pw = raw.encode("utf-8")[:72]
       return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    pw = raw.encode("utf-8")[:72]
    return bcrypt.checkpw(pw, hashed.encode("utf-8"))


def create_token(email: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": email, "role": role, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def current_user(token: str | None = Depends(oauth2_scheme),
                 db: Session = Depends(get_db)) -> AppUser:
    err = HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.",
                        headers={"WWW-Authenticate": "Bearer"})
    if not token:
        raise err
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        email = payload.get("sub")
    except JWTError:
        raise err from None
    user = db.execute(select(AppUser).where(AppUser.email == email)).scalar_one_or_none()
    if not user:
        raise err
    return user


def require_role(*allowed: str):
    """Dependency factory: restrict an endpoint to specific roles.

    Viewers can read dashboards; analysts can also upload data; admins
    can do everything.
    """
    def _check(user: AppUser = Depends(current_user)) -> AppUser:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                f"This action needs one of these roles: {', '.join(allowed)}.")
        return user
    return _check
