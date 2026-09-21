"""Onboarding domain, free of frameworks: plain-dataclass entities, the eligibility and pricing rules,
and the ports (`onboarding_core.ports`) that the persistence and gateway adapters implement.

Nothing here imports SQLAlchemy, LangGraph or FastAPI. The backend maps the entities onto its tables
(`app/db/models.py`); the agent reads and writes them through `ports.UnitOfWork`."""
