"""User Management API: CRUD, role assignment, maker-checker, sessions."""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, update, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User, UserRole, UserStatus
from app.models.rbac import (
    Role, Permission, RolePermission, UserRoleAssignment,
    PendingAction, PendingActionStatus,
)
from app.models.session import UserSession, LoginAttempt
from app.models.mfa import MFADevice
from app.models.audit import AuditLog
from app.auth_utils import (
    get_current_user,
    require_permission,
    hash_password,
)
from app.schemas import (
    UserResponse,
    UserDetailResponse,
    UserRoleAssignmentResponse,
    AdminUserCreate,
    AdminUserUpdate,
    AssignRolesRequest,
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    RoleBriefResponse,
    PermissionResponse,
    PendingActionResponse,
    PendingActionDecision,
)
from app.services.error_logger import log_error

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────


async def _audit(
    db: AsyncSession,
    entity_type: str,
    entity_id: int,
    action: str,
    user_id: int,
    old_values: dict | None = None,
    new_values: dict | None = None,
    details: str | None = None,
) -> None:
    log = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        user_id=user_id,
        old_values=old_values,
        new_values=new_values,
        details=details,
    )
    db.add(log)


async def _get_user_effective_permissions(db: AsyncSession, user_id: int) -> list[str]:
    """Resolve all permission codes for a user through their role assignments."""
    result = await db.execute(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRoleAssignment, UserRoleAssignment.role_id == RolePermission.role_id)
        .where(UserRoleAssignment.user_id == user_id)
        .distinct()
    )
    return list(result.scalars().all())


async def _build_user_detail(db: AsyncSession, user: User) -> dict:
    """Build the full user detail response."""
    # Roles
    ura_result = await db.execute(
        select(UserRoleAssignment, Role.name).join(
            Role, Role.id == UserRoleAssignment.role_id
        ).where(UserRoleAssignment.user_id == user.id)
    )
    roles = [
        {
            "id": ura.id,
            "role_id": ura.role_id,
            "role_name": name,
            "granted_by": ura.granted_by,
            "granted_at": ura.granted_at,
            "expires_at": ura.expires_at,
            "is_primary": ura.is_primary,
        }
        for ura, name in ura_result.all()
    ]

    # Effective permissions
    perms = await _get_user_effective_permissions(db, user.id)

    # Active sessions count
    sess_count = (await db.execute(
        select(func.count(UserSession.id)).where(
            UserSession.user_id == user.id,
            UserSession.is_active.is_(True),
        )
    )).scalar() or 0

    # Recent login attempts
    login_result = await db.execute(
        select(LoginAttempt).where(
            LoginAttempt.user_id == user.id
        ).order_by(LoginAttempt.created_at.desc()).limit(10)
    )
    recent_logins = [
        {
            "id": la.id,
            "ip_address": la.ip_address,
            "success": la.success,
            "failure_reason": la.failure_reason,
            "created_at": la.created_at.isoformat() if la.created_at else None,
        }
        for la in login_result.scalars().all()
    ]

    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "middle_name": user.middle_name,
        "display_name": user.display_name,
        "phone": user.phone,
        "role": user.role.value if hasattr(user.role, "value") else user.role,
        "status": user.status,
        "employee_id": user.employee_id,
        "department": user.department,
        "job_title": user.job_title,
        "timezone": user.timezone,
        "language": user.language,
        "profile_photo_url": user.profile_photo_url,
        "mfa_enabled": user.mfa_enabled,
        "last_login_at": user.last_login_at,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "roles": roles,
        "effective_permissions": perms,
        "active_sessions_count": sess_count,
        "recent_login_attempts": recent_logins,
    }


# ═══════════════════════════════════════════════════════════════
# USER CRUD
# ═══════════════════════════════════════════════════════════════


