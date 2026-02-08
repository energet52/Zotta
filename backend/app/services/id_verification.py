"""ID verification service with adapter pattern.

Uses a mock verifier for the prototype; real providers
(Onfido, Jumio, or a local provider) can be swapped via config.
"""

import hashlib
import random
from typing import Dict, Any

from app.config import settings


async def verify_identity(
    national_id: str,
    document_type: str,
    document_path: str,
) -> Dict[str, Any]:
    """Verify an applicant's identity document.

    Args:
        national_id: The applicant's national ID number.
        document_type: Type of document (national_id, passport, drivers_license).
        document_path: Path to the uploaded document image.

    Returns:
        Dict with status, verified (bool), details, and message.
    """
    provider = settings.id_verification_provider.lower()

    if provider == "mock":
        return await _mock_verify(national_id, document_type, document_path)
    else:
        raise NotImplementedError(f"Verification provider '{provider}' not implemented")


async def _mock_verify(
    national_id: str,
    document_type: str,
    document_path: str,
) -> Dict[str, Any]:
    """Mock ID verification for development.

    Deterministically produces a result based on the national ID,
    so the same ID always gets the same outcome.
    """
    # Deterministic based on national ID
    hash_val = int(hashlib.md5(national_id.encode()).hexdigest(), 16)
    rng = random.Random(hash_val)

    # Validate document type
    valid_types = ["national_id", "passport", "drivers_license"]
    if document_type not in valid_types:
        return {
            "status": "failed",
            "verified": False,
            "message": f"Invalid document type. Must be one of: {', '.join(valid_types)}",
        }

    # Validate national ID format (Trinidad: typically 19XXXXXXX or similar)
    if len(national_id) < 5:
        return {
            "status": "failed",
            "verified": False,
            "message": "National ID format appears invalid. Please check and retry.",
        }

    # Simulate verification outcomes
    outcome = rng.random()

    if outcome < 0.80:
        # 80% success rate
        return {
            "status": "verified",
            "verified": True,
            "details": {
                "document_type": document_type,
                "id_number_match": True,
                "face_match_score": round(rng.uniform(0.85, 0.99), 3),
                "document_quality": "good",
                "expiry_valid": True,
            },
            "message": "Identity verified successfully.",
        }
    elif outcome < 0.95:
        # 15% needs manual review
        return {
            "status": "manual_review",
            "verified": False,
            "details": {
                "document_type": document_type,
                "id_number_match": True,
                "face_match_score": round(rng.uniform(0.5, 0.84), 3),
                "document_quality": "fair",
                "reason": "Face match score below threshold - needs manual review",
            },
            "message": "Verification requires manual review. An underwriter will review your documents.",
        }
    else:
        # 5% failure
        return {
            "status": "failed",
            "verified": False,
            "details": {
                "document_type": document_type,
                "reason": "Document appears altered or unreadable",
            },
            "message": "Verification failed. Please upload a clear, unaltered document.",
        }
