# =================================================================================
# Файл: bot/utils/text_utils.py (ВЕРСИЯ "Distinguished Engineer" - ПРОДАКШН)
# Описание: Утилиты для безопасной обработки и нормализации текста.
# ИСПРАВЛЕНИЕ: Добавлены все недостающие функции из обеих версий.
# =================================================================================

import re
import bleach
import json
from typing import Optional

# Список тегов, разрешенных для форматирования в Telegram
ALLOWED_TAGS = ['b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 'a', 'code', 'pre']

def sanitize_html(text: str) -> str:
    """
    Безопасно очищает HTML-строку, оставляя только теги,
    которые разрешены для форматирования в Telegram.
    """
    if not text:
        return ""
    return bleach.clean(text, tags=ALLOWED_TAGS, strip=True)

def escape_html(text: str) -> str:
    """
    Экранирует специальные HTML-символы (<, >, &) для безопасного вывода.
    """
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def parse_power(power_str: str) -> Optional[int]:
    """
    Извлекает и нормализует значение мощности из строки, возвращая значение в Ваттах.
    """
    if not isinstance(power_str, str):
        return None
    
    power_str = power_str.lower().strip()
    match = re.search(r'(\d[\d\.,]*)', power_str)
    if not match:
        return None
        
    value_str = match.group(1).replace(',', '.')
    try:
        value = float(value_str)
    except ValueError:
        return None

    if 'kw' in power_str or 'квт' in power_str:
        value *= 1000
        
    return int(value)

def normalize_asic_name(name: str) -> str:
    """
    Приводит название ASIC-майнера к стандартизированному виду.
    """
    if not name:
        return ""
    
    normalized = name.lower()
    normalized = re.sub(r'\s*\([^)]*\)', '', normalized)
    normalized = re.sub(r'[-_\/]', ' ', normalized)
    normalized = ' '.join(normalized.split())
    
    return normalized.strip()

def clean_json_string(raw_json: str) -> str:
    """
    Очищает строку, которая должна содержать JSON, от лишних символов
    и markdown-разметки, часто добавляемой LLM.
    """
    if not raw_json:
        return ""
    # Удаляем ```json ... ``` и аналогичные обертки
    cleaned = re.sub(r'```[a-zA-Z]*\n(.*?)\n```', r'\1', raw_json, flags=re.DOTALL)
    # Находим первую { или [ и последнюю } или ]
    start = -1
    end = -1
    for i, char in enumerate(cleaned):
        if char in '{[':
            start = i
            break
    for i, char in enumerate(reversed(cleaned)):
        if char in '}]':
            end = len(cleaned) - i
            break
    
    if start != -1 and end != -1 and start < end:
        return cleaned[start:end]
    return raw_json.strip()

def clip_text(text: str, max_length: int) -> str:
    """
    Обрезает текст до максимальной длины, стараясь не разрывать слова.
    """
    if len(text) <= max_length:
        return text
    
    clipped = text[:max_length]
    last_space = clipped.rfind(' ')
    if last_space != -1:
        return clipped[:last_space] + "..."
    return clipped + "..."