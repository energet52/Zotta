"""AV Knowles credit bureau adapter stub for Trinidad and Tobago.

This is a placeholder implementation ready to be connected to the
real AV Knowles API when credentials and documentation become available.
"""

from typing import Dict, Any

import httpx

from app.config import settings
from app.services.credit_bureau.adapter import CreditBureauAdapter


class AVKnowlesAdapter(CreditBureauAdapter):
    """AV Knowles credit bureau integration for Trinidad & Tobago.

    TODO: Replace stub methods with actual API calls once API documentation
    and credentials are obtained from AV Knowles.

    Expected API pattern (to be confirmed):
    - Base URL: https://api.avknowles.com/v1
    - Auth: API key in header
    - Endpoint: POST /credit-report
    - Request: { "national_id": "...", "consent": true }
    - Response: { "score": int, "tradelines": [...], ... }
    """

    def __init__(self):
        self.base_url = settings.av_knowles_api_url
        self.api_key = settings.av_knowles_api_key

    @property
    def provider_name(self) -> str:
        return "av_knowles"

    async def pull_credit_report(self, national_id: str) -> Dict[str, Any]:
        """Pull credit report from AV Knowles API.

        Currently raises NotImplementedError - to be implemented
        when API credentials are available.
        """
        if not self.base_url or not self.api_key:
            raise NotImplementedError(
                "AV Knowles API credentials not configured. "
                "Set AV_KNOWLES_API_URL and AV_KNOWLES_API_KEY in .env"
            )

        # Placeholder for actual API call
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/credit-report",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "national_id": national_id,
                    "consent": True,
                    "report_type": "full",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        # Transform AV Knowles response to standard format
        # TODO: Map actual response fields when API docs are available
        return {
            "score": data.get("credit_score", 0),
            "payment_history_score": data.get("payment_history_pct", 0) / 100,
            "total_outstanding_debt": data.get("total_debt", 0),
            "num_inquiries": data.get("inquiry_count", 0),
            "credit_history_years": data.get("oldest_account_years", 0),
            "tradelines": data.get("tradelines", []),
            "inquiries": data.get("inquiries", []),
            "public_records": data.get("public_records", []),
            "raw_response": data,
        }

    async def check_health(self) -> bool:
        """Check if AV Knowles API is reachable."""
        if not self.base_url:
            return False
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/health",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=5.0,
                )
                return response.status_code == 200
        except Exception:
            return False
