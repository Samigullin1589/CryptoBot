import json
from types import SimpleNamespace
from pathlib import Path
from datetime import datetime, timezone

import pytest
import pytest_asyncio
import fakeredis.aioredis

from bot.services.achievement_service import AchievementService
from bot.config.settings import AchievementServiceConfig


class DummyMarketDataService:
    async def get_top_coins_by_market_cap(self):
        return [
            {
                "id": "bitcoin",
                "name": "Bitcoin",
                "ath": 50000,
                "current_price": 60000,
                "price_change_percentage_24h": 30,
            }
        ]


@pytest_asyncio.fixture
async def redis():
    r = fakeredis.aioredis.FakeRedis()
    await r.flushall()
    yield r
    await r.flushall()
    await r.close()


@pytest.fixture
def achievement_service(redis):
    config = AchievementServiceConfig(config_path=str(Path("data/achievements.json")))
    return AchievementService(redis, config, DummyMarketDataService())


@pytest.mark.asyncio
async def test_load_achievements(achievement_service):
    all_ach = await achievement_service.get_all_achievements()
    assert len(achievement_service.static_achievements) == 3
    assert len(achievement_service.dynamic_achievements) == 3
    assert len(all_ach) == 6


@pytest.mark.asyncio
async def test_process_static_event_awards_and_no_duplicates(redis, achievement_service):
    user_id = 1
    # first session should unlock first achievement
    first = await achievement_service.process_static_event(user_id, "session_completed")
    assert first and first.id == "static_first_session"

    # increment counter up to 9 (total 10 with next call)
    for _ in range(8):
        await achievement_service.process_static_event(user_id, "session_completed")

    second = await achievement_service.process_static_event(user_id, "session_completed")
    assert second and second.id == "static_ten_sessions"

    # additional call should not unlock anything
    none = await achievement_service.process_static_event(user_id, "session_completed")
    assert none is None

    balance = await redis.hget(achievement_service.keys.user_game_profile(user_id), "balance")
    assert float(balance) == 600  # 100 + 500


@pytest.mark.asyncio
async def test_check_market_events(redis, achievement_service):
    user_id = 42
    unlocked = await achievement_service.check_market_events(user_id)
    ids = {a.id for a in unlocked}
    assert ids == {"dynamic_witness_ath", "dynamic_pump_rider"}

    # second run should not duplicate
    unlocked_again = await achievement_service.check_market_events(user_id)
    assert unlocked_again == []

    user_ach = await achievement_service.get_user_achievements(user_id)
    assert len(user_ach) == 2
