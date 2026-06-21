"""Schema-portability spike — resolves RESEARCH.md Open Question 1 /
Assumption A1 empirically: does SQLAlchemy's `schema_translate_map`
execution option let an in-memory SQLite test engine stand in for
Postgres's real multi-schema (`device_identity.*`, `traffic.*`,
`security.*`, `devices.*`) layout used in production?

Not a permanent test file (RESEARCH.md explicitly calls this out) — it is a
standalone, throwaway, pytest-collectible script proving (or disproving)
the strategy Plan 03/04/05's conftest.py fixtures will rely on. Run either
via `python tests/schema_portability_spike.py` or
`pytest tests/schema_portability_spike.py -x -s`.
"""

import asyncio

from sqlalchemy import Column, Integer, String, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase


class SpikeBase(DeclarativeBase):
    pass


class SpikeA(SpikeBase):
    __tablename__ = "spike_a_table"
    __table_args__ = {"schema": "spike_a"}

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    value: str = Column(String(50))


class SpikeB(SpikeBase):
    __tablename__ = "spike_b_table"
    __table_args__ = {"schema": "spike_b"}

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    value: str = Column(String(50))


async def _run_spike() -> bool:
    """Returns True if schema_translate_map worked end-to-end for both
    schemas simultaneously against in-memory SQLite, False otherwise."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        execution_options={
            "schema_translate_map": {
                "spike_a": None,
                "spike_b": None,
            }
        },
    )

    try:
        async with engine.begin() as conn:
            await conn.run_sync(SpikeBase.metadata.create_all)

        async with engine.begin() as conn:
            await conn.execute(SpikeA.__table__.insert().values(value="from-a"))
            await conn.execute(SpikeB.__table__.insert().values(value="from-b"))

        async with engine.connect() as conn:
            result_a = (await conn.execute(select(SpikeA.__table__.c.value))).scalar_one()
            result_b = (await conn.execute(select(SpikeB.__table__.c.value))).scalar_one()

        return result_a == "from-a" and result_b == "from-b"
    finally:
        await engine.dispose()


def test_schema_translate_map_resolves_open_question_1():
    """pytest entry point — also runnable as a standalone script via main()."""
    passed = asyncio.run(_run_spike())
    if passed:
        print(
            "PASS: schema_translate_map successfully maps two distinct declared "
            "Postgres-style schemas (spike_a, spike_b) onto a single in-memory "
            "SQLite database, both round-tripping independent rows correctly. "
            "RESEARCH.md Open Question 1 / Assumption A1 is CONFIRMED — Plan "
            "03/04/05's conftest.py fixtures should use schema_translate_map "
            "(mapping each module's real schema name to None) for the SQLite "
            "test engine, while Postgres production keeps real schema names."
        )
    else:
        print(
            "FAIL: schema_translate_map did NOT round-trip both schemas "
            "correctly against in-memory SQLite. RESEARCH.md Open Question 1 "
            "/ Assumption A1 is REFUTED for this project's environment — "
            "Plan 03 must fall back to one of RESEARCH.md Pitfall 1's other "
            "options (multi-attach SQLite databases, or a real test-Postgres "
            "instance via testcontainers) instead of schema_translate_map."
        )
    assert passed


if __name__ == "__main__":
    test_schema_translate_map_resolves_open_question_1()
