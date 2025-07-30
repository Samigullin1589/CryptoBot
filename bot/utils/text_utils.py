# ===============================================================
# Файл: bot/utils/text_utils.py (НОВЫЙ ФАЙЛ)
# Описание: Утилиты для обработки и нормализации текста.
# ===============================================================
import re

def normalize_asic_name(name: str) -> str:
    """Приводит имя ASIC к единому формату: lowercase, без пробелов и спецсимволов."""
    if not name:
        return ""
    # Удаляем общие слова и спецсимволы
    name = re.sub(r'\b(bitmain|antminer|whatsminer|canaan|avalon|innosilicon)\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\(.*\)', '', name) # Удаляем текст в скобках
    # Оставляем только буквы и цифры
    return re.sub(r'[^a-z0-9]', '', name.lower())

def parse_power(power_str: str) -> int:
    """Извлекает числовое значение мощности из строки."""
    if not isinstance(power_str, str):
        return 0
    # Находим все числа в строке
    numbers = re.findall(r'\d+', power_str)
    return int(numbers[0]) if numbers else 0