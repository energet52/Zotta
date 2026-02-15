"""Administration endpoints for hire-purchase catalog management and rules."""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth_utils import require_roles
from app.database import get_db
from app.models.user import User, UserRole
from app.models.decision import DecisionRulesConfig
from app.models.catalog import (
    Merchant,
    Branch,
    ProductCategory,
    CreditProduct,
    ProductScoreRange,
    ProductFee,
)
from app.schemas import (
    MerchantCreate,
    MerchantUpdate,
    MerchantResponse,
    BranchCreate,
    BranchUpdate,
    BranchResponse,
    ProductCategoryCreate,
    ProductCategoryUpdate,
    ProductCategoryResponse,
    CreditProductCreate,
    CreditProductUpdate,
    CreditProductResponse,
    ProductScoreRangeCreate,
    ProductScoreRangeUpdate,
    ProductScoreRangeResponse,
    ProductFeeCreate,
    ProductFeeUpdate,
    ProductFeeResponse,
)
from app.services.decision_engine.rules import RULES_REGISTRY, DEFAULT_RULES
from app.services.rule_generator import generate_rule, ALLOWED_FIELDS

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Pydantic schemas for rules endpoints ─────────────────────────────────

class RuleEntry(BaseModel):
    rule_id: str
    name: str
    description: str
    field: str
    operator: str
    threshold: Any = None
    outcome: str
    severity: str
    type: str = "threshold"
    is_custom: bool = False
    enabled: bool = True


class RulesConfigResponse(BaseModel):
    version: int
    name: str
    rules: list[RuleEntry]
    allowed_fields: dict[str, Any]


class RulesUpdateRequest(BaseModel):
    rules: list[RuleEntry]


class RuleGenerateRequest(BaseModel):
    prompt: str = Field(min_length=5)
    conversation_history: Optional[list[dict]] = None


class RuleGenerateResponse(BaseModel):
    status: str
    questions: Optional[list[str]] = None
    refusal_reason: Optional[str] = None
    rule: Optional[dict] = None
    explanation: Optional[str] = None


# ── Rules management endpoints (admin-only) ──────────────────────────────

