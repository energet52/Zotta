"""Authentication endpoints: register, login, refresh, MFA verify, me."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole, UserStatus
from app.models.session import UserSession, LoginAttempt
from app.models.mfa import MFADevice
from app.models.loan import ApplicantProfile
from app.models.audit import AuditLog
from app.schemas import (
    UserCreate, UserLogin, TokenResponse, UserResponse, UserUpdate,
    MFASetupResponse, MFAVerifyRequest, RefreshRequest,
    ChangePasswordRequest, ResetPasswordRequest,
)
from app.auth_utils import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    _generate_jti,
    MAX_FAILED_ATTEMPTS,
    LOCKOUT_MINUTES,
    ALGORITHM,
)
from app.config import settings
from app.services.error_logger import log_error
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _user_agent(request: Request) -> str:
    return request.headers.get("user-agent", "")[:500]


async def _record_login_attempt(
    db: AsyncSession,
    *,
    email: str,
    user_id: int | None,
    ip: str,
    ua: str,
    success: bool,
    failure_reason: str | None = None,
) -> None:
    attempt = LoginAttempt(
        email=email,
        user_id=user_id,
        ip_address=ip,
        user_agent=ua,
        success=success,
        failure_reason=failure_reason,
    )
    db.add(attempt)


async def _create_session(
    db: AsyncSession,
    user: User,
    jti: str,
    request: Request,
    expires_delta: timedelta | None = None,
    refresh_jti: str | None = None,
) -> UserSession:
    """Create a tracked session for the user."""
    expires = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    session = UserSession(
        user_id=user.id,
        token_jti=jti,
        refresh_token_jti=refresh_jti,
        device_info=_user_agent(request)[:255],
        ip_address=_client_ip(request),
        expires_at=expires,
    )
    db.add(session)
    return session


# ── Register ─────────────────────────────────────────────────


@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit("10/minute")
async def register(
    data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        # Validate password strength
        pwd_error = validate_password_strength(data.password)
        if pwd_error:
            raise HTTPException(status_code=400, detail=pwd_error)

        result = await db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Registration could not be completed. If you already have an account, please log in.",
            )

        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            role=UserRole.APPLICANT,
        )
        db.add(user)
        await db.flush()

        profile = ApplicantProfile(user_id=user.id)
        db.add(profile)

        jti = _generate_jti()
        refresh_jti = _generate_jti()
        access_token = create_access_token(
            {"sub": str(user.id), "role": user.role.value, "email": user.email}, jti=jti,
        )
        refresh_token = create_refresh_token({"sub": str(user.id)}, jti=refresh_jti)

        await _create_session(db, user, jti, request, refresh_jti=refresh_jti)
        await _record_login_attempt(
            db, email=data.email, user_id=user.id,
            ip=_client_ip(request), ua=_user_agent(request), success=True,
        )

        db.add(AuditLog(
            entity_type="auth", entity_id=user.id, action="register",
            user_id=user.id, ip_address=_client_ip(request),
            details=f"New account registered: {data.email}",
        ))

        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.auth", function_name="register")
        raise


# ── Login ────────────────────────────────────────────────────


@router.post("/login", response_model=TokenResponse)
@limiter.limit("600/minute")
async def login(
    data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        ip = _client_ip(request)
        ua = _user_agent(request)

        result = await db.execute(select(User).where(User.email == data.email))
        user = result.scalar_one_or_none()

        if not user:
            await _record_login_attempt(
                db, email=data.email, user_id=None, ip=ip, ua=ua,
                success=False, failure_reason="user_not_found",
            )
            await db.commit()
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Account lockout check
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            remaining = int((user.locked_until - datetime.now(timezone.utc)).total_seconds() / 60) + 1
            await _record_login_attempt(
                db, email=data.email, user_id=user.id, ip=ip, ua=ua,
                success=False, failure_reason="account_locked",
            )
            await db.commit()
            raise HTTPException(
                status_code=403,
                detail=f"Account locked. Try again in {remaining} minutes.",
            )

        # Status checks
        if user.status == UserStatus.DEACTIVATED.value:
            await _record_login_attempt(
                db, email=data.email, user_id=user.id, ip=ip, ua=ua,
                success=False, failure_reason="deactivated",
            )
            await db.commit()
            raise HTTPException(status_code=403, detail="Account is deactivated")

        if user.status == UserStatus.SUSPENDED.value:
            await _record_login_attempt(
                db, email=data.email, user_id=user.id, ip=ip, ua=ua,
                success=False, failure_reason="suspended",
            )
            await db.commit()
            raise HTTPException(status_code=403, detail="Account is suspended")

        if not verify_password(data.password, user.hashed_password):
            user.failed_login_attempts += 1
            locked = user.failed_login_attempts >= MAX_FAILED_ATTEMPTS
            if locked:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
                user.status = UserStatus.LOCKED.value
            await _record_login_attempt(
                db, email=data.email, user_id=user.id, ip=ip, ua=ua,
                success=False, failure_reason="bad_password",
            )
            db.add(AuditLog(
                entity_type="auth", entity_id=user.id,
                action="login_failed_locked" if locked else "login_failed",
                user_id=user.id, ip_address=ip,
                details=f"Failed login for {data.email} (attempt {user.failed_login_attempts})"
                + (f" — account locked for {LOCKOUT_MINUTES}m" if locked else ""),
            ))
            await db.commit()
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Successful auth — reset counters
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now(timezone.utc)
        if user.status == UserStatus.LOCKED.value:
            user.status = UserStatus.ACTIVE.value

        # Check MFA requirement
        if user.mfa_enabled:
            mfa_result = await db.execute(
                select(MFADevice).where(
                    MFADevice.user_id == user.id,
                    MFADevice.is_verified.is_(True),
                )
            )
            mfa_device = mfa_result.scalar_one_or_none()
            if mfa_device:
                # Return partial token that requires MFA verification
                mfa_token = create_access_token(
                    {"sub": str(user.id), "role": user.role.value, "email": user.email, "mfa_pending": True},
                    expires_delta=timedelta(minutes=5),
                )
                await _record_login_attempt(
                    db, email=data.email, user_id=user.id, ip=ip, ua=ua,
                    success=True, failure_reason="mfa_pending",
                )
                return TokenResponse(
                    access_token=mfa_token,
                    refresh_token="",
                    token_type="mfa_required",
                )

        jti = _generate_jti()
        refresh_jti = _generate_jti()
        access_token = create_access_token(
            {"sub": str(user.id), "role": user.role.value, "email": user.email}, jti=jti,
        )
        refresh_token = create_refresh_token({"sub": str(user.id)}, jti=refresh_jti)

        await _create_session(db, user, jti, request, refresh_jti=refresh_jti)
        await _record_login_attempt(
            db, email=data.email, user_id=user.id, ip=ip, ua=ua, success=True,
        )

        db.add(AuditLog(
            entity_type="auth", entity_id=user.id, action="login",
            user_id=user.id, ip_address=ip,
            details=f"Login successful: {user.email}",
        ))

        resp = TokenResponse(access_token=access_token, refresh_token=refresh_token)
        if user.must_change_password:
            resp.must_change_password = True
        return resp
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.auth", function_name="login")
        raise


# ── MFA Verify ───────────────────────────────────────────────


@router.post("/mfa/verify", response_model=TokenResponse)
@limiter.limit("10/minute")
async def mfa_verify(
    data: MFAVerifyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Verify MFA code and return full tokens."""
    try:
        import pyotp

        payload = decode_token(data.mfa_token)
        if not payload.get("mfa_pending"):
            raise HTTPException(status_code=400, detail="Invalid MFA token")

        user_id = int(payload["sub"])
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        mfa_result = await db.execute(
            select(MFADevice).where(
                MFADevice.user_id == user.id,
                MFADevice.is_verified.is_(True),
                MFADevice.is_primary.is_(True),
            )
        )
        device = mfa_result.scalar_one_or_none()
        if not device:
            raise HTTPException(status_code=400, detail="No MFA device configured")

        if device.device_type == "totp":
            totp = pyotp.TOTP(device.secret)
            if not totp.verify(data.code, valid_window=1):
                raise HTTPException(status_code=401, detail="Invalid MFA code")
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported MFA type: {device.device_type}")

        device.last_used_at = datetime.now(timezone.utc)

        jti = _generate_jti()
        refresh_jti = _generate_jti()
        access_token = create_access_token(
            {"sub": str(user.id), "role": user.role.value, "email": user.email}, jti=jti,
        )
        refresh_token = create_refresh_token({"sub": str(user.id)}, jti=refresh_jti)
        await _create_session(db, user, jti, request, refresh_jti=refresh_jti)

        db.add(AuditLog(
            entity_type="auth", entity_id=user.id, action="mfa_verified",
            user_id=user.id, ip_address=_client_ip(request),
            details=f"MFA verified for {user.email}",
        ))

        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.auth", function_name="mfa_verify")
        raise


