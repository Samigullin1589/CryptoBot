# bot/utils/text/parser.py
"""
Парсинг и извлечение структурированных данных из текста.
"""
import re
from typing import Optional, List
from decimal import Decimal, InvalidOperation


def parse_power(power_str: str) -> Optional[int]:
    """
    Извлекает и нормализует мощность из строки, возвращая значение в Ваттах.
    
    Поддерживаемые форматы:
    - "1500W", "1500 W", "1500 Вт"
    - "1.5kW", "1.5 kW", "1.5 кВт"
    - "1500", "1,500"
    
    Args:
        power_str: Строка с мощностью
    
    Returns:
        Мощность в Ваттах или None при ошибке парсинга
    """
    if not isinstance(power_str, str):
        return None
    
    # Нормализация входной строки
    power_str = power_str.lower().strip()
    
    # Извлечение числового значения
    match = re.search(r'(\d[\d\s.,]*)', power_str)
    if not match:
        return None
    
    value_str = match.group(1)
    # Удаляем пробелы и заменяем запятую на точку
    value_str = value_str.replace(' ', '').replace(',', '.')
    
    try:
        value = float(value_str)
    except ValueError:
        return None
    
    # Проверка единиц измерения
    if any(unit in power_str for unit in ['kw', 'квт', 'kilowatt']):
        value *= 1000
    elif any(unit in power_str for unit in ['mw', 'мвт', 'megawatt']):
        value *= 1_000_000
    
    return int(value)


def parse_hashrate(hashrate_str: str) -> Optional[float]:
    """
    Извлекает и нормализует хешрейт из строки, возвращая значение в TH/s.
    
    Поддерживаемые форматы:
    - "100 TH/s", "100TH/s"
    - "100 GH/s", "100GH/s"
    - "100 MH/s", "100MH/s"
    - "0.1 PH/s", "0.1PH/s"
    
    Args:
        hashrate_str: Строка с хешрейтом
    
    Returns:
        Хешрейт в TH/s или None при ошибке парсинга
    """
    if not isinstance(hashrate_str, str):
        return None
    
    # Нормализация
    hashrate_str = hashrate_str.lower().strip()
    
    # Извлечение числа
    match = re.search(r'(\d+\.?\d*)', hashrate_str)
    if not match:
        return None
    
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    
    # Преобразование в TH/s
    if 'ph/s' in hashrate_str or 'пх/с' in hashrate_str:
        value *= 1000  # PH/s -> TH/s
    elif 'gh/s' in hashrate_str or 'гх/с' in hashrate_str:
        value /= 1000  # GH/s -> TH/s
    elif 'mh/s' in hashrate_str or 'мх/с' in hashrate_str:
        value /= 1_000_000  # MH/s -> TH/s
    # По умолчанию считаем что указано в TH/s
    
    return value


def extract_numbers(text: str) -> List[float]:
    """
    Извлекает все числа из текста.
    
    Поддерживает:
    - Целые числа: 123
    - Дробные числа: 123.45, 123,45
    - Отрицательные числа: -123
    
    Args:
        text: Исходный текст
    
    Returns:
        Список чисел
    """
    if not text:
        return []
    
    # Паттерн для чисел (включая отрицательные и дробные)
    pattern = r'-?\d+[.,]?\d*'
    matches = re.findall(pattern, text)
    
    numbers = []
    for match in matches:
        try:
            # Заменяем запятую на точку
            num_str = match.replace(',', '.')
            numbers.append(float(num_str))
        except ValueError:
            continue
    
    return numbers


def extract_urls(text: str) -> List[str]:
    """
    Извлекает все URL из текста.
    
    Args:
        text: Исходный текст
    
    Returns:
        Список найденных URL
    """
    if not text:
        return []
    
    # Паттерн для URL
    url_pattern = re.compile(
        r'http[s]?://'  # http:// или https://
        r'(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|'  # Разрешенные символы
        r'(?:%[0-9a-fA-F][0-9a-fA-F]))+'  # Процентное кодирование
    )
    
    return url_pattern.findall(text)


def extract_mentions(text: str) -> List[str]:
    """
    Извлекает упоминания пользователей (@username) из текста.
    
    Args:
        text: Исходный текст
    
    Returns:
        Список username (без @)
    """
    if not text:
        return []
    
    # Паттерн для Telegram username
    pattern = r'@([a-zA-Z0-9_]{5,32})'
    matches = re.findall(pattern, text)
    
    return matches


def extract_hashtags(text: str) -> List[str]:
    """
    Извлекает хештеги (#hashtag) из текста.
    
    Args:
        text: Исходный текст
    
    Returns:
        Список хештегов (без #)
    """
    if not text:
        return []
    
    # Паттерн для хештегов
    pattern = r'#([a-zA-Zа-яА-ЯёЁ0-9_]+)'
    matches = re.findall(pattern, text)
    
    return matches