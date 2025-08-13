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
from typing import List, Optional, Dict

from bot.config.settings import MiningEventServiceConfig
from bot.utils.models import MiningEvent

logger = logging.getLogger(__name__)

class MiningEventService:
    """
    Сервис, отвечающий за генерацию случайных событий в игре.
    События и их вероятности полностью управляются через внешний JSON-файл.
    """

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
            
            # ИСПРАВЛЕНО: Собираем события из всех пулов в один список
            all_events_data = []
            if "event_pools" in data:
                for pool_name, event_list in data["event_pools"].items():
                    if isinstance(event_list, list):
                        # Для простых событий берем 'effects', для интерактивных - нет
                        for event_data in event_list:
                             # Простая эвристика для преобразования структуры эффектов
                            if "effects" in event_data and isinstance(event_data["effects"], list):
                                effect = event_data["effects"][0]
                                if effect["type"] == "PROFIT_MULTIPLIER":
                                    event_data["profit_multiplier"] = effect["value"]
                                if effect["type"] == "COST_MULTIPLIER":
                                    event_data["cost_multiplier"] = effect["value"]
                            # Устанавливаем вероятность 1, т.к. она теперь управляется глобально
                            event_data["probability"] = 1.0 
                            all_events_data.append(event_data)

            self.events = [MiningEvent(**event_data) for event_data in all_events_data]
            
            logger.info(f"Успешно загружено {len(self.events)} игровых событий из '{config_path}'.")

        except FileNotFoundError:
            logger.error(f"Файл конфигурации событий не найден по пути: {config_path}")
        except json.JSONDecodeError:
            logger.error(f"Ошибка декодирования JSON в файле: {config_path}")
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при загрузке событий: {e}", exc_info=True)

    def get_random_event(self) -> Optional[MiningEvent]:
        """
        Возвращает случайное событие на основе его вероятности или None.
        """
        if not self.events:
            return None

        # Используем глобальный шанс на событие из конфига, если он есть
        event_chance = 0.25 # Значение по умолчанию, если не найдено в конфиге
        try:
             with open(self.config.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                event_chance = data.get("global_settings", {}).get("event_chance_per_session", 0.25)
        except Exception:
            pass # Используем значение по умолчанию

        # Сначала решаем, произойдет ли событие вообще
        if random.random() > event_chance:
            logger.info("Игровое событие не сгенерировано (штатный режим).")
            return None

        # Если событие произошло, выбираем случайное из пула
        chosen_event = random.choice(self.events)
        
        logger.info(f"Сгенерировано игровое событие: {chosen_event.name}")
            
        return chosen_event