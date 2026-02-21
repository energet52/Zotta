"""JWT token creation, password hashing, and access-control dependencies."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models.user import User, UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

ALGORITHM = "HS256"
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 30


# ── Password helpers ─────────────────────────────────────────

# Common weak passwords (top entries — extend as needed)
_COMMON_PASSWORDS = frozenset({
    "password", "12345678", "123456789", "1234567890", "qwerty123",
    "password1", "password123", "iloveyou", "sunshine", "princess",
    "football", "charlie", "access14", "trustno1", "letmein1",
    "abc12345", "monkey12", "master12", "dragon12", "login123",
    "passw0rd", "admin123", "welcome1", "mustang1", "shadow12",
})


def validate_password_strength(password: str) -> str | None:
    """Return an error message if the password is too weak, or None if it passes."""
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if len(password) > 128:
        return "Password must not exceed 128 characters"
    if not any(c.isupper() for c in password):
        return "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one digit"
    if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?`~" for c in password):
        return "Password must contain at least one special character"
    if password.lower() in _COMMON_PASSWORDS:
        return "This password is too common. Please choose a stronger password."
    return None


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ── Token helpers ────────────────────────────────────────────


def _generate_jti() -> str:
    """Generate a unique JWT ID for session tracking."""
    return uuid.uuid4().hex


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    jti: Optional[str] = None,
) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({
        "exp": expire,
        "type": "access",
        "jti": jti or _generate_jti(),
    })
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def create_refresh_token(data: dict, jti: Optional[str] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "jti": jti or _generate_jti(),
    })
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and return the JWT payload. Raises JWTError on failure."""
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])


# ── User dependencies ───────────────────────────────────────


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode JWT and return the current user. Checks session validity."""
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id_raw = payload.get("sub")
        token_type: str = payload.get("type")
        if user_id_raw is None or token_type != "access":
            raise credentials_exception
        user_id = int(user_id_raw)
    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    # Check session revocation if jti is present
    token_jti = payload.get("jti")
    if token_jti:
        from app.models.session import UserSession
        # Avoid ORM stale-row flush errors when sessions are concurrently revoked:
        # update heartbeat directly and treat zero updated rows as invalid session.
        update_result = await db.execute(
            update(UserSession)
            .where(
                UserSession.token_jti == token_jti,
                UserSession.is_active.is_(True),
            )
            .values(last_activity_at=datetime.now(timezone.utc))
        )
        if update_result.rowcount == 0:
            raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception
    # Check account status
    if user.status not in ("active",):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {user.status}",
        )
    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Return current user if valid token provided, else None."""
    if credentials is None:
        return None
    try:
        payload = jwt.decode(
            credentials.credentials, settings.secret_key, algorithms=[ALGORITHM]
        )
        user_id_raw = payload.get("sub")
        token_type: str = payload.get("type")
        if user_id_raw is None or token_type != "access":
            return None
        user_id = int(user_id_raw)
    except (JWTError, ValueError, TypeError):
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    return user


# ── Legacy role check ───────────────────────────────────────


def require_roles(*roles: UserRole):
    """Dependency factory that checks the user has one of the required legacy roles."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return role_checker


# ── Granular permission check ────────────────────────────────


def require_permission(*permission_codes: str):
    """Dependency factory that checks the user has at least one of the required permissions.

    Resolves the user's effective permissions from their RBAC role assignments.
    Falls back to legacy role: admin gets everything, underwriters get a reasonable set.
    """
    async def permission_checker(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        from app.models.rbac import UserRoleAssignment, RolePermission, Permission, Role

        # Collect all role IDs assigned to this user (including parent roles)
        ura_result = await db.execute(
            select(UserRoleAssignment.role_id).where(
                UserRoleAssignment.user_id == current_user.id,
            )
        )
        role_ids = [r[0] for r in ura_result.all()]

        # Walk parent chain for inherited permissions
        all_role_ids = set(role_ids)
        to_check = list(role_ids)
        while to_check:
            parent_result = await db.execute(
                select(Role.parent_role_id).where(
                    Role.id.in_(to_check),
                    Role.parent_role_id.isnot(None),
                )
            )
            parents = [r[0] for r in parent_result.all()]
            new_parents = [p for p in parents if p not in all_role_ids]
            all_role_ids.update(new_parents)
            to_check = new_parents

        if all_role_ids:
            # Check if any of the user's roles have the required permission
            perm_result = await db.execute(
                select(Permission.code).join(
                    RolePermission, RolePermission.permission_id == Permission.id
                ).where(
                    RolePermission.role_id.in_(all_role_ids),
                    Permission.code.in_(permission_codes),
                )
            )
            found = perm_result.scalars().all()
            if found:
                return current_user

        # Fallback: legacy role admin gets everything
        if current_user.role == UserRole.ADMIN:
            return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return permission_checker
