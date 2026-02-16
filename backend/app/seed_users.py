"""Seed roles, permissions, and default role-permission mappings for user management."""

import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rbac import Role, Permission, RolePermission, UserRoleAssignment
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

# ── Permission definitions (module.object.action) ────────────

PERMISSIONS: list[dict] = [
    # Origination
    {"code": "origination.applications.view", "module": "origination", "object": "applications", "action": "view", "description": "View loan applications"},
    {"code": "origination.applications.create", "module": "origination", "object": "applications", "action": "create", "description": "Create loan applications"},
    {"code": "origination.applications.edit", "module": "origination", "object": "applications", "action": "edit", "description": "Edit loan applications"},
    {"code": "origination.applications.approve", "module": "origination", "object": "applications", "action": "approve", "description": "Approve loan applications"},
    {"code": "origination.applications.decline", "module": "origination", "object": "applications", "action": "decline", "description": "Decline loan applications"},
    {"code": "origination.applications.assign", "module": "origination", "object": "applications", "action": "assign", "description": "Assign applications to underwriters"},
    {"code": "origination.documents.view", "module": "origination", "object": "documents", "action": "view", "description": "View application documents"},
    {"code": "origination.documents.upload", "module": "origination", "object": "documents", "action": "upload", "description": "Upload application documents"},
    {"code": "origination.disbursements.create", "module": "origination", "object": "disbursements", "action": "create", "description": "Disburse approved loans"},
    # Collections
    {"code": "collections.cases.view", "module": "collections", "object": "cases", "action": "view", "description": "View collection cases"},
    {"code": "collections.cases.work", "module": "collections", "object": "cases", "action": "work", "description": "Work assigned collection cases"},
    {"code": "collections.cases.reassign", "module": "collections", "object": "cases", "action": "reassign", "description": "Reassign collection cases"},
    {"code": "collections.settlements.view", "module": "collections", "object": "settlements", "action": "view", "description": "View settlement offers"},
    {"code": "collections.settlements.offer", "module": "collections", "object": "settlements", "action": "offer", "description": "Make settlement offers"},
    {"code": "collections.settlements.approve", "module": "collections", "object": "settlements", "action": "approve", "description": "Approve settlement offers"},
    {"code": "collections.ptp.create", "module": "collections", "object": "ptp", "action": "create", "description": "Create promise-to-pay"},
    {"code": "collections.compliance.view", "module": "collections", "object": "compliance", "action": "view", "description": "View compliance rules"},
    {"code": "collections.compliance.manage", "module": "collections", "object": "compliance", "action": "manage", "description": "Manage compliance rules"},
    {"code": "collections.dashboard.view", "module": "collections", "object": "dashboard", "action": "view", "description": "View collections dashboard"},
    # Scoring
    {"code": "scoring.scorecards.view", "module": "scoring", "object": "scorecards", "action": "view", "description": "View scorecard definitions"},
    {"code": "scoring.scorecards.edit", "module": "scoring", "object": "scorecards", "action": "edit", "description": "Edit scorecard weights and bins"},
    {"code": "scoring.scorecards.create", "module": "scoring", "object": "scorecards", "action": "create", "description": "Create new scorecards"},
    {"code": "scoring.scorecards.promote", "module": "scoring", "object": "scorecards", "action": "promote", "description": "Promote challenger to champion"},
    {"code": "scoring.rules.view", "module": "scoring", "object": "rules", "action": "view", "description": "View business rules"},
    {"code": "scoring.rules.manage", "module": "scoring", "object": "rules", "action": "manage", "description": "Create/edit business rules"},
    # Sector Analysis
    {"code": "sectors.analysis.view", "module": "sectors", "object": "analysis", "action": "view", "description": "View sectorial analysis"},
    {"code": "sectors.policy.modify", "module": "sectors", "object": "policy", "action": "modify", "description": "Modify sector lending policies"},
    # Admin / Catalog
    {"code": "admin.catalog.view", "module": "admin", "object": "catalog", "action": "view", "description": "View catalog (merchants, products)"},
    {"code": "admin.catalog.manage", "module": "admin", "object": "catalog", "action": "manage", "description": "Manage catalog entries"},
    {"code": "admin.config.manage", "module": "admin", "object": "config", "action": "manage", "description": "Manage system configuration"},
    # Reports
    {"code": "reports.generate", "module": "reports", "object": "reports", "action": "generate", "description": "Generate reports"},
    {"code": "reports.export", "module": "reports", "object": "reports", "action": "export", "description": "Export report data"},
    {"code": "reports.dashboard.view", "module": "reports", "object": "dashboard", "action": "view", "description": "View reporting dashboards"},
    # User Management
    {"code": "users.view", "module": "users", "object": "users", "action": "view", "description": "View user list and details"},
    {"code": "users.create", "module": "users", "object": "users", "action": "create", "description": "Create new users"},
    {"code": "users.edit", "module": "users", "object": "users", "action": "edit", "description": "Edit user profiles"},
    {"code": "users.suspend", "module": "users", "object": "users", "action": "suspend", "description": "Suspend/reactivate users"},
    {"code": "users.deactivate", "module": "users", "object": "users", "action": "deactivate", "description": "Deactivate (offboard) users"},
    {"code": "users.roles.manage", "module": "users", "object": "roles", "action": "manage", "description": "Manage roles and permissions"},
    {"code": "users.roles.assign", "module": "users", "object": "roles", "action": "assign", "description": "Assign/remove roles for users"},
    {"code": "users.pending.approve", "module": "users", "object": "pending", "action": "approve", "description": "Approve pending user actions"},
    # Audit
    {"code": "audit.logs.view", "module": "audit", "object": "logs", "action": "view", "description": "View audit trail"},
    {"code": "audit.logs.export", "module": "audit", "object": "logs", "action": "export", "description": "Export audit trail data"},
    # GL
    {"code": "gl.accounts.view", "module": "gl", "object": "accounts", "action": "view", "description": "View GL accounts"},
    {"code": "gl.accounts.manage", "module": "gl", "object": "accounts", "action": "manage", "description": "Manage GL accounts"},
    {"code": "gl.journals.view", "module": "gl", "object": "journals", "action": "view", "description": "View journal entries"},
    {"code": "gl.journals.create", "module": "gl", "object": "journals", "action": "create", "description": "Create journal entries"},
    # Conversations
    {"code": "conversations.view", "module": "conversations", "object": "conversations", "action": "view", "description": "View customer conversations"},
    {"code": "conversations.manage", "module": "conversations", "object": "conversations", "action": "manage", "description": "Manage customer conversations"},
    # Customers
    {"code": "customers.view", "module": "customers", "object": "customers", "action": "view", "description": "View customer 360 data"},
    # Error Monitoring
    {"code": "errors.view", "module": "errors", "object": "errors", "action": "view", "description": "View error logs"},
    {"code": "errors.manage", "module": "errors", "object": "errors", "action": "manage", "description": "Manage error logs"},
    # Payments
    {"code": "payments.view", "module": "payments", "object": "payments", "action": "view", "description": "View payments"},
    {"code": "payments.create", "module": "payments", "object": "payments", "action": "create", "description": "Record payments"},
]

