# bot/services/achievement_service.py
# Дата обновления: 19.08.2025
# Версия: 2.0.0
# Описание: Сервис для управления статическими и динамическими достижениями пользователей.

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from loguru import logger
from redis.asyncio import Redis

from bot.services.market_data_service import MarketDataService
from bot.utils.dependencies import get_redis_client
from bot.utils.keys import KeyFactory
from bot.utils.models import Achievement


class AchievementService:
    """
    Управляет логикой загрузки, проверки и выдачи достижений.
    Разделяет достижения на статические (основанные на действиях пользователя)
    и динамические (основанные на рыночных событиях).
    """

    def __init__(self, market_data_service: MarketDataService):
        """
        Инициализирует сервис достижений.

        :param market_data_service: Сервис для получения рыночных данных,
                                    необходимый для динамических достижений.
        """
        self.redis: Redis = get_redis_client()
        self.market_data_service = market_data_service
        self.keys = KeyFactory
        self.static_achievements: Dict[str, Achievement] = {}
        self.dynamic_achievements: Dict[str, Achievement] = {}
        # Путь к файлу конфигурации достижений
        self._config_path = Path(__file__).parent.parent / "config" / "achievements.yaml"
        self._load_achievements_from_config()

    def _load_achievements_from_config(self) -> None:
        """
        Загружает и валидирует конфигурацию достижений из YAML-файла.
        Разделяет их на статические и динамические для дальнейшей обработки.
        """
        logger.info(f"Загрузка конфигурации достижений из файла: {self._config_path}")
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "achievements" not in data:
                logger.warning("Файл конфигурации достижений пуст или не содержит ключ 'achievements'.")
                return

            for ach_data in data["achievements"]:
                try:
                    achievement = Achievement(**ach_data)
                    if achievement.type == "static":
                        self.static_achievements[achievement.id] = achievement
                    elif achievement.type == "dynamic":
                        self.dynamic_achievements[achievement.id] = achievement
                except Exception as pydantic_error:
                    logger.error(f"Ошибка валидации данных для достижения: {ach_data}. Ошибка: {pydantic_error}")

            logger.info(
                f"Загружено {len(self.static_achievements)} статических и "
                f"{len(self.dynamic_achievements)} динамических достижений."
            )
        except FileNotFoundError:
            logger.error(f"Файл конфигурации достижений не найден по пути: {self._config_path}")
        except yaml.YAMLError as e:
            logger.error(f"Ошибка парсинга YAML в файле достижений: {e}")
        except Exception as e:
            logger.exception(f"Непредвиденная ошибка при загрузке достижений: {e}")

    async def get_all_achievements(self) -> List[Achievement]:
        """Возвращает полный список всех сконфигурированных достижений."""
        return list(self.static_achievements.values()) + list(self.dynamic_achievements.values())

    async def get_user_achievements(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Возвращает список всех разблокированных пользователем достижений.
        Данные извлекаются из Redis.
        """
        unlocked_data = await self.redis.hgetall(self.keys.user_achievements(user_id))
        achievements = []
        for ach_json in unlocked_data.values():
            try:
                achievements.append(json.loads(ach_json))
            except json.JSONDecodeError:
                logger.warning(f"Не удалось декодировать JSON для достижения пользователя {user_id}: {ach_json}")
        return achievements

    async def _unlock_achievement(
        self, user_id: int, achievement: Achievement, context: Optional[Dict[str, Any]] = None
    ) -> Optional[Achievement]:
        """
        Атомарно выдает достижение пользователю, если оно еще не было выдано с таким же контекстом.
        Начисляет награду и сохраняет информацию в Redis.

        :param user_id: ID пользователя.
        :param achievement: Объект достижения для выдачи.
        :param context: Контекстные данные для форматирования описания (например, имя монеты).
        :return: Объект Achievement в случае успеха, иначе None.
        """
        context = context or {}
        
        # Создаем уникальный идентификатор для экземпляра достижения,
        # чтобы одно и то же динамическое достижение можно было получить для разных событий (например, для разных монет).
        instance_id = f"{achievement.id}:{context.get('coin_id', 'global')}"

        # Атомарная проверка и установка. HSETNX вернет 1, если поле было создано, и 0, если уже существовало.
        if not await self.redis.hsetnx(self.keys.user_achievements(user_id), instance_id, "placeholder"):
            return None  # Достижение с таким instance_id уже выдано

        try:
            # Создаем копию достижения для пользователя с отформатированным описанием
            unlocked_achievement = achievement.model_copy(deep=True)
            unlocked_achievement.description = achievement.description.format(**context)
            
            # Сериализуем данные для хранения в Redis
            achievement_json = unlocked_achievement.model_dump_json()

            # Используем транзакцию для гарантии целостности данных
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.hset(self.keys.user_achievements(user_id), instance_id, achievement_json)
                pipe.hincrbyfloat(self.keys.user_game_profile(user_id), "balance", achievement.reward_coins)
                await pipe.execute()
            
            logger.success(
                f"Пользователь {user_id} разблокировал достижение '{achievement.name}' "
                f"({unlocked_achievement.description}). Награда: {achievement.reward_coins} монет."
            )
            return unlocked_achievement
        except Exception as e:
            logger.exception(f"Ошибка при выдаче достижения {achievement.id} пользователю {user_id}: {e}")
            # Откатываем изменения, если что-то пошло не так
            await self.redis.hdel(self.keys.user_achievements(user_id), instance_id)
            return None

    async def check_market_events(self, user_id: int) -> List[Achievement]:
        """
        Проверяет рыночные события (например, рост цены, новый ATH) и
        выдает соответствующие динамические достижения.
        """
        unlocked_list = []
        top_coins = await self.market_data_service.get_top_coins_by_market_cap(limit=30)
        if not top_coins:
            logger.warning("Не удалось получить топ монет для проверки динамических достижений.")
            return unlocked_list

        for coin in top_coins:
            coin_id = coin.get("id")
            coin_name = coin.get("name")
            current_price = coin.get("current_price")
            ath = coin.get("ath")
            price_change_24h = coin.get("price_change_percentage_24h")

            if not all([coin_id, coin_name, current_price, ath, price_change_24h]):
                continue # Пропускаем монету, если данные неполные

            # Проверка достижения нового исторического максимума (ATH)
            if current_price >= ath:
                if ach := self.dynamic_achievements.get("dynamic_witness_ath"):
                    context = {"coin_name": coin_name, "coin_id": coin_id}
                    if unlocked_ach := await self._unlock_achievement(user_id, ach, context):
                        unlocked_list.append(unlocked_ach)

            # Проверка значительного роста цены за 24 часа ("Pump Rider")
            if price_change_24h > 25:
                if ach := self.dynamic_achievements.get("dynamic_pump_rider"):
                    context = {"coin_name": coin_name, "coin_id": coin_id}
                    if unlocked_ach := await self._unlock_achievement(user_id, ach, context):
                        unlocked_list.append(unlocked_ach)
        
        return unlocked_list

    async def process_static_event(
        self, user_id: int, event_name: str, event_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Achievement]:
        """
        Обрабатывает статические события (например, 'первая_покупка', 'прохождение_квиза').
        Проверяет, выполнены ли условия для получения статического достижения.
        """
        event_data = event_data or {}
        counters_key = self.keys.user_event_counters(user_id)
        
        # Увеличиваем счетчик для данного события
        current_count = await self.redis.hincrby(counters_key, event_name, 1)

        for ach_id, achievement in self.static_achievements.items():
            if achievement.trigger_event == event_name:
                # Проверяем, выполнено ли условие по количеству событий
                required_count = achievement.trigger_conditions.get(f"{event_name}_count", 1)
                if current_count >= required_count:
                    # Выдаем достижение (внутри _unlock_achievement есть проверка на дубликат)
                    return await self._unlock_achievement(user_id, achievement)
        
        return None