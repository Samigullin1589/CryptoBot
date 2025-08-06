# =================================================================================
# Файл: bot/services/achievement_service.py (ВЕРСЯ "Distinguished Engineer" - ДИНАМИЧЕСКАЯ)
# Описание: Управляемый событиями сервис для динамической системы достижений,
# интегрированный с рыночными данными в реальном времени.
# =================================================================================

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

import redis.asyncio as redis

from bot.config.settings import AchievementServiceConfig
from bot.services.market_data_service import MarketDataService
from bot.utils.models import Achievement
from bot.utils.keys import KeyFactory

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

    def _load_achievements_from_config(self, config_path: Path):
        """Загружает и разделяет достижения на статические и динамические."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for ach_data in data.get("achievements", []):
                # Добавляем 'type', если его нет, для обратной совместимости
                if 'type' not in ach_data:
                    ach_data['type'] = 'static'
                achievement = Achievement(**ach_data)
                if achievement.type == "static":
                    self.static_achievements[achievement.id] = achievement
                elif achievement.type == "dynamic":
                    self.dynamic_achievements[achievement.id] = achievement
            logger.info(f"Загружено {len(self.static_achievements)} статических и {len(self.dynamic_achievements)} динамических достижений.")
        except FileNotFoundError:
            logger.error(f"Файл конфигурации достижений не найден: {config_path}")
        except Exception as e:
            logger.error(f"Критическая ошибка при загрузке достижений: {e}", exc_info=True)

    async def get_user_achievements(self, user_id: int) -> List[Dict[str, Any]]:
        """Возвращает список разблокированных пользователем достижений с их описаниями."""
        unlocked_data = await self.redis.hgetall(self.keys.user_achievements(user_id))
        return [json.loads(data) for data in unlocked_data.values()]

    async def _unlock_achievement(self, user_id: int, achievement: Achievement, context: Dict = None) -> Optional[Achievement]:
        """Атомарно выдает достижение, форматируя описание с контекстом, и начисляет награду."""
        if context is None: context = {}
        
        instance_id = f"{achievement.id}:{context.get('coin_id', 'global')}"
        
        if await self.redis.hget(self.keys.user_achievements(user_id), instance_id):
            return None

        formatted_description = achievement.description.format(**context)
        
        achievement_data = {
            "name": achievement.name,
            "description": formatted_description,
            "reward": achievement.reward_coins
        }

        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hset(self.keys.user_achievements(user_id), instance_id, json.dumps(achievement_data, ensure_ascii=False))
            pipe.hincrbyfloat(self.keys.user_game_profile(user_id), "balance", achievement.reward_coins)
            await pipe.execute()
        logger.info(f"Пользователь {user_id} разблокировал достижение '{achievement.name}' ({formatted_description})")
        return achievement

    async def check_market_events(self, user_id: int) -> List[Achievement]:
        """
        Проверяет рыночные данные и выдает динамические достижения.
        """
        unlocked = []
        top_coins = await self.market_data_service.get_top_coins_by_market_cap()
        if not top_coins:
            return unlocked

        for i, coin in enumerate(top_coins[:30]): # Анализируем топ-30
            coin_id = coin.get('id')
            coin_name = coin.get('name')
            
            # Проверка на новый ATH
            if coin.get('ath') and coin.get('current_price') and coin.get('current_price') >= coin.get('ath'):
                if ach := self.dynamic_achievements.get("dynamic_witness_ath"):
                    if unlocked_ach := await self._unlock_achievement(user_id, ach, context={"coin_name": coin_name, "coin_id": coin_id}):
                        unlocked.append(unlocked_ach)
            
            # Проверка на рост > 25%
            price_change = coin.get('price_change_percentage_24h')
            if price_change and price_change > 25:
                 if ach := self.dynamic_achievements.get("dynamic_pump_rider"):
                    if unlocked_ach := await self._unlock_achievement(user_id, ach, context={"coin_name": coin_name, "coin_id": coin_id}):
                        unlocked.append(unlocked_ach)
            
            # Проверка на вхождение в топ-10
            if i < 10:
                # Здесь нужна логика проверки, что пользователь взаимодействовал с монетой ДО того, как она вошла в топ-10
                # Это требует хранения истории взаимодействий, что является следующим шагом в развитии.
                pass

        return unlocked

    async def process_static_event(self, user_id: int, event_name: str, event_data: Dict[str, Any] = None) -> Optional[Achievement]:
        """Обрабатывает статические события, такие как завершение сессии."""
        if event_data is None: event_data = {}
        
        counters_key = self.keys.user_event_counters(user_id)
        await self.redis.hincrby(counters_key, f"{event_name}_count", 1)

        unlocked_ids_raw = await self.redis.hkeys(self.keys.user_achievements(user_id))
        unlocked_ids = {uid.decode('utf-8').split(':')[0] for uid in unlocked_ids_raw}

        user_counters = await self.redis.hgetall(counters_key)
        user_counters = {k.decode('utf-8'): int(v) for k, v in user_counters.items()}

        for ach_id, achievement in self.static_achievements.items():
            if ach_id not in unlocked_ids and achievement.trigger_event == event_name:
                conditions_met = True
                if achievement.trigger_conditions:
                    for key, required_value in achievement.trigger_conditions.items():
                        if user_counters.get(key, 0) < required_value:
                            conditions_met = False
                            break
                
                if conditions_met:
                    return await self._unlock_achievement(user_id, achievement)
        return None
