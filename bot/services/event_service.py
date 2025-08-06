# =================================================================================
# Файл: bot/services/event_service.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Полностью самодостаточный сервис для управления динамическими
# игровыми событиями, полностью интегрированный в DI-архитектуру.
# ИСПРАВЛЕНИЕ: Сервис переработан для получения всех зависимостей через __init__.
# =================================================================================

import json
import random
import logging
from pathlib import Path
from typing import List, Optional

from bot.config.settings import MiningEventServiceConfig
from bot.utils.models import MiningEvent

logger = logging.getLogger(__name__)

class MiningEventService:
    """
    Сервис, отвечающий за генерацию случайных событий в игре.
    События и их вероятности полностью управляются через внешний JSON-файл.
    """

    # ИСПРАВЛЕНО: Конструктор теперь принимает объект config
    def __init__(self, config: MiningEventServiceConfig):
        """
        Инициализирует сервис игровых событий.

        :param config: Конфигурация для сервиса событий.
        """
        self.config = config
        self.events: List[MiningEvent] = []
        # Путь к файлу теперь берется из объекта конфигурации
        self._load_events_from_config(Path(self.config.config_path))

    def _load_events_from_config(self, config_path: Path):
        """Загружает и валидирует события из JSON-файла."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.events = [MiningEvent(**event_data) for event_data in data.get("events", [])]
            
            total_probability = sum(event.probability for event in self.events)
            if total_probability > 1.0:
                logger.warning(f"Суммарная вероятность событий ({total_probability}) больше 1.0. "
                               "Это означает, что событие будет происходить всегда.")
            
            logger.info(f"Успешно загружено {len(self.events)} игровых событий из '{config_path}'.")

        except FileNotFoundError:
            logger.error(f"Файл конфигурации событий не найден по пути: {config_path}")
        except json.JSONDecodeError:
            logger.error(f"Ошибка декодирования JSON в файле: {config_path}")
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при загрузке событий: {e}")

    def get_random_event(self) -> Optional[MiningEvent]:
        """
        Возвращает случайное событие на основе его вероятности или None.
        """
        if not self.events:
            return None

        events = self.events
        weights = [event.probability for event in self.events]
        
        total_probability = sum(weights)
        no_event_probability = max(0, 1.0 - total_probability)
        
        choices = events + [None]
        final_weights = weights + [no_event_probability]

        chosen_event = random.choices(choices, weights=final_weights, k=1)[0]
        
        if chosen_event:
            logger.info(f"Сгенерировано игровое событие: {chosen_event.name}")
        else:
            logger.info("Игровое событие не сгенерировано (штатный режим).")
            
        return chosen_event