# ── MFA Setup ────────────────────────────────────────────────


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate TOTP secret and provisioning URI for authenticator app setup."""
    try:
        import pyotp

        # Check for existing unverified device
        existing = await db.execute(
            select(MFADevice).where(
                MFADevice.user_id == current_user.id,
                MFADevice.device_type == "totp",
                MFADevice.is_verified.is_(False),
            )
        )
        device = existing.scalar_one_or_none()

        secret = pyotp.random_base32()
        if device:
            device.secret = secret
        else:
            device = MFADevice(
                user_id=current_user.id,
                device_type="totp",
                device_name="Authenticator App",
                secret=secret,
            )
            db.add(device)

        await db.flush()

        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=current_user.email,
            issuer_name=settings.lender_name,
        )

        return MFASetupResponse(
            provisioning_uri=provisioning_uri,
            device_id=device.id,
        )
    except Exception as e:
        await log_error(e, db=db, module="api.auth", function_name="mfa_setup")
        raise


@router.post("/mfa/confirm")
async def mfa_confirm(
    data: MFAVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm MFA setup by verifying a test code, then enable MFA on the account."""
    try:
        import pyotp

        device_result = await db.execute(
            select(MFADevice).where(
                MFADevice.user_id == current_user.id,
                MFADevice.device_type == "totp",
                MFADevice.is_verified.is_(False),
            )
        )
        device = device_result.scalar_one_or_none()
        if not device:
            raise HTTPException(status_code=400, detail="No pending MFA device")

        totp = pyotp.TOTP(device.secret)
        if not totp.verify(data.code, valid_window=1):
            raise HTTPException(status_code=401, detail="Invalid code — try again")

        device.is_verified = True
        device.is_primary = True
        current_user.mfa_enabled = True

        await db.flush()
        return {"status": "ok", "message": "MFA enabled successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.auth", function_name="mfa_confirm")
        raise