@router.get("/", response_model=list[UserResponse])
async def list_users(
    search: str = Query(default="", max_length=200),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    role_filter: Optional[str] = Query(default=None, alias="role"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_permission("users.view")),
    db: AsyncSession = Depends(get_db),
):
    """List users with search & filters."""
    q = select(User)
    if search:
        q = q.where(
            User.email.ilike(f"%{search}%")
            | User.first_name.ilike(f"%{search}%")
            | User.last_name.ilike(f"%{search}%")
            | User.employee_id.ilike(f"%{search}%")
        )
    if status_filter:
        q = q.where(User.status == status_filter)
    if role_filter:
        q = q.where(User.role == role_filter)
    q = q.order_by(User.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/count")
async def user_count(
    current_user: User = Depends(require_permission("users.view")),
    db: AsyncSession = Depends(get_db),
):
    """Return total user count and breakdown by status."""
    total = (await db.execute(select(func.count(User.id)))).scalar() or 0
    by_status = {}
    for s in UserStatus:
        c = (await db.execute(
            select(func.count(User.id)).where(User.status == s.value)
        )).scalar() or 0
        by_status[s.value] = c
    return {"total": total, "by_status": by_status}


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_permission("users.view")),
    db: AsyncSession = Depends(get_db),
):
    """Get full user detail including roles, permissions, sessions."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return await _build_user_detail(db, user)


@router.post("/", response_model=UserDetailResponse, status_code=201)
async def create_user(
    data: AdminUserCreate,
    current_user: User = Depends(require_permission("users.create")),
    db: AsyncSession = Depends(get_db),
):
    """Admin creates a new user."""
    try:
        # Check email uniqueness
        existing = await db.execute(select(User).where(User.email == data.email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")

        # Map role string to enum
        try:
            legacy_role = UserRole(data.role)
        except ValueError:
            legacy_role = UserRole.APPLICANT

        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            middle_name=data.middle_name,
            phone=data.phone,
            role=legacy_role,
            employee_id=data.employee_id,
            department=data.department,
            job_title=data.job_title,
            timezone=data.timezone,
            language=data.language,
            must_change_password=data.must_change_password,
        )
        db.add(user)
        await db.flush()

        # Assign roles
        for role_id in data.role_ids:
            role_exists = await db.execute(select(Role).where(Role.id == role_id))
            if role_exists.scalar_one_or_none():
                ura = UserRoleAssignment(
                    user_id=user.id,
                    role_id=role_id,
                    granted_by=current_user.id,
                    is_primary=(role_id == data.role_ids[0]),
                )
                db.add(ura)

        await db.flush()
        await _audit(
            db, "user", user.id, "create", current_user.id,
            new_values={"email": user.email, "roles": data.role_ids},
        )

        return await _build_user_detail(db, user)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.users", function_name="create_user")
        raise


@router.patch("/{user_id}", response_model=UserDetailResponse)
async def update_user(
    user_id: int,
    data: AdminUserUpdate,
    current_user: User = Depends(require_permission("users.edit")),
    db: AsyncSession = Depends(get_db),
):
    """Admin updates user profile fields."""
    try:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        old_values = {}
        new_values = {}

        for field in [
            "first_name", "last_name", "middle_name", "display_name",
            "phone", "employee_id", "department", "job_title",
            "timezone", "language", "status", "is_active",
        ]:
            val = getattr(data, field, None)
            if val is not None:
                old_values[field] = getattr(user, field)
                setattr(user, field, val)
                new_values[field] = val

        await db.flush()
        await _audit(
            db, "user", user.id, "update", current_user.id,
            old_values=old_values, new_values=new_values,
        )

        return await _build_user_detail(db, user)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.users", function_name="update_user")
        raise


# ── User status actions ──────────────────────────────────────


@router.post("/{user_id}/suspend")
async def suspend_user(
    user_id: int,
    current_user: User = Depends(require_permission("users.suspend")),
    db: AsyncSession = Depends(get_db),
):
    """Suspend a user account."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot suspend yourself")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_status = user.status
    user.status = UserStatus.SUSPENDED.value
    user.is_active = False

    # Revoke all sessions
    await db.execute(
        update(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.is_active.is_(True),
        ).values(is_active=False)
    )

    await _audit(
        db, "user", user_id, "suspend", current_user.id,
        old_values={"status": old_status},
        new_values={"status": UserStatus.SUSPENDED.value},
    )
    return {"status": "ok", "message": f"User {user.email} suspended"}


