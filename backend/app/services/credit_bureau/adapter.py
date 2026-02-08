"""Abstract credit bureau adapter and factory."""

from abc import ABC, abstractmethod
from typing import Dict, Any

from app.config import settings


class CreditBureauAdapter(ABC):
    """Abstract interface for credit bureau integrations."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the credit bureau provider."""
        ...

    @abstractmethod
    async def pull_credit_report(self, national_id: str) -> Dict[str, Any]:
        """Pull a credit report for the given national ID.

        Returns a dict containing at minimum:
        - score: int (bureau credit score)
        - payment_history_score: float (0-1)
        - total_outstanding_debt: float
        - num_inquiries: int
        - credit_history_years: float
        - tradelines: list of dicts
        - inquiries: list of dicts
        - public_records: list of dicts
        """
        ...

    @abstractmethod
    async def check_health(self) -> bool:
        """Check if the bureau API is reachable."""
        ...


def get_credit_bureau() -> CreditBureauAdapter:
    """Factory function that returns the configured credit bureau adapter."""
    provider = settings.credit_bureau_provider.lower()

    if provider == "av_knowles":
        from app.services.credit_bureau.av_knowles import AVKnowlesAdapter
        return AVKnowlesAdapter()
    else:
        from app.services.credit_bureau.mock_bureau import MockBureauAdapter
        return MockBureauAdapter()
