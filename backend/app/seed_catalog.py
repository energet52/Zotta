"""Seed data for hire-purchase catalog."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import (
    Merchant,
    Branch,
    ProductCategory,
    CreditProduct,
    ProductScoreRange,
    ProductFee,
)


# Merchant-specific categories based on actual product offerings
# Ramlagans: furniture, appliances, electronics (ramlagansholdings.com)
MERCHANT_CATEGORIES = {
    "Ramlagans Super Store": [
        "Stove",
        "Refrigerator",
        "Washing Machine",
        "Microwave",
        "Air Conditioner",
        "Bedroom Furniture",
        "Living Room Furniture",
        "Dining Room Furniture",
        "Office Furniture",
        "TV Stands & Entertainment",
        "Mattress & Bed Base",
        "Small Kitchen Appliances",
        "Fans & Cooling",
        "Vacuum & Floor Care",
        "Electronics",
        "Other",
    ],
    # SAI Appliances & Furniture: home furnishings, appliances (Sangre Grande)
    "SAI": [
        "Refrigerator",
        "Stove",
        "Washing Machine",
        "Sofa & Living Room",
        "Dining Set",
        "Bedroom Set",
        "Kitchen Appliances",
        "Home Technology",
        "Home Decor",
        "Air Conditioner",
        "Mattress",
        "Other",
    ],
    # ZWSSL: security systems, surveillance (security retail)
    "Zone Watch Security Services (ZWSSL)": [
        "CCTV Cameras",
        "Alarm Systems",
        "Access Control",
        "Surveillance Systems",
        "Security Sensors",
        "Monitoring Equipment",
        "Auto Security",
        "Security Installation",
        "Other",
    ],
    # Value Optical: eyeglasses, contact lenses (valueoptical.com)
    "Value Optical": [
        "Eyeglasses",
        "Contact Lenses",
        "Sunglasses",
        "Designer Frames",
        "Reading Glasses",
        "Prescription Lenses",
        "Eye Care Accessories",
        "Other",
    ],
}

MERCHANT_BRANCHES = {
    "Ramlagans Super Store": ["Chaguanas", "San Fernando", "Balmain", "Online"],
    "SAI": ["Brydens", "Port of Spain", "Online"],
    "Zone Watch Security Services (ZWSSL)": ["Kingston", "Online"],
    "Value Optical": ["Port of Spain", "Online"],
}

PRODUCTS = [
    ("ZWSSL's 24 over $2,000", "Minimum term: 6 months Maximum: 24 months", "Zone Watch Security Services (ZWSSL)", 6, 24, 2000, 25000),
    ("SAI's 36 over $2,999", "SAI's 36 over $2,999", "SAI", 6, 36, 3000, 30000),
    ("SAI's 24 up to $2,999", "SAI's 24 up to $2,999", "SAI", 6, 24, 2000, 2999),
    ("SAI's 30 over $2,999 Non Brydens", "SAI's 30 over $2,999 Non Brydens", "SAI", 6, 30, 3000, 30000),
    ("Ramlagan's 36 for over 2,999", "Ramlagan's 36 for over 2,999", "Ramlagans Super Store", 6, 36, 3000, 30000),
    ("Ramlagan's 24 up to 2,999", "Ramlagan's 24 up to 2,999", "Ramlagans Super Store", 6, 24, 2000, 2999),
    ("Ramlagan's 30 for over 2,999 Non-Brydens", "Ramlagan's 30 for over 2,999 Non-Brydens", "Ramlagans Super Store", 6, 30, 3000, 30000),
    ("Affordable 15, 18, 24 Plan", "15 month, 18 month or 24 month affordable plan", "Value Optical", 15, 24, 1500, 25000),
    ("Value 6 or 12", "6 month or 12 month flexible credit", "Value Optical", 6, 12, 2500, 25000),
]


async def _get_or_create_merchant(db: AsyncSession, name: str) -> Merchant:
    res = await db.execute(select(Merchant).where(Merchant.name == name))
    merchant = res.scalar_one_or_none()
    if merchant:
        return merchant
    merchant = Merchant(name=name, is_active=True)
    db.add(merchant)
    await db.flush()
    return merchant


async def _ensure_branch(db: AsyncSession, merchant_id: int, name: str) -> None:
    res = await db.execute(
        select(Branch).where(Branch.merchant_id == merchant_id, Branch.name == name)
    )
    if res.scalar_one_or_none():
        return
    db.add(
        Branch(
            merchant_id=merchant_id,
            name=name,
            address=name,
            is_online=name.lower() == "online",
            is_active=True,
        )
    )
    await db.flush()


async def _ensure_category(db: AsyncSession, merchant_id: int, name: str) -> None:
    res = await db.execute(
        select(ProductCategory).where(
            ProductCategory.merchant_id == merchant_id,
            ProductCategory.name == name,
        )
    )
    if res.scalar_one_or_none():
        return
    db.add(ProductCategory(merchant_id=merchant_id, name=name))
    await db.flush()


async def _ensure_product(
    db: AsyncSession,
    name: str,
    description: str,
    merchant_id: int,
    min_term: int,
    max_term: int,
    min_amount: float,
    max_amount: float,
) -> None:
    res = await db.execute(select(CreditProduct).where(CreditProduct.name == name))
    product = res.scalar_one_or_none()
    if not product:
        product = CreditProduct(
            name=name,
            description=description,
            merchant_id=merchant_id,
            min_term_months=min_term,
            max_term_months=max_term,
            min_amount=min_amount,
            max_amount=max_amount,
            repayment_scheme="Monthly Equal Installment Monthly Actual/365 (Fixed)",
            grace_period_days=0,
            is_active=True,
        )
        db.add(product)
        await db.flush()

    sr = await db.execute(select(ProductScoreRange).where(ProductScoreRange.credit_product_id == product.id))
    if not sr.scalar_one_or_none():
        db.add(ProductScoreRange(credit_product_id=product.id, min_score=300, max_score=850))

    existing_fees = await db.execute(select(ProductFee).where(ProductFee.credit_product_id == product.id))
    if not existing_fees.scalars().first():
        defaults = [
            ("admin_fee_pct", "purchase_amount", 0.00),
            ("credit_fee_pct", "financed_amount", 0.03),
            ("origination_fee_pct", "purchase_amount", 0.01),
            ("origination_fee_flat", "flat", 10.00),
            ("late_payment_fee_flat", "flat", 5.00),
        ]
        for fee_type, fee_base, fee_amount in defaults:
            db.add(
                ProductFee(
                    credit_product_id=product.id,
                    fee_type=fee_type,
                    fee_base=fee_base,
                    fee_amount=fee_amount,
                    is_available=True,
                )
            )
    await db.flush()


async def seed_catalog_data(db: AsyncSession) -> None:
    """Idempotently seed catalog data."""
    merchant_map: dict[str, Merchant] = {}
    for merchant_name in MERCHANT_BRANCHES.keys():
        merchant_map[merchant_name] = await _get_or_create_merchant(db, merchant_name)

    for merchant_name, branch_names in MERCHANT_BRANCHES.items():
        merchant = merchant_map[merchant_name]
        for branch_name in branch_names:
            await _ensure_branch(db, merchant.id, branch_name)

    for merchant_name, category_names in MERCHANT_CATEGORIES.items():
        merchant = merchant_map.get(merchant_name)
        if merchant:
            for category_name in category_names:
                await _ensure_category(db, merchant.id, category_name)

    for product in PRODUCTS:
        name, description, merchant_name, min_term, max_term, min_amount, max_amount = product
        merchant = merchant_map[merchant_name]
        await _ensure_product(
            db,
            name,
            description,
            merchant.id,
            min_term,
            max_term,
            min_amount,
            max_amount,
        )

    await db.commit()