@router.post("/{user_id}/reactivate")
async def reactivate_user(
    user_id: int,
    current_user: User = Depends(require_permission("users.suspend")),
    db: AsyncSession = Depends(get_db),
):
    """Reactivate a suspended user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_status = user.status
    user.status = UserStatus.ACTIVE.value
    user.is_active = True
    user.locked_until = None
    user.failed_login_attempts = 0

    await _audit(
        db, "user", user_id, "reactivate", current_user.id,
        old_values={"status": old_status},
        new_values={"status": UserStatus.ACTIVE.value},
    )
    return {"status": "ok", "message": f"User {user.email} reactivated"}


@router.post("/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    current_user: User = Depends(require_permission("users.deactivate")),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate (offboard) a user."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.status = UserStatus.DEACTIVATED.value
    user.is_active = False

    await db.execute(
        update(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.is_active.is_(True),
        ).values(is_active=False)
    )

    await _audit(
        db, "user", user_id, "deactivate", current_user.id,
        details=f"User {user.email} deactivated by {current_user.email}",
    )
    return {"status": "ok", "message": f"User {user.email} deactivated"}


@router.post("/{user_id}/unlock")
async def unlock_user(
    user_id: int,
    current_user: User = Depends(require_permission("users.suspend")),
    db: AsyncSession = Depends(get_db),
):
    """Unlock a locked account."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.status = UserStatus.ACTIVE.value
    user.locked_until = None
    user.failed_login_attempts = 0
    user.is_active = True

    await _audit(db, "user", user_id, "unlock", current_user.id)
    return {"status": "ok", "message": f"User {user.email} unlocked"}


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    data: dict,
    current_user: User = Depends(require_permission("users.edit")),
    db: AsyncSession = Depends(get_db),
):
    """Admin resets a user's password."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_password = data.get("new_password", "")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user.hashed_password = hash_password(new_password)
    user.must_change_password = True
    user.password_changed_at = datetime.now(timezone.utc)

    # Revoke sessions
    await db.execute(
        update(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.is_active.is_(True),
        ).values(is_active=False)
    )

    await _audit(db, "user", user_id, "password_reset", current_user.id)
    return {"status": "ok", "message": "Password reset. User must change on next login."}


# ═══════════════════════════════════════════════════════════════
# ROLE ASSIGNMENT
# ═══════════════════════════════════════════════════════════════


@router.get("/{user_id}/roles", response_model=list[UserRoleAssignmentResponse])
async def get_user_roles(
    user_id: int,
    current_user: User = Depends(require_permission("users.view")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserRoleAssignment, Role.name).join(
            Role, Role.id == UserRoleAssignment.role_id
        ).where(UserRoleAssignment.user_id == user_id)
    )
    return [
        {
            "id": ura.id,
            "role_id": ura.role_id,
            "role_name": name,
            "granted_by": ura.granted_by,
            "granted_at": ura.granted_at,
            "expires_at": ura.expires_at,
            "is_primary": ura.is_primary,
        }
        for ura, name in result.all()
    ]


@router.put("/{user_id}/roles")
async def assign_roles(
    user_id: int,
    data: AssignRolesRequest,
    current_user: User = Depends(require_permission("users.roles.assign")),
    db: AsyncSession = Depends(get_db),
):
    """Replace all roles for a user (SoD check: cannot assign roles to yourself)."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot modify your own roles (SoD)")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Remove existing assignments
    await db.execute(
        sa_delete(UserRoleAssignment).where(UserRoleAssignment.user_id == user_id)
    )

    # Add new
    for i, role_id in enumerate(data.role_ids):
        role_check = await db.execute(select(Role).where(Role.id == role_id))
        if not role_check.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"Role {role_id} not found")
        ura = UserRoleAssignment(
            user_id=user_id,
            role_id=role_id,
            granted_by=current_user.id,
            is_primary=(i == 0),
        )
        db.add(ura)

    await db.flush()
    await _audit(
        db, "user", user_id, "roles_assigned", current_user.id,
        new_values={"role_ids": data.role_ids},
    )
    return {"status": "ok", "role_ids": data.role_ids}


# ═══════════════════════════════════════════════════════════════
# ROLES CRUD
# ═══════════════════════════════════════════════════════════════


@router.get("/roles/all", response_model=list[RoleBriefResponse])
async def list_roles(
    current_user: User = Depends(require_permission("users.view")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Role).order_by(Role.name))
    return result.scalars().all()