# ── Role definitions with permission mappings ────────────────

ROLE_DEFINITIONS: list[dict] = [
    {
        "name": "System Administrator",
        "description": "Full system access, user management, configuration",
        "is_system": True,
        "permissions": "*",  # all permissions
    },
    {
        "name": "Applicant",
        "description": "Consumer applicant — self-service portal access only",
        "is_system": True,
        "permissions": [],
    },
    {
        "name": "Loan Officer",
        "description": "Processes loan applications",
        "is_system": True,
        "permissions": [
            "origination.applications.view",
            "origination.applications.create",
            "origination.applications.edit",
            "origination.documents.view",
            "origination.documents.upload",
            "reports.dashboard.view",
            "customers.view",
        ],
    },
    {
        "name": "Junior Underwriter",
        "description": "Reviews applications and makes recommendations",
        "is_system": True,
        "permissions": [
            "origination.applications.view",
            "origination.applications.edit",
            "origination.documents.view",
            "origination.documents.upload",
            "scoring.scorecards.view",
            "scoring.rules.view",
            "reports.dashboard.view",
            "customers.view",
            "collections.cases.view",
            "collections.dashboard.view",
            "conversations.view",
        ],
    },
    {
        "name": "Senior Underwriter",
        "description": "Reviews, approves and declines applications",
        "is_system": True,
        "permissions": [
            "origination.applications.view",
            "origination.applications.edit",
            "origination.applications.approve",
            "origination.applications.decline",
            "origination.applications.assign",
            "origination.documents.view",
            "origination.documents.upload",
            "origination.disbursements.create",
            "scoring.scorecards.view",
            "scoring.rules.view",
            "reports.generate",
            "reports.dashboard.view",
            "customers.view",
            "collections.cases.view",
            "collections.dashboard.view",
            "conversations.view",
            "conversations.manage",
        ],
    },
    {
        "name": "Credit Risk Manager",
        "description": "Manages scoring models and credit policy",
        "is_system": True,
        "permissions": [
            "origination.applications.view",
            "scoring.scorecards.view",
            "scoring.scorecards.edit",
            "scoring.scorecards.create",
            "scoring.scorecards.promote",
            "scoring.rules.view",
            "scoring.rules.manage",
            "sectors.analysis.view",
            "sectors.policy.modify",
            "reports.generate",
            "reports.export",
            "reports.dashboard.view",
        ],
    },
    {
        "name": "Collections Agent",
        "description": "Works delinquent cases via phone/message",
        "is_system": True,
        "permissions": [
            "collections.cases.view",
            "collections.cases.work",
            "collections.ptp.create",
            "collections.settlements.view",
            "collections.settlements.offer",
            "collections.compliance.view",
            "collections.dashboard.view",
            "reports.dashboard.view",
            "customers.view",
        ],
    },
    {
        "name": "Collections Manager",
        "description": "Manages collections strategy and operations",
        "is_system": True,
        "permissions": [
            "collections.cases.view",
            "collections.cases.work",
            "collections.cases.reassign",
            "collections.ptp.create",
            "collections.settlements.view",
            "collections.settlements.offer",
            "collections.settlements.approve",
            "collections.compliance.view",
            "collections.compliance.manage",
            "collections.dashboard.view",
            "reports.generate",
            "reports.export",
            "reports.dashboard.view",
            "customers.view",
        ],
    },
    {
        "name": "Finance Manager",
        "description": "Manages general ledger and reconciliation",
        "is_system": True,
        "permissions": [
            "gl.accounts.view",
            "gl.accounts.manage",
            "gl.journals.view",
            "gl.journals.create",
            "payments.view",
            "payments.create",
            "reports.generate",
            "reports.export",
            "reports.dashboard.view",
        ],
    },
    {
        "name": "Compliance Officer",
        "description": "Monitors compliance and audit (read-only across system)",
        "is_system": True,
        "permissions": [
            "origination.applications.view",
            "origination.documents.view",
            "collections.cases.view",
            "collections.settlements.view",
            "collections.compliance.view",
            "collections.dashboard.view",
            "scoring.scorecards.view",
            "scoring.rules.view",
            "sectors.analysis.view",
            "gl.accounts.view",
            "gl.journals.view",
            "payments.view",
            "reports.generate",
            "reports.export",
            "reports.dashboard.view",
            "audit.logs.view",
            "audit.logs.export",
            "customers.view",
            "errors.view",
        ],
    },
]