@router.delete("/mfa/disable")
async def mfa_disable(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disable MFA for current user and remove all devices."""
    try:
        from sqlalchemy import delete as sa_delete
        await db.execute(
            sa_delete(MFADevice).where(MFADevice.user_id == current_user.id)
        )
        current_user.mfa_enabled = False
        await db.flush()
        return {"status": "ok", "message": "MFA disabled"}
    except Exception as e:
        await log_error(e, db=db, module="api.auth", function_name="mfa_disable")
        raise


# ── Refresh ──────────────────────────────────────────────────


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("600/minute")
async def refresh_token(
    data: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Exchange a refresh token for a new access + refresh token pair.

    Implements refresh token rotation: the old refresh token is invalidated
    and a new one is issued. If a revoked token is reused, all sessions for
    that user are revoked (stolen token detection).
    """
    try:
        payload = decode_token(data.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user_id = int(payload["sub"])
        old_refresh_jti = payload.get("jti")

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")

        # Token rotation: verify the refresh token JTI is still active
        if old_refresh_jti:
            sess_result = await db.execute(
                select(UserSession).where(
                    UserSession.refresh_token_jti == old_refresh_jti,
                    UserSession.is_active.is_(True),
                )
            )
            old_session = sess_result.scalar_one_or_none()
            if old_session is None:
                # Possible token reuse attack — revoke all sessions for this user
                logger.warning("Refresh token reuse detected for user %s — revoking all sessions", user_id)
                await db.execute(
                    update(UserSession).where(
                        UserSession.user_id == user_id,
                        UserSession.is_active.is_(True),
                    ).values(is_active=False)
                )
                raise HTTPException(status_code=401, detail="Refresh token has been revoked")
            # Invalidate the old session
            old_session.is_active = False

        jti = _generate_jti()
        refresh_jti = _generate_jti()
        access_token = create_access_token(
            {"sub": str(user.id), "role": user.role.value, "email": user.email}, jti=jti,
        )
        new_refresh = create_refresh_token({"sub": str(user.id)}, jti=refresh_jti)

        await _create_session(db, user, jti, request, refresh_jti=refresh_jti)

        return TokenResponse(access_token=access_token, refresh_token=new_refresh)
    except (JWTError, ValueError, TypeError):
        # Invalid/expired/garbled refresh token should be a 401, not a server error.
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.auth", function_name="refresh_token")
        raise


# ── Logout ───────────────────────────────────────────────────


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke all active sessions for current user."""
    await db.execute(
        update(UserSession).where(
            UserSession.user_id == current_user.id,
            UserSession.is_active.is_(True),
        ).values(is_active=False)
    )
    db.add(AuditLog(
        entity_type="auth", entity_id=current_user.id, action="logout",
        user_id=current_user.id,
        details=f"User {current_user.email} logged out",
    ))
    return {"status": "ok", "message": "Logged out"}


# ── Me ───────────────────────────────────────────────────────


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user's profile (first_name, last_name, phone)."""
    try:
        if data.first_name is not None:
            current_user.first_name = data.first_name
        if data.last_name is not None:
            current_user.last_name = data.last_name
        if data.phone is not None:
            current_user.phone = data.phone
        await db.flush()
        await db.refresh(current_user)
        return current_user
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.auth", function_name="update_me")
        raise


# ── Sessions ─────────────────────────────────────────────────


@router.get("/sessions")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List active sessions for the current user."""
    result = await db.execute(
        select(UserSession).where(
            UserSession.user_id == current_user.id,
            UserSession.is_active.is_(True),
        ).order_by(UserSession.last_activity_at.desc())
    )
    sessions = result.scalars().all()
    return [
        {
            "id": s.id,
            "device_info": s.device_info,
            "ip_address": s.ip_address,
            "location": s.location,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "last_activity_at": s.last_activity_at.isoformat() if s.last_activity_at else None,
        }
        for s in sessions
    ]


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a specific session."""
    result = await db.execute(
        select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.is_active = False
    return {"status": "ok", "message": "Session revoked"}


# ── Change Password ──────────────────────────────────────────


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the current user's password."""
    try:
        pwd_error = validate_password_strength(data.new_password)
        if pwd_error:
            raise HTTPException(status_code=400, detail=pwd_error)

        if not verify_password(data.old_password, current_user.hashed_password):
            raise HTTPException(status_code=401, detail="Current password is incorrect")

        current_user.hashed_password = hash_password(data.new_password)
        current_user.password_changed_at = datetime.now(timezone.utc)
        current_user.must_change_password = False

        # Revoke all sessions except current
        await db.execute(
            update(UserSession).where(
                UserSession.user_id == current_user.id,
                UserSession.is_active.is_(True),
            ).values(is_active=False)
        )

        db.add(AuditLog(
            entity_type="auth", entity_id=current_user.id, action="password_changed",
            user_id=current_user.id,
            details=f"Password changed by {current_user.email}",
        ))

        return {"status": "ok", "message": "Password changed. All sessions revoked."}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.auth", function_name="change_password")
        raise
