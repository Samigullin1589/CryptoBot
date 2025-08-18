import json
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
import fakeredis.aioredis

from bot.services.event_service import EventService


@pytest_asyncio.fixture
async def redis():
    r = fakeredis.aioredis.FakeRedis()
    await r.flushall()
    yield r
    await r.flushall()
    await r.close()


@pytest.fixture
def event_config(tmp_path):
    now = datetime.now(timezone.utc)
    data = {
        "events": [
            {
                "id": "boost",
                "name": "Boost",
                "domain": "mining",
                "multiplier": 2.0,
                "starts_at": (now - timedelta(hours=1)).isoformat(),
                "ends_at": (now + timedelta(hours=1)).isoformat(),
            },
            {
                "id": "expired",
                "name": "Old",
                "domain": "mining",
                "multiplier": 3.0,
                "starts_at": "2000-01-01T00:00:00Z",
                "ends_at": "2000-01-02T00:00:00Z",
            },
        ]
    }
    path = tmp_path / "events.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return str(path)


@pytest.fixture
def event_service(redis, event_config):
    settings = SimpleNamespace(events=SimpleNamespace(config_path=event_config, default_multiplier=1.0))
    return EventService(settings=settings, redis=redis)


@pytest.mark.asyncio
async def test_load_and_multiplier(event_service):
    events = await event_service.list_events()
    assert {e.id for e in events} == {"boost", "expired"}
    active = await event_service.get_active_events()
    assert len(active) == 1 and active[0].id == "boost"
    mult = await event_service.get_multiplier(domain="mining")
    assert mult == 2.0


@pytest.mark.asyncio
async def test_upsert_and_cancel_event(event_service):
    now = datetime.now(timezone.utc)
    await event_service.upsert_event(
        event_id="custom",
        name="Custom",
        domain="mining",
        multiplier=1.5,
        starts_at=now.isoformat(),
        ends_at=(now + timedelta(hours=1)).isoformat(),
    )
    ids = {e.id for e in await event_service.list_events(include_inactive=False, now=now)}
    assert "custom" in ids
    assert await event_service.cancel_event("custom") is True
    ids_after = {e.id for e in await event_service.list_events()}
    assert "custom" not in ids_after


@pytest.mark.asyncio
async def test_multiplier_unknown_domain(event_service):
    mult = await event_service.get_multiplier(domain="unknown")
    assert mult == 1.0