@router.get("/roles/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: int,
    current_user: User = Depends(require_permission("users.view")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Get permissions
    perm_result = await db.execute(
        select(Permission).join(
            RolePermission, RolePermission.permission_id == Permission.id
        ).where(RolePermission.role_id == role_id)
    )
    permissions = perm_result.scalars().all()

    # User count
    user_count = (await db.execute(
        select(func.count(UserRoleAssignment.id)).where(
            UserRoleAssignment.role_id == role_id
        )
    )).scalar() or 0

    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "parent_role_id": role.parent_role_id,
        "is_system": role.is_system,
        "is_active": role.is_active,
        "permissions": permissions,
        "user_count": user_count,
        "created_at": role.created_at,
        "updated_at": role.updated_at,
    }


@router.post("/roles", response_model=RoleResponse, status_code=201)
async def create_role(
    data: RoleCreate,
    current_user: User = Depends(require_permission("users.roles.manage")),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(Role).where(Role.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Role name already exists")

    role = Role(
        name=data.name,
        description=data.description,
        parent_role_id=data.parent_role_id,
    )
    db.add(role)
    await db.flush()

    # Assign permissions
    for code in data.permission_codes:
        perm_result = await db.execute(select(Permission).where(Permission.code == code))
        perm = perm_result.scalar_one_or_none()
        if perm:
            rp = RolePermission(role_id=role.id, permission_id=perm.id, scope="all")
            db.add(rp)

    await db.flush()
    await _audit(
        db, "role", role.id, "create", current_user.id,
        new_values={"name": role.name, "permissions": data.permission_codes},
    )
    return await get_role(role.id, current_user, db)


@router.patch("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    data: RoleUpdate,
    current_user: User = Depends(require_permission("users.roles.manage")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system and data.name and data.name != role.name:
        raise HTTPException(status_code=400, detail="Cannot rename system roles")

    if data.name is not None:
        role.name = data.name
    if data.description is not None:
        role.description = data.description
    if data.parent_role_id is not None:
        role.parent_role_id = data.parent_role_id
    if data.is_active is not None:
        role.is_active = data.is_active

    # Update permissions if provided
    if data.permission_codes is not None:
        await db.execute(
            sa_delete(RolePermission).where(RolePermission.role_id == role_id)
        )
        for code in data.permission_codes:
            perm_result = await db.execute(select(Permission).where(Permission.code == code))
            perm = perm_result.scalar_one_or_none()
            if perm:
                rp = RolePermission(role_id=role.id, permission_id=perm.id, scope="all")
                db.add(rp)

    await db.flush()
    await _audit(db, "role", role.id, "update", current_user.id)
    return await get_role(role.id, current_user, db)


# ═══════════════════════════════════════════════════════════════
# PERMISSIONS
# ═══════════════════════════════════════════════════════════════


@router.get("/permissions/all", response_model=list[PermissionResponse])
async def list_permissions(
    current_user: User = Depends(require_permission("users.view")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Permission).order_by(Permission.module, Permission.code))
    return result.scalars().all()


# ═══════════════════════════════════════════════════════════════
# PENDING ACTIONS (Maker-Checker)
# ═══════════════════════════════════════════════════════════════


@router.get("/pending-actions", response_model=list[PendingActionResponse])
async def list_pending_actions(
    current_user: User = Depends(require_permission("users.pending.approve")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PendingAction).where(
            PendingAction.status == PendingActionStatus.PENDING.value
        ).order_by(PendingAction.created_at.desc())
    )
    actions = result.scalars().all()
    out = []
    for a in actions:
        # Resolve requester name
        req = await db.execute(select(User).where(User.id == a.requested_by))
        requester = req.scalar_one_or_none()
        out.append({
            **{c.name: getattr(a, c.name) for c in a.__table__.columns},
            "requester_name": requester.full_name if requester else None,
            "approver_name": None,
        })
    return out


@router.post("/pending-actions/{action_id}/decide")
async def decide_pending_action(
    action_id: int,
    data: PendingActionDecision,
    current_user: User = Depends(require_permission("users.pending.approve")),
    db: AsyncSession = Depends(get_db),
):
    """Approve or reject a pending action (SoD: cannot approve your own request)."""
    result = await db.execute(
        select(PendingAction).where(PendingAction.id == action_id)
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Pending action not found")
    if action.status != PendingActionStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Action already resolved")
    if action.requested_by == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot approve your own request (SoD)")

    if data.approved:
        action.status = PendingActionStatus.APPROVED.value
        action.approved_by = current_user.id
        action.resolved_at = datetime.now(timezone.utc)
        # Execute the pending action
        await _execute_pending_action(db, action, current_user)
    else:
        action.status = PendingActionStatus.REJECTED.value
        action.approved_by = current_user.id
        action.rejection_reason = data.rejection_reason
        action.resolved_at = datetime.now(timezone.utc)

    await _audit(
        db, "pending_action", action_id,
        "approve" if data.approved else "reject",
        current_user.id,
    )
    return {"status": "ok", "decision": "approved" if data.approved else "rejected"}


async def _execute_pending_action(
    db: AsyncSession,
    action: PendingAction,
    approver: User,
) -> None:
    """Execute an approved pending action (e.g., role change, deactivation)."""
    payload = action.payload or {}
    if action.action_type == "role_change":
        user_id = action.target_user_id
        new_role_ids = payload.get("role_ids", [])
        await db.execute(
            sa_delete(UserRoleAssignment).where(UserRoleAssignment.user_id == user_id)
        )
        for i, rid in enumerate(new_role_ids):
            ura = UserRoleAssignment(
                user_id=user_id, role_id=rid,
                granted_by=approver.id, is_primary=(i == 0),
            )
            db.add(ura)
    elif action.action_type == "deactivate":
        user_id = action.target_user_id
        if user_id:
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if user:
                user.status = UserStatus.DEACTIVATED.value
                user.is_active = False
    elif action.action_type == "suspend":
        user_id = action.target_user_id
        if user_id:
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if user:
                user.status = UserStatus.SUSPENDED.value
                user.is_active = False


# ═══════════════════════════════════════════════════════════════
# USER SESSIONS (admin view)
# ═══════════════════════════════════════════════════════════════


@router.get("/{user_id}/sessions")
async def get_user_sessions(
    user_id: int,
    current_user: User = Depends(require_permission("users.view")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserSession).where(
            UserSession.user_id == user_id,
        ).order_by(UserSession.last_activity_at.desc()).limit(20)
    )
    sessions = result.scalars().all()
    return [
        {
            "id": s.id,
            "device_info": s.device_info,
            "ip_address": s.ip_address,
            "location": s.location,
            "is_active": s.is_active,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "last_activity_at": s.last_activity_at.isoformat() if s.last_activity_at else None,
        }
        for s in sessions
    ]


@router.post("/{user_id}/sessions/revoke-all")
async def revoke_all_sessions(
    user_id: int,
    current_user: User = Depends(require_permission("users.suspend")),
    db: AsyncSession = Depends(get_db),
):
    """Revoke all active sessions for a specific user."""
    count = (await db.execute(
        select(func.count(UserSession.id)).where(
            UserSession.user_id == user_id,
            UserSession.is_active.is_(True),
        )
    )).scalar() or 0

    await db.execute(
        update(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.is_active.is_(True),
        ).values(is_active=False)
    )

    await _audit(db, "user", user_id, "sessions_revoked", current_user.id)
    return {"status": "ok", "sessions_revoked": count}


# ═══════════════════════════════════════════════════════════════
# LOGIN HISTORY (admin view)
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
# AI FEATURES
# ═══════════════════════════════════════════════════════════════


@router.post("/ai/recommend-roles")
async def ai_recommend_roles(
    data: dict,
    current_user: User = Depends(require_permission("users.roles.manage")),
    db: AsyncSession = Depends(get_db),
):
    """AI-powered role recommendation based on department/title."""
    from app.services.user_ai import recommend_roles
    result = await recommend_roles(
        db,
        department=data.get("department"),
        job_title=data.get("job_title"),
    )
    return {"recommendations": result}


@router.post("/ai/query")
async def ai_admin_query(
    data: dict,
    current_user: User = Depends(require_permission("users.view")),
    db: AsyncSession = Depends(get_db),
):
    """Natural language admin query about users."""
    from app.services.user_ai import admin_nlp_query
    query_text = data.get("query", "")
    if not query_text:
        raise HTTPException(status_code=400, detail="Query text required")
    return await admin_nlp_query(db, query_text)


@router.get("/ai/login-analytics")
async def ai_login_analytics(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(require_permission("users.view")),
    db: AsyncSession = Depends(get_db),
):
    """Login analytics for the admin dashboard."""
    from app.services.user_anomaly import get_login_analytics
    return await get_login_analytics(db, days)


@router.get("/{user_id}/anomaly-check")
async def check_user_anomalies(
    user_id: int,
    current_user: User = Depends(require_permission("users.view")),
    db: AsyncSession = Depends(get_db),
):
    """Check a user's recent login patterns for anomalies."""
    from app.services.user_anomaly import detect_login_anomalies
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Use the user's last known IP as current for demonstration
    last_attempt_result = await db.execute(
        select(LoginAttempt).where(
            LoginAttempt.user_id == user_id,
            LoginAttempt.success.is_(True),
        ).order_by(LoginAttempt.created_at.desc()).limit(1)
    )
    last = last_attempt_result.scalar_one_or_none()

    result = await detect_login_anomalies(
        db, user_id,
        current_ip=last.ip_address if last else "",
        current_ua=last.user_agent if last else "",
    )
    return result


@router.get("/{user_id}/login-history")
async def get_login_history(
    user_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_permission("users.view")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LoginAttempt).where(
            LoginAttempt.user_id == user_id
        ).order_by(LoginAttempt.created_at.desc()).limit(limit)
    )
    attempts = result.scalars().all()
    return [
        {
            "id": a.id,
            "email": a.email,
            "ip_address": a.ip_address,
            "user_agent": a.user_agent,
            "location": a.location,
            "success": a.success,
            "failure_reason": a.failure_reason,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in attempts
    ]
