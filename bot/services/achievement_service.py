# =================================================================================
# Файл: bot/services/achievement_service.py (ВЕРСЯ "Distinguished Engineer" - ДИНАМИЧЕСКАЯ)
# Описание: Управляемый событиями сервис для динамической системы достижений,
# интегрированный с рыночными данными в реальном времени.
# ИСПРАВЛЕНИЕ: Добавлена проверка контекста для предотвращения повторной выдачи динамических достижений.
# =================================================================================

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
import yaml

from bot.config.settings import AchievementServiceConfig
from bot.services.market_data_service import MarketDataService
from bot.utils.keys import KeyFactory
from bot.utils.models import Achievement

logger = logging.getLogger(__name__)

class AchievementService:
    """Сервис, управляющий логикой получения статических и динамических достижений."""

    def __init__(self, redis: redis.Redis, config: AchievementServiceConfig, market_data_service: MarketDataService):
        self.redis = redis
        self.config = config
        self.market_data_service = market_data_service
        self.keys = KeyFactory
        self.static_achievements: Dict[str, Achievement] = {}
        self.dynamic_achievements: Dict[str, Achievement] = {}
        self._load_achievements_from_config(Path(self.config.config_path))

    def _load_achievements_from_config(self, config_path: Path) -> None:
        """Загружает и разделяет достижения на статические и динамические."""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                if config_path.suffix in {".yaml", ".yml"}:
                    data = yaml.safe_load(f) or {}
                else:
                    data = json.load(f)

            for ach_data in data.get("achievements", []):
                ach_data.setdefault("type", "static")
                achievement = Achievement(**ach_data)
                if achievement.type == "static":
                    self.static_achievements[achievement.id] = achievement
                elif achievement.type == "dynamic":
                    self.dynamic_achievements[achievement.id] = achievement

            logger.info(
                "Загружено %s статических и %s динамических достижений.",
                len(self.static_achievements),
                len(self.dynamic_achievements),
            )
        except FileNotFoundError:
            logger.error("Файл конфигурации достижений не найден: %s", config_path)
        except Exception as e:
            logger.error("Критическая ошибка при загрузке достижений: %s", e, exc_info=True)

    async def get_all_achievements(self) -> List[Achievement]:
        """Возвращает полный список всех достижений."""
        return list(self.static_achievements.values()) + list(self.dynamic_achievements.values())

    async def get_user_achievements(self, user_id: int) -> List[Dict[str, Any]]:
        """Возвращает список разблокированных пользователем достижений с их описаниями."""
        unlocked_data = await self.redis.hgetall(self.keys.user_achievements(user_id))
        return [json.loads(data) for data in unlocked_data.values()]

    async def _unlock_achievement(self, user_id: int, achievement: Achievement, context: Dict = None) -> Optional[Achievement]:
        """Атомарно выдает достижение, форматируя описание с контекстом, и начисляет награду."""
        if context is None:
            context = {}
        
        # ИСПРАВЛЕНО: instance_id теперь включает контекст (ID монеты) для уникальности
        instance_id = f"{achievement.id}:{context.get('coin_id', 'global')}"
        
        if await self.redis.hget(self.keys.user_achievements(user_id), instance_id):
            return None # Достижение с этим контекстом уже выдано

        formatted_description = achievement.description.format(**context)
        
        unlocked_achievement = achievement.model_copy(deep=True)
        unlocked_achievement.description = formatted_description
        
        achievement_data_to_store = {
            "id": unlocked_achievement.id,
            "name": unlocked_achievement.name,
            "description": unlocked_achievement.description,
            "reward_coins": unlocked_achievement.reward_coins
        }

        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hset(self.keys.user_achievements(user_id), instance_id, json.dumps(achievement_data_to_store, ensure_ascii=False))
            pipe.hincrbyfloat(self.keys.user_game_profile(user_id), "balance", achievement.reward_coins)
            await pipe.execute()
        logger.info(f"Пользователь {user_id} разблокировал достижение '{achievement.name}' ({formatted_description})")
        return unlocked_achievement

    async def check_market_events(self, user_id: int) -> List[Achievement]:
        """
        Проверяет рыночные данные и выдает динамические достижения.
        """
        unlocked = []
        top_coins = await self.market_data_service.get_top_coins_by_market_cap()
        if not top_coins:
            return unlocked

        for i, coin in enumerate(top_coins[:30]):
            coin_id = coin.get('id')
            coin_name = coin.get('name')
            
            if coin.get('ath') and coin.get('current_price') and coin.get('current_price') >= coin.get('ath'):
                if ach := self.dynamic_achievements.get("dynamic_witness_ath"):
                    if unlocked_ach := await self._unlock_achievement(user_id, ach, context={"coin_name": coin_name, "coin_id": coin_id}):
                        unlocked.append(unlocked_ach)
            
            price_change = coin.get('price_change_percentage_24h')
            if price_change and price_change > 25:
                 if ach := self.dynamic_achievements.get("dynamic_pump_rider"):
                    if unlocked_ach := await self._unlock_achievement(user_id, ach, context={"coin_name": coin_name, "coin_id": coin_id}):
                        unlocked.append(unlocked_ach)

        return unlocked

    async def process_static_event(self, user_id: int, event_name: str, event_data: Dict[str, Any] = None) -> Optional[Achievement]:
        """Обрабатывает статические события, такие как завершение сессии."""
        if event_data is None:
            event_data = {}
        
        counters_key = self.keys.user_event_counters(user_id)
        current_count = await self.redis.hincrby(counters_key, f"{event_name}_count", 1)

        unlocked_ids_raw = await self.redis.hkeys(self.keys.user_achievements(user_id))
        unlocked_ids = {uid.decode('utf-8').split(':')[0] for uid in unlocked_ids_raw}
        
        for ach_id, achievement in self.static_achievements.items():
            if ach_id not in unlocked_ids and achievement.trigger_event == event_name:
                conditions_met = True
                if achievement.trigger_conditions:
                    for key, required_value in achievement.trigger_conditions.items():
                        if key == f"{event_name}_count" and current_count < required_value:
                            conditions_met = False
                            break
                        if key in event_data and event_data[key] != required_value:
                            conditions_met = False
                            break
                
                if conditions_met:
                    return await self._unlock_achievement(user_id, achievement)
        return None
