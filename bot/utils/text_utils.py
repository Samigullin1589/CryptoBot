# bot/utils/text_utils.py
# =================================================================================
# Файл: bot/utils/text_utils.py (ВЕРСИЯ "Distinguished Engineer" - ПРОДАКШН)
# Описание: Утилиты для безопасной обработки и нормализации текста.
# ИСПРАВЛЕНИЕ: Добавлены недостающие функции parse_power и normalize_asic_name.
# =================================================================================

import re
import bleach
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
    cleaned_text = bleach.clean(text, tags=ALLOWED_TAGS, strip=True)
    return cleaned_text

def escape_html(text: str) -> str:
    """
    Экранирует специальные HTML-символы (<, >, &) для безопасного вывода.
    """
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def parse_power(power_str: str) -> Optional[int]:
    """
    Извлекает и нормализует значение мощности из строки.
    Обрабатывает форматы "3400 W", "3.4 kW" и т.д., возвращая значение в Ваттах.
    """
    if not isinstance(power_str, str):
        return None
    
    power_str = power_str.lower().strip()
    
    # Ищем число (целое или с плавающей точкой)
    match = re.search(r'(\d[\d\.,]*)', power_str)
    if not match:
        return None
        
    value_str = match.group(1).replace(',', '.')
    
    try:
        value = float(value_str)
    except ValueError:
        return None

    # Проверяем на киловатты
    if 'kw' in power_str or 'квт' in power_str:
        value *= 1000
        
    return int(value)

def normalize_asic_name(name: str) -> str:
    """
    Приводит название ASIC-майнера к стандартизированному виду для
    упрощения поиска и сравнения.
    """
    if not name:
        return ""
    
    # Приводим к нижнему регистру
    normalized = name.lower()
    
    # Удаляем информацию о вольтаже и прочие скобки
    normalized = re.sub(r'\s*\([^)]*\)', '', normalized)
    
    # Заменяем распространенные разделители на пробел
    normalized = re.sub(r'[-_\/]', ' ', normalized)
    
    # Удаляем лишние пробелы
    normalized = ' '.join(normalized.split())
    
    return normalized.strip()

