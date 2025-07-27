# ===============================================================
# Файл: bot/utils/text_utils.py (ПРОДАКШН-ВЕРСЯ 2025)
# Описание: Утилиты для обработки и очистки текста.
# ===============================================================
import logging
import re
from typing import Optional

import bleach

logger = logging.getLogger(__name__)

def sanitize_html(text: str) -> str:
    """
    Очищает строку от всех HTML-тегов, кроме разрешенных,
    чтобы предотвратить инъекции и ошибки форматирования в Telegram.
    
    :param text: Входная строка.
    :return: Очищенная строка.
    """
    if not text:
        return ""
    # Разрешаем только базовые теги форматирования, которые поддерживает Telegram
    allowed_tags = ['b', 'i', 'u', 's', 'strike', 'strong', 'em', 'code', 'pre', 'a']
    allowed_attrs = {'a': ['href']}
    return bleach.clean(text, tags=allowed_tags, attributes=allowed_attrs, strip=True)

def parse_power(s: str) -> Optional[int]:
    """
    Извлекает числовое значение мощности из строки.
    Например, из "1350W" вернет 1350.
    
    :param s: Входная строка.
    :return: Мощность в Ваттах или None, если не найдено.
    """
    if not isinstance(s, str):
        s = str(s)
    match = re.search(r'[\d]+', s)
    return int(match.group(0)) if match else None

# --- НОВАЯ ФУНКЦИЯ, КОТОРОЙ НЕ ХВАТАЛО ---
def normalize_asic_name(name: str) -> str:
    """
    Агрессивно очищает и нормализует имя ASIC-майнера для надежного
    сравнения и нечеткого поиска. Удаляет названия брендов, единицы
    измерения и все символы, кроме букв и цифр.
    
    Пример: "Bitmain Antminer S19 Pro 110 Th/s (бу)" -> "s19pro110"
    
    :param name: Исходное имя модели.
    :return: Нормализованное имя.
    """
    if not isinstance(name, str):
        return ""
    # Удаляем распространенные бренды и слова
    name = re.sub(
        r'\b(bitmain|antminer|whatsminer|canaan|avalon|jasminer|goldshell|бу|hydro)\b', 
        '', name, flags=re.IGNORECASE
    )
    # Удаляем единицы измерения хешрейта
    name = re.sub(
        r'\s*(th/s|ths|gh/s|mh/s|ksol|t|g|m)\b', 
        '', name, flags=re.IGNORECASE
    )
    # Оставляем только буквы и цифры в нижнем регистре
    return re.sub(r'[^a-z0-9]', '', name.lower())
# --- КОНЕЦ НОВОЙ ФУНКЦИИ ---
