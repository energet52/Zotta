"""Celery tasks for decision engine processing."""

import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.tasks import celery_app
from app.config import settings


def get_async_session():
    engine = create_async_engine(settings.database_url)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@celery_app.task(name="run_decision_engine_task")
def run_decision_engine_task(application_id: int):
    """Run the decision engine for a loan application asynchronously."""
    from app.services.decision_engine.engine import run_decision_engine

    async def _run():
        session_factory = get_async_session()
        async with session_factory() as session:
            try:
                decision = await run_decision_engine(application_id, session)
                await session.commit()
                return {
                    "application_id": application_id,
                    "score": decision.credit_score,
                    "outcome": decision.final_outcome,
                }
            except Exception as e:
                await session.rollback()
                raise

    return asyncio.get_event_loop().run_until_complete(_run())
