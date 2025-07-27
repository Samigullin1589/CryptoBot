# ===============================================================
# Файл: bot/utils/text_utils.py (НОВЫЙ ФАЙЛ)
# Описание: Содержит утилиты для обработки и парсинга текста.
# ===============================================================

import re
from typing import Optional

import bleach

def sanitize_html(text: str) -> str:
    """
    Очищает текст от небезопасных HTML-тегов, оставляя только разрешенные
    для форматирования в Telegram.
    
    :param text: Исходный текст.
    :return: Очищенный текст.
    """
    if not text:
        return ""
    
    allowed_tags = ['b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 'a', 'code', 'pre']
    allowed_attributes = {'a': ['href']}
    
    return bleach.clean(text, tags=allowed_tags, attributes=allowed_attributes, strip=True)

def parse_profitability(s: str) -> float:
    """
    Извлекает числовое значение доходности из строки.
    Корректно обрабатывает как точки, так и запятые в качестве разделителя.
    
    :param s: Строка с доходностью (например, "$10.5/day" или "12,5").
    :return: Числовое значение доходности или 0.0, если не найдено.
    """
    if not isinstance(s, str):
        s = str(s)
        
    # Заменяем запятую на точку и ищем первое число с плавающей точкой
    match = re.search(r'[\d.]+', s.replace(',', '.'))
    return float(match.group(0)) if match else 0.0

def parse_power(s: str) -> Optional[int]:
    """
    Извлекает числовое значение мощности из строки.
    
    :param s: Строка с мощностью (например, "3250W" или "3000").
    :return: Числовое значение мощности или None, если не найдено.
    """
    if not isinstance(s, str):
        s = str(s)
        
    match = re.search(r'[\d]+', s)
    return int(match.group(0)) if match else None

