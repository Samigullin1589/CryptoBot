# bot/services/event_service.py
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from pydantic import ValidationError
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.utils.keys import KeyFactory
from bot.utils.models import EventItem


class EventService:
    """
    Сервис управления игровыми событиями.
    
    Функциональность:
    - Загрузка статических событий из конфигурационного файла
    - Управление динамическими событиями в Redis
    - Расчет итоговых множителей для игровых доменов
    - Кэширование для оптимизации производительности
    """

    _static_events_cache: List[EventItem] = []
    _static_mtime: float = 0.0

    def __init__(self, redis: Redis):
        """
        Инициализирует сервис событий.
        
        Args:
            redis: Клиент Redis для работы с динамическими событиями
        """
        self.redis = redis
        self.config = settings.events
        self.keys = KeyFactory
        
        self._static_config_path = self._resolve_config_path()
        
        logger.info("✅ Сервис EventService инициализирован.")

    def _resolve_config_path(self) -> Path:
        """
        Определяет полный путь к файлу конфигурации статических событий.
        
        Returns:
            Path: Абсолютный путь к файлу конфигурации
        """
        config_path = self.config.config_path
        
        if Path(config_path).is_absolute():
            return Path(config_path)
        
        project_root = Path(__file__).parent.parent.parent
        return project_root / config_path

    async def _load_static_events_if_changed(self) -> None:
        """
        Загружает статические события из JSON-файла при обнаружении изменений.
        Использует in-memory кэш и проверку mtime для оптимизации.
        """
        if not self._static_config_path.exists():
            if not self._static_events_cache:
                logger.warning(
                    f"⚠️ Файл конфигурации событий не найден: {self._static_config_path}"
                )
            return

        try:
            current_mtime = os.path.getmtime(self._static_config_path)
            
            if current_mtime == self._static_mtime and self._static_events_cache:
                return
            
            logger.info(
                f"🔄 Обнаружены изменения в {self._static_config_path.name}. "
                f"Перезагрузка статических событий."
            )
            
            with open(self._static_config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            events_data = data.get("events", [])
            
            if not isinstance(events_data, list):
                logger.error("❌ Ключ 'events' в конфигурации должен быть списком.")
                return

            loaded_events = []
            skipped_count = 0
            
            for item in events_data:
                try:
                    event = EventItem.model_validate(item)
                    loaded_events.append(event)
                except ValidationError as e:
                    skipped_count += 1
                    logger.warning(
                        f"⚠️ Пропущено некорректное событие: {item.get('id', 'unknown')}. "
                        f"Ошибка: {e}"
                    )
            
            self._static_events_cache = loaded_events
            self._static_mtime = current_mtime
            
            logger.success(
                f"✅ Загружено {len(loaded_events)} статических событий"
                + (f" (пропущено: {skipped_count})" if skipped_count else "")
            )

        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON в файле событий: {e}")
        except OSError as e:
            logger.error(f"❌ Ошибка чтения файла событий: {e}")
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при загрузке статических событий: {e}")

    async def _get_dynamic_events(self) -> List[EventItem]:
        """
        Загружает динамические события из Redis.
        
        Returns:
            List[EventItem]: Список валидных динамических событий
        """
        try:
            events_raw = await self.redis.hgetall(self.keys.custom_events())
            
            if not events_raw:
                return []
            
            dynamic_events = []
            skipped_count = 0
            
            for event_id, event_json in events_raw.items():
                try:
                    event = EventItem.model_validate_json(event_json)
                    dynamic_events.append(event)
                except (ValidationError, json.JSONDecodeError) as e:
                    skipped_count += 1
                    logger.warning(
                        f"⚠️ Пропущено некорректное динамическое событие '{event_id}': {e}"
                    )
            
            if skipped_count:
                logger.warning(
                    f"⚠️ Пропущено {skipped_count} некорректных динамических событий"
                )
            
            return dynamic_events
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки динамических событий из Redis: {e}")
            return []

    async def list_all_events(self) -> List[EventItem]:
        """
        Возвращает полный список событий (статические + динамические).
        
        Динамические события с тем же ID имеют приоритет над статическими.
        
        Returns:
            List[EventItem]: Объединенный список всех событий
        """
        await self._load_static_events_if_changed()
        
        static_events = self._static_events_cache
        dynamic_events = await self._get_dynamic_events()

        merged_events: Dict[str, EventItem] = {e.id: e for e in static_events}
        
        for event in dynamic_events:
            merged_events[event.id] = event
        
        return list(merged_events.values())

    async def get_active_events(self) -> List[EventItem]:
        """
        Возвращает список активных событий на текущий момент.
        
        Returns:
            List[EventItem]: События, активные в данный момент времени
        """
        now = datetime.now(timezone.utc)
        all_events = await self.list_all_events()
        
        active = [event for event in all_events if event.is_active(now)]
        
        return active

    async def get_multiplier(self, domain: str) -> float:
        """
        Рассчитывает итоговый множитель для указанного домена.
        
        Перемножает базовый множитель со всеми активными событиями,
        применимыми к данному домену или ко всем доменам ("all").
        
        Args:
            domain: Название игрового домена (например, "mining", "quiz")
            
        Returns:
            float: Итоговый множитель, округленный до 4 знаков
        """
        base_multiplier = self.config.default_multiplier
        active_events = await self.get_active_events()
        
        final_multiplier = base_multiplier
        domain_lower = domain.lower()
        
        applicable_events = [
            event for event in active_events
            if event.domain == "all" or event.domain == domain_lower
        ]
        
        for event in applicable_events:
            final_multiplier *= event.multiplier
        
        return round(final_multiplier, 4)

    async def upsert_event(self, event_data: Dict[str, Any]) -> Optional[EventItem]:
        """
        Создает или обновляет динамическое событие в Redis.
        
        Args:
            event_data: Данные события для валидации и сохранения
            
        Returns:
            Optional[EventItem]: Созданное/обновленное событие или None при ошибке
        """
        try:
            event = EventItem.model_validate(event_data)
            
            await self.redis.hset(
                self.keys.custom_events(),
                event.id,
                event.model_dump_json()
            )
            
            logger.success(f"✅ Событие '{event.id}' успешно создано/обновлено.")
            return event
            
        except ValidationError as e:
            logger.error(
                f"❌ Ошибка валидации события '{event_data.get('id', 'unknown')}': {e}"
            )
            return None
        except Exception as e:
            logger.error(
                f"❌ Ошибка сохранения события '{event_data.get('id', 'unknown')}': {e}"
            )
            return None

    async def cancel_event(self, event_id: str) -> bool:
        """
        Удаляет динамическое событие из Redis.
        
        Args:
            event_id: Идентификатор события для удаления
            
        Returns:
            bool: True если событие удалено, False если не найдено или ошибка
        """
        try:
            result = await self.redis.hdel(self.keys.custom_events(), event_id)
            
            if result > 0:
                logger.success(f"✅ Событие '{event_id}' успешно удалено.")
                return True
            
            logger.warning(f"⚠️ Событие '{event_id}' не найдено для удаления.")
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка удаления события '{event_id}': {e}")
            return False

    async def get_event_by_id(self, event_id: str) -> Optional[EventItem]:
        """
        Получает событие по его идентификатору.
        
        Args:
            event_id: Идентификатор события
            
        Returns:
            Optional[EventItem]: Событие или None если не найдено
        """
        all_events = await self.list_all_events()
        
        for event in all_events:
            if event.id == event_id:
                return event
        
        return None