# Mapping from legacy UserRole enum to new Role names
LEGACY_ROLE_MAP = {
    UserRole.APPLICANT: "Applicant",
    UserRole.JUNIOR_UNDERWRITER: "Junior Underwriter",
    UserRole.SENIOR_UNDERWRITER: "Senior Underwriter",
    UserRole.ADMIN: "System Administrator",
}


async def seed_user_management(db: AsyncSession) -> None:
    """Seed roles, permissions, role-permission mappings, and migrate existing users."""

    # Check if already seeded
    count = (await db.execute(select(func.count(Role.id)))).scalar() or 0
    if count > 0:
        logger.info("User management data already seeded (%d roles). Skipping.", count)
        return

    logger.info("Seeding user management data...")

    # 1. Seed permissions
    perm_map: dict[str, Permission] = {}
    for p in PERMISSIONS:
        perm = Permission(
            code=p["code"],
            module=p["module"],
            object=p["object"],
            action=p["action"],
            description=p.get("description"),
            scope_levels=p.get("scope_levels", ["own", "team", "branch", "all"]),
        )
        db.add(perm)
        perm_map[p["code"]] = perm

    await db.flush()
    logger.info("Seeded %d permissions.", len(perm_map))

    # 2. Seed roles and role-permission mappings
    role_map: dict[str, Role] = {}
    for rd in ROLE_DEFINITIONS:
        role = Role(
            name=rd["name"],
            description=rd["description"],
            is_system=rd.get("is_system", False),
        )
        db.add(role)
        await db.flush()
        role_map[rd["name"]] = role

        perms = rd["permissions"]
        if perms == "*":
            perms = list(perm_map.keys())

        for perm_code in perms:
            if perm_code in perm_map:
                rp = RolePermission(
                    role_id=role.id,
                    permission_id=perm_map[perm_code].id,
                    scope="all",
                )
                db.add(rp)

    await db.flush()
    logger.info("Seeded %d roles with permission mappings.", len(role_map))

    # 3. Migrate existing users: create UserRoleAssignment based on legacy role column
    result = await db.execute(select(User))
    users = result.scalars().all()
    migrated = 0
    for user in users:
        role_name = LEGACY_ROLE_MAP.get(user.role)
        if role_name and role_name in role_map:
            ura = UserRoleAssignment(
                user_id=user.id,
                role_id=role_map[role_name].id,
                is_primary=True,
            )
            db.add(ura)
            migrated += 1

    await db.flush()
    logger.info("Migrated %d existing users to new role assignments.", migrated)

    await db.commit()
    logger.info("User management seed complete.")
