# =================================================================================
# Файл: bot/services/achievement_service.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Управляемый событиями сервис для системы достижений,
# полностью интегрированный в DI-архитектуру.
# ИСПРАВЛЕНИЕ: Сервис переработан для получения всех зависимостей через __init__.
# =================================================================================

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

import redis.asyncio as redis

from bot.config.settings import AchievementServiceConfig
from bot.utils.models import Achievement
from bot.utils.keys import KeyFactory

logger = logging.getLogger(__name__)

class AchievementService:
    """Сервис, управляющий логикой получения достижений."""

    # ИСПРАВЛЕНО: Конструктор теперь принимает redis и config
    def __init__(self, redis: redis.Redis, config: AchievementServiceConfig):
        """
        Инициализирует сервис достижений.

        :param redis: Асинхронный клиент Redis.
        :param config: Конфигурация для сервиса достижений.
        """
        self.redis = redis
        self.config = config
        self.keys = KeyFactory
        self.achievements: Dict[str, Achievement] = {}
        self._load_achievements_from_config(Path(self.config.config_path))

    def _load_achievements_from_config(self, config_path: Path):
        """Загружает и кэширует в память все достижения из JSON-файла."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for ach_data in data.get("achievements", []):
                achievement = Achievement(**ach_data)
                self.achievements[achievement.id] = achievement
            logger.info(f"Успешно загружено {len(self.achievements)} достижений из '{config_path}'.")
        except FileNotFoundError:
            logger.error(f"Файл конфигурации достижений не найден: {config_path}")
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
        """
        if event_data is None:
            event_data = {}
        
        counters_key = self.keys.user_event_counters(user_id)
        await self.redis.hincrby(counters_key, f"{event_name}_count", 1)

        unlocked_ids = await self.redis.smembers(self.keys.user_achievements(user_id))
        unlocked_ids = {uid.decode('utf-8') for uid in unlocked_ids}

        user_counters = await self.redis.hgetall(counters_key)
        user_counters = {k.decode('utf-8'): int(v) for k, v in user_counters.items()}

        for ach_id, achievement in self.achievements.items():
            if ach_id not in unlocked_ids and achievement.trigger_event == event_name:
                conditions_met = True
                if achievement.trigger_conditions:
                    for key, required_value in achievement.trigger_conditions.items():
                        if key.endswith("_count"):
                            if user_counters.get(key, 0) < required_value:
                                conditions_met = False
                                break
                        elif key in event_data:
                            if event_data[key] != required_value:
                                conditions_met = False
                                break
                        else:
                            conditions_met = False
                            break
                
                if conditions_met:
                    await self._unlock_achievement(user_id, achievement)
                    return achievement
        return None