@router.get("/rules", response_model=RulesConfigResponse)
async def get_rules(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Return the current active rules config."""
    # Load latest active config from DB
    result = await db.execute(
        select(DecisionRulesConfig)
        .where(DecisionRulesConfig.is_active == True)
        .order_by(desc(DecisionRulesConfig.version))
        .limit(1)
    )
    db_config = result.scalar_one_or_none()

    # Start from defaults
    registry = {k: dict(v) for k, v in RULES_REGISTRY.items()}

    # Overlay DB overrides
    if db_config and db_config.rules:
        saved_registry = db_config.rules.get("rules_registry")
        if saved_registry and isinstance(saved_registry, dict):
            for rid, overrides in saved_registry.items():
                if rid in registry:
                    registry[rid].update(overrides)
                else:
                    registry[rid] = overrides

    version = db_config.version if db_config else DEFAULT_RULES["version"]
    name = db_config.name if db_config else DEFAULT_RULES["name"]

    rules_list = []
    for rule_id in sorted(registry.keys()):
        r = registry[rule_id]
        rules_list.append(RuleEntry(
            rule_id=rule_id,
            name=r.get("name", rule_id),
            description=r.get("description", ""),
            field=r.get("field", ""),
            operator=r.get("operator", ""),
            threshold=r.get("threshold"),
            outcome=r.get("outcome", "decline"),
            severity=r.get("severity", "hard"),
            type=r.get("type", "threshold"),
            is_custom=r.get("is_custom", False),
            enabled=r.get("enabled", True),
        ))

    return RulesConfigResponse(
        version=version,
        name=name,
        rules=rules_list,
        allowed_fields=ALLOWED_FIELDS,
    )


@router.put("/rules")
async def update_rules(
    body: RulesUpdateRequest,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Save updated rules config. Creates a new version."""
    # Get current latest version
    result = await db.execute(
        select(DecisionRulesConfig)
        .where(DecisionRulesConfig.is_active == True)
        .order_by(desc(DecisionRulesConfig.version))
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    new_version = (existing.version + 1) if existing else (DEFAULT_RULES["version"] + 1)

    # Build registry dict from the rules list
    registry: dict[str, dict] = {}
    for rule in body.rules:
        registry[rule.rule_id] = {
            "name": rule.name,
            "description": rule.description,
            "field": rule.field,
            "operator": rule.operator,
            "threshold": rule.threshold,
            "outcome": rule.outcome,
            "severity": rule.severity,
            "type": rule.type,
            "is_custom": rule.is_custom,
            "enabled": rule.enabled,
        }

    # Build full config (keep legacy structure + new registry)
    full_config = dict(DEFAULT_RULES)
    full_config["rules_registry"] = registry

    # Mark old configs as inactive
    if existing:
        existing.is_active = False

    # Create new version
    new_config = DecisionRulesConfig(
        version=new_version,
        name=f"Rules v{new_version}",
        rules=full_config,
        is_active=True,
        created_by=current_user.id,
    )
    db.add(new_config)
    await db.flush()

    return {"message": "Rules saved", "version": new_version}


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Delete a custom rule from the config."""
    # Only allow deleting custom rules
    if rule_id in RULES_REGISTRY and not RULES_REGISTRY[rule_id].get("is_custom", False):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete built-in rules. Disable them instead.",
        )

    # Load current config
    result = await db.execute(
        select(DecisionRulesConfig)
        .where(DecisionRulesConfig.is_active == True)
        .order_by(desc(DecisionRulesConfig.version))
        .limit(1)
    )
    existing = result.scalar_one_or_none()

    if not existing or not existing.rules:
        raise HTTPException(status_code=404, detail="No active rules config found")

    saved_registry = existing.rules.get("rules_registry", {})
    if not saved_registry or rule_id not in saved_registry:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found in config")

    # Remove the rule
    del saved_registry[rule_id]

    # Create new version
    new_version = existing.version + 1
    full_config = dict(existing.rules)
    full_config["rules_registry"] = saved_registry

    existing.is_active = False

    new_config = DecisionRulesConfig(
        version=new_version,
        name=f"Rules v{new_version}",
        rules=full_config,
        is_active=True,
        created_by=current_user.id,
    )
    db.add(new_config)
    await db.flush()

    return {"message": f"Rule {rule_id} deleted", "version": new_version}


@router.post("/rules/generate", response_model=RuleGenerateResponse)
async def generate_rule_endpoint(
    body: RuleGenerateRequest,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Use AI to generate a rule from a natural-language prompt."""
    result = generate_rule(
        prompt=body.prompt,
        conversation_history=body.conversation_history,
    )
    return RuleGenerateResponse(**result)


def _product_to_response(product: CreditProduct) -> CreditProductResponse:
    return CreditProductResponse(
        id=product.id,
        name=product.name,
        description=product.description,
        merchant_id=product.merchant_id,
        merchant_name=product.merchant.name if product.merchant else None,
        min_term_months=product.min_term_months,
        max_term_months=product.max_term_months,
        min_amount=float(product.min_amount),
        max_amount=float(product.max_amount),
        repayment_scheme=product.repayment_scheme,
        grace_period_days=product.grace_period_days,
        is_active=product.is_active,
        score_ranges=[ProductScoreRangeResponse.model_validate(sr) for sr in product.score_ranges],
        fees=[ProductFeeResponse.model_validate(fee) for fee in product.fees],
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.get("/merchants", response_model=list[MerchantResponse])
async def list_merchants(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Merchant).order_by(Merchant.name))
    return result.scalars().all()


@router.post("/merchants", response_model=MerchantResponse, status_code=status.HTTP_201_CREATED)
async def create_merchant(
    data: MerchantCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    exists = await db.execute(select(Merchant).where(func.lower(Merchant.name) == data.name.lower()))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Merchant with this name already exists")

    merchant = Merchant(name=data.name.strip(), is_active=data.is_active)
    db.add(merchant)
    await db.flush()

    # Every merchant gets an Online branch by default
    online = Branch(
        merchant_id=merchant.id,
        name="Online",
        address="Online",
        is_online=True,
        is_active=True,
    )
    db.add(online)
    await db.flush()
    await db.refresh(merchant)
    return merchant


@router.put("/merchants/{merchant_id}", response_model=MerchantResponse)
async def update_merchant(
    merchant_id: int,
    data: MerchantUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
    merchant = result.scalar_one_or_none()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    if data.name is not None:
        merchant.name = data.name.strip()
    if data.is_active is not None:
        merchant.is_active = data.is_active

    await db.flush()
    await db.refresh(merchant)
    return merchant


@router.delete("/merchants/{merchant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_merchant(
    merchant_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
    merchant = result.scalar_one_or_none()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    await db.delete(merchant)
    await db.flush()
    return None


@router.get("/merchants/{merchant_id}/branches", response_model=list[BranchResponse])
async def list_branches(
    merchant_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Branch).where(Branch.merchant_id == merchant_id).order_by(Branch.is_online.desc(), Branch.name)
    )
    return result.scalars().all()


@router.post("/merchants/{merchant_id}/branches", response_model=BranchResponse, status_code=status.HTTP_201_CREATED)
async def create_branch(
    merchant_id: int,
    data: BranchCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    m = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
    if not m.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Merchant not found")

    branch = Branch(
        merchant_id=merchant_id,
        name=data.name.strip(),
        address=data.address,
        is_online=data.is_online,
        is_active=data.is_active,
    )
    db.add(branch)
    await db.flush()
    await db.refresh(branch)
    return branch


@router.put("/branches/{branch_id}", response_model=BranchResponse)
async def update_branch(
    branch_id: int,
    data: BranchUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Branch).where(Branch.id == branch_id))
    branch = result.scalar_one_or_none()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(branch, field, value)

    await db.flush()
    await db.refresh(branch)
    return branch


@router.delete("/branches/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_branch(
    branch_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Branch).where(Branch.id == branch_id))
    branch = result.scalar_one_or_none()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    await db.delete(branch)
    await db.flush()
    return None


@router.get("/merchants/{merchant_id}/categories", response_model=list[ProductCategoryResponse])
async def list_categories(
    merchant_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    m = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
    if not m.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Merchant not found")
    result = await db.execute(
        select(ProductCategory).where(ProductCategory.merchant_id == merchant_id).order_by(ProductCategory.name)
    )
    return result.scalars().all()


@router.post("/merchants/{merchant_id}/categories", response_model=ProductCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    merchant_id: int,
    data: ProductCategoryCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    m = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
    if not m.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Merchant not found")
    exists = await db.execute(
        select(ProductCategory).where(
            ProductCategory.merchant_id == merchant_id,
            func.lower(ProductCategory.name) == data.name.strip().lower(),
        )
    )
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Category with this name already exists for merchant")
    category = ProductCategory(merchant_id=merchant_id, name=data.name.strip())
    db.add(category)
    await db.flush()
    await db.refresh(category)
    return category


@router.put("/categories/{category_id}", response_model=ProductCategoryResponse)
async def update_category(
    category_id: int,
    data: ProductCategoryUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ProductCategory).where(ProductCategory.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    category.name = data.name.strip()
    await db.flush()
    await db.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ProductCategory).where(ProductCategory.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    await db.delete(category)
    await db.flush()
    return None


@router.get("/products", response_model=list[CreditProductResponse])
async def list_products(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CreditProduct)
        .options(
            selectinload(CreditProduct.score_ranges),
            selectinload(CreditProduct.fees),
            selectinload(CreditProduct.merchant),
        )
        .order_by(CreditProduct.created_at.desc())
    )
    return [_product_to_response(p) for p in result.scalars().unique().all()]


@router.get("/products/{product_id}", response_model=CreditProductResponse)
async def get_product(
    product_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CreditProduct)
        .where(CreditProduct.id == product_id)
        .options(
            selectinload(CreditProduct.score_ranges),
            selectinload(CreditProduct.fees),
            selectinload(CreditProduct.merchant),
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return _product_to_response(product)


@router.post("/products", response_model=CreditProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: CreditProductCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    product = CreditProduct(
        name=data.name.strip(),
        description=data.description,
        merchant_id=data.merchant_id,
        min_term_months=data.min_term_months,
        max_term_months=data.max_term_months,
        min_amount=data.min_amount,
        max_amount=data.max_amount,
        repayment_scheme=data.repayment_scheme,
        grace_period_days=data.grace_period_days,
        is_active=data.is_active,
    )
    db.add(product)
    await db.flush()

    for sr in data.score_ranges:
        db.add(ProductScoreRange(credit_product_id=product.id, min_score=sr.min_score, max_score=sr.max_score))
    for fee in data.fees:
        db.add(
            ProductFee(
                credit_product_id=product.id,
                fee_type=fee.fee_type,
                fee_base=fee.fee_base,
                fee_amount=fee.fee_amount,
                is_available=fee.is_available,
            )
        )
    await db.flush()
    return await get_product(product.id, current_user, db)


@router.put("/products/{product_id}", response_model=CreditProductResponse)
async def update_product(
    product_id: int,
    data: CreditProductUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CreditProduct).where(CreditProduct.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    await db.flush()
    return await get_product(product_id, current_user, db)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CreditProduct).where(CreditProduct.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    await db.delete(product)
    await db.flush()
    return None


@router.post("/products/{product_id}/score-ranges", response_model=ProductScoreRangeResponse, status_code=status.HTTP_201_CREATED)
async def create_score_range(
    product_id: int,
    data: ProductScoreRangeCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    item = ProductScoreRange(credit_product_id=product_id, min_score=data.min_score, max_score=data.max_score)
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


@router.put("/score-ranges/{score_range_id}", response_model=ProductScoreRangeResponse)
async def update_score_range(
    score_range_id: int,
    data: ProductScoreRangeUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ProductScoreRange).where(ProductScoreRange.id == score_range_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Score range not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await db.flush()
    await db.refresh(item)
    return item


@router.delete("/score-ranges/{score_range_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_score_range(
    score_range_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ProductScoreRange).where(ProductScoreRange.id == score_range_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Score range not found")
    await db.delete(item)
    await db.flush()
    return None


@router.post("/products/{product_id}/fees", response_model=ProductFeeResponse, status_code=status.HTTP_201_CREATED)
async def create_fee(
    product_id: int,
    data: ProductFeeCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    fee = ProductFee(
        credit_product_id=product_id,
        fee_type=data.fee_type,
        fee_base=data.fee_base,
        fee_amount=data.fee_amount,
        is_available=data.is_available,
    )
    db.add(fee)
    await db.flush()
    await db.refresh(fee)
    return fee


@router.put("/fees/{fee_id}", response_model=ProductFeeResponse)
async def update_fee(
    fee_id: int,
    data: ProductFeeUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ProductFee).where(ProductFee.id == fee_id))
    fee = result.scalar_one_or_none()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(fee, field, value)
    await db.flush()
    await db.refresh(fee)
    return fee


@router.delete("/fees/{fee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fee(
    fee_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ProductFee).where(ProductFee.id == fee_id))
    fee = result.scalar_one_or_none()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")
    await db.delete(fee)
    await db.flush()
    return None
