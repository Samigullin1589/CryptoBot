# ===============================================================
# Файл: bot/utils/text_utils.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Утилиты для обработки и парсинга текста.
# ===============================================================
import re
from datetime import timedelta
from typing import Optional

import bleach

def sanitize_html(text: str) -> str:
    """Очищает текст от небезопасных HTML-тегов."""
    if not text:
        return ""
    return bleach.clean(
        text,
        tags=['b', 'i', 'u', 's', 'code', 'pre', 'a', 'blockquote'],
        attributes={'a': ['href']},
        strip=True
    )

def normalize_asic_name(name: str) -> str:
    """Агрессивно очищает имя ASIC для надежного сравнения."""
    name = re.sub(r'\b(bitmain|antminer|whatsminer|canaan|avalon|jasminer|goldshell|бу|hydro)\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*(th/s|ths|gh/s|mh/s|ksol|t|g|m)\b', '', name, flags=re.IGNORECASE)
    # Удаляем все, кроме букв и цифр, и приводим к нижнему регистру
    return re.sub(r'[^a-z0-9]', '', name.lower())

def parse_power(s: str) -> Optional[int]:
    """Извлекает числовое значение мощности из строки."""
    if not isinstance(s, str):
        s = str(s)
    match = re.search(r'[\d]+', s)
    return int(match.group(0)) if match else None

def parse_duration(text: str) -> Optional[timedelta]:
    """
    Парсит строку с длительностью (например, "30m", "2h", "1d") в объект timedelta.
    """
    if not isinstance(text, str):
        return None
        
    match = re.match(r"(\d+)([mhd])", text.lower().strip())
    if not match:
        return None
        
    value, unit = int(match.group(1)), match.group(2)
    
    if unit == 'm':
        return timedelta(minutes=value)
    if unit == 'h':
        return timedelta(hours=value)
    if unit == 'd':
        return timedelta(days=value)
        
    return None
