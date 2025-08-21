# bot/services/event_service.py
# Дата обновления: 20.08.2025
# Версия: 2.0.0
# Описание: Сервис для управления статическими и динамическими игровыми
# событиями (баффами, акциями) с кэшированием в Redis.

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from pydantic import ValidationError
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.utils.dependencies import get_redis_client
from bot.utils.keys import KeyFactory
from bot.utils.models import EventItem, parse_datetime


class EventService:
    """
    Управляет жизненным циклом игровых событий.
    - Загружает базовые события из файла конфигурации.
    - Позволяет администраторам динамически создавать/удалять события в Redis.
    - Предоставляет методы для получения активных событий и расчета итоговых множителей.
    """

    _static_events_cache: List[EventItem] = []
    _static_config_path: Optional[Path] = None
    _static_mtime: float = 0.0

    def __init__(self):
        """Инициализирует сервис, получая зависимости и конфигурацию."""
        self.redis: Redis = get_redis_client()
        self.config = settings.EVENTS
        self.keys = KeyFactory
        self._static_config_path = Path(__file__).parent.parent.parent / self.config.CONFIG_PATH
        logger.info("Сервис EventService инициализирован.")

    async def _load_static_events_if_changed(self):
        """
        Загружает статические события из JSON-файла, если файл изменился.
        Использует in-memory кэш для предотвращения лишних дисковых операций.
        """
        if not self._static_config_path or not self._static_config_path.exists():
            if not self._static_events_cache:
                logger.warning(f"Файл конфигурации статических событий не найден: {self._static_config_path}")
            return

        try:
            current_mtime = os.path.getmtime(self._static_config_path)
            if current_mtime == self._static_mtime:
                return  # Файл не менялся, используем кэш

            logger.info(f"Обнаружены изменения в файле {self._static_config_path}. Перезагрузка статических событий.")
            
            with open(self._static_config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            events_data = data.get("events", [])
            if not isinstance(events_data, list):
                logger.error("Ключ 'events' в конфиге должен быть списком.")
                return

            loaded_events = []
            for item in events_data:
                try:
                    loaded_events.append(EventItem.model_validate(item))
                except ValidationError as e:
                    logger.warning(f"Пропущено некорректное статическое событие: {item}. Ошибка: {e}")
            
            self._static_events_cache = loaded_events
            self._static_mtime = current_mtime
            logger.success(f"Загружено {len(self._static_events_cache)} статических событий.")

        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Не удалось прочитать или обработать файл статических событий: {e}")

    async def _get_dynamic_events(self) -> List[EventItem]:
        """Загружает динамические (созданные админом) события из Redis."""
        try:
            events_raw = await self.redis.hgetall(self.keys.custom_events())
            if not events_raw:
                return []
            
            dynamic_events = []
            for event_json in events_raw.values():
                try:
                    dynamic_events.append(EventItem.model_validate_json(event_json))
                except (ValidationError, json.JSONDecodeError) as e:
                    logger.warning(f"Пропущено некорректное динамическое событие в Redis: {event_json}. Ошибка: {e}")
            return dynamic_events
        except Exception as e:
            logger.error(f"Не удалось загрузить динамические события из Redis: {e}")
            return []

    async def list_all_events(self) -> List[EventItem]:
        """
        Возвращает объединенный список всех событий (статических и динамических).
        Динамические события с тем же ID перезаписывают статические.
        """
        await self._load_static_events_if_changed()
        static_events = self._static_events_cache
        dynamic_events = await self._get_dynamic_events()

        merged_events: Dict[str, EventItem] = {e.id: e for e in static_events}
        for event in dynamic_events:
            merged_events[event.id] = event
        
        return list(merged_events.values())

    async def get_active_events(self) -> List[EventItem]:
        """Возвращает список только активных на данный момент событий."""
        now = datetime.now(timezone.utc)
        all_events = await self.list_all_events()
        return [event for event in all_events if event.is_active(now)]

    async def get_multiplier(self, domain: str) -> float:
        """
        Рассчитывает итоговый множитель для указанной игровой области (домена).
        Перемножает множители всех активных событий, подходящих под домен.
        """
        base_multiplier = self.config.DEFAULT_MULTIPLIER
        active_events = await self.get_active_events()
        
        final_multiplier = base_multiplier
        domain_lower = domain.lower()
        
        for event in active_events:
            if event.domain == "all" or event.domain == domain_lower:
                final_multiplier *= event.multiplier

        return round(final_multiplier, 4)

    async def upsert_event(self, event_data: Dict[str, Any]) -> Optional[EventItem]:
        """Создает или обновляет динамическое событие в Redis."""
        try:
            # Валидируем и создаем объект события
            event = EventItem.model_validate(event_data)
            await self.redis.hset(
                self.keys.custom_events(),
                event.id,
                event.model_dump_json()
            )
            logger.success(f"Динамическое событие '{event.id}' успешно создано/обновлено.")
            return event
        except ValidationError as e:
            logger.error(f"Ошибка валидации данных при создании события: {event_data}. Ошибка: {e}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении события '{event_data.get('id')}' в Redis: {e}")
        return None

    async def cancel_event(self, event_id: str) -> bool:
        """Удаляет динамическое событие из Redis."""
        try:
            result = await self.redis.hdel(self.keys.custom_events(), event_id)
            if result > 0:
                logger.info(f"Динамическое событие '{event_id}' успешно удалено.")
                return True
            logger.warning(f"Попытка удалить несуществующее событие '{event_id}'.")
            return False
        except Exception as e:
            logger.error(f"Ошибка при удалении события '{event_id}': {e}")
            return False