# =================================================================================
# Файл: bot/services/achievement_service.py (ВЕРСИЯ "ГЕНИЙ 2.0" - ОКОНЧАТЕЛЬНАЯ)
# Описание: Управляемый событиями сервис для системы достижений.
# =================================================================================

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

import redis.asyncio as redis
from bot.utils.models import Achievement

logger = logging.getLogger(__name__)

class _KeyFactory:
    """Генератор ключей Redis для системы достижений."""
    @staticmethod
    def user_achievements(user_id: int) -> str: return f"achievements:{user_id}"
    @staticmethod
    def user_event_counters(user_id: int) -> str: return f"achievements:counters:{user_id}"
    @staticmethod
    def user_game_profile(user_id: int) -> str: return f"game:profile:{user_id}"

class AchievementService:
    """Сервис, управляющий логикой получения достижений."""

    def __init__(self, redis_client: redis.Redis, config_path: Path):
        self.redis = redis_client
        self.keys = _KeyFactory
        self.achievements: Dict[str, Achievement] = {}
        self._load_achievements_from_config(config_path)

    def _load_achievements_from_config(self, config_path: Path):
        """Загружает и кэширует в память все достижения из JSON-файла."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for ach_data in data.get("achievements", []):
                achievement = Achievement(**ach_data)
                self.achievements[achievement.id] = achievement
            logger.info(f"Успешно загружено {len(self.achievements)} достижений из '{config_path}'.")
        except Exception as e:
            logger.error(f"Критическая ошибка при загрузке достижений: {e}", exc_info=True)

    async def get_user_achievements(self, user_id: int) -> List[Achievement]:
        """Возвращает список разблокированных пользователем достижений."""
        unlocked_ids = await self.redis.smembers(self.keys.user_achievements(user_id))
        return [self.achievements[ach_id.decode('utf-8')] for ach_id in unlocked_ids if ach_id.decode('utf-8') in self.achievements]

    async def get_all_achievements(self) -> List[Achievement]:
        """Возвращает список всех существующих достижений."""
        return list(self.achievements.values())

    async def _unlock_achievement(self, user_id: int, achievement: Achievement) -> None:
        """Атомарно выдает достижение пользователю и начисляет награду."""
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.sadd(self.keys.user_achievements(user_id), achievement.id)
            pipe.hincrbyfloat(self.keys.user_game_profile(user_id), "balance", achievement.reward_coins)
            await pipe.execute()
        logger.info(f"Пользователь {user_id} разблокировал достижение '{achievement.id}' и получил {achievement.reward_coins} монет.")

    async def process_event(self, user_id: int, event_name: str, event_data: Dict[str, Any] = None) -> Optional[Achievement]:
        """
        Главный метод. Обрабатывает входящее событие и проверяет, не выполнил ли пользователь условия для нового достижения.
        Возвращает разблокированное достижение для немедленного уведомления пользователя.
        """
        if event_data is None:
            event_data = {}
        
        # Увеличиваем счетчики событий для пользователя
        counters_key = self.keys.user_event_counters(user_id)
        # Собираем все счетчики, которые нужно увеличить
        counters_to_increment = {
            f"{event_name}_count": 1,
            # Можно добавить и более сложные счетчики, например, по сумме
            # f"{event_name}_sum": event_data.get('amount', 0)
        }
        await self.redis.hincrby(counters_key, f"{event_name}_count", 1)

        unlocked_ids = await self.redis.smembers(self.keys.user_achievements(user_id))
        unlocked_ids = {uid.decode('utf-8') for uid in unlocked_ids}

        # Получаем текущие значения всех счетчиков пользователя
        user_counters = await self.redis.hgetall(counters_key)
        user_counters = {k.decode('utf-8'): int(v) for k, v in user_counters.items()}

        for ach_id, achievement in self.achievements.items():
            if ach_id not in unlocked_ids and achievement.trigger_event == event_name:
                # Проверяем условия триггера
                conditions_met = True
                if achievement.trigger_conditions:
                    for key, required_value in achievement.trigger_conditions.items():
                        # Условие по счетчику (e.g., sessions_completed: 10)
                        if key.endswith("_count"):
                            if user_counters.get(key, 0) < required_value:
                                conditions_met = False
                                break
                        # Условие по данным из события (e.g., tariff_name: "Промышленный")
                        elif key in event_data:
                            if event_data[key] != required_value:
                                conditions_met = False
                                break
                        else: # Условие не может быть проверено
                            conditions_met = False
                            break
                
                if conditions_met:
                    await self._unlock_achievement(user_id, achievement)
                    # Возвращаем первое сработавшее достижение для уведомления
                    return achievement
        return None