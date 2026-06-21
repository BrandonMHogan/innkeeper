from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.bandwidth import BandwidthMetric
from src.modules.device_identity.models import Device, DeviceType
from src.services.bandwidth_anomaly import check_bandwidth_anomaly


async def _seed_device(test_db, mac: str = "11:22:33:44:55:66") -> int:
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        device = Device(
            identity_key="host:bandwidth-device",
            name="Bandwidth Device",
            type=DeviceType.OTHER,
            last_known_mac=mac,
        )
        db.add(device)
        await db.commit()
        await db.refresh(device)
        return device.id


async def _seed_daily_rows(test_db, mac: str, daily_totals: list[float], now=None):
    """Seeds one BandwidthMetric row per entry in daily_totals, oldest first,
    one distinct calendar day apart, ending at `now` (defaults to utcnow)."""
    now = now or datetime.now(timezone.utc)
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        num_days = len(daily_totals)
        for i, total in enumerate(daily_totals):
            days_ago = num_days - 1 - i
            db.add(
                BandwidthMetric(
                    time=now - timedelta(days=days_ago),
                    device_mac=mac,
                    bytes_rx=total / 2,
                    bytes_tx=total / 2,
                )
            )
        await db.commit()


async def test_returns_false_below_minimum_sample_days(test_db):
    mac = "11:22:33:44:55:66"
    device_id = await _seed_device(test_db, mac)
    # Only 3 distinct days — below MIN_SAMPLE_DAYS=7. Most recent reading is huge.
    await _seed_daily_rows(test_db, mac, [100.0, 100.0, 1_000_000.0])

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        result = await check_bandwidth_anomaly(db, device_id)
    assert result is False


async def test_returns_true_on_spike_after_sufficient_history(test_db):
    mac = "11:22:33:44:55:66"
    device_id = await _seed_device(test_db, mac)
    # 7 steady days + 1 spike day (3x+ the rolling average) = 8 distinct days total.
    steady = [100.0] * 7
    spike = [1000.0]
    await _seed_daily_rows(test_db, mac, steady + spike)

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        result = await check_bandwidth_anomaly(db, device_id)
    assert result is True


async def test_returns_false_when_steady(test_db):
    mac = "11:22:33:44:55:66"
    device_id = await _seed_device(test_db, mac)
    # 7 steady days + 1 more steady day in the same range.
    steady = [100.0] * 8
    await _seed_daily_rows(test_db, mac, steady)

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        result = await check_bandwidth_anomaly(db, device_id)
    assert result is False
