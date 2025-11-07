# bot/utils/text/normalizer.py
"""
Нормализация текста для обработки, поиска и анализа.
"""
import re
import unicodedata
from typing import Optional


def normalize_text(text: str, lowercase: bool = True, remove_punctuation: bool = True) -> str:
    """
    Нормализует текст для анализа (антиспам, поиск).
    
    Применяет:
    - Удаление лишних пробелов
    - Приведение к нижнему регистру (опционально)
    - Удаление пунктуации (опционально)
    - Нормализация Unicode
    
    Args:
        text: Исходный текст
        lowercase: Приводить к нижнему регистру
        remove_punctuation: Удалять пунктуацию
    
    Returns:
        Нормализованный текст
    """
    if not text:
        return ""
    
    # Unicode нормализация (NFC - canonical decomposition + canonical composition)
    normalized = unicodedata.normalize('NFC', text)
    
    # Приведение к нижнему регистру
    if lowercase:
        normalized = normalized.lower()
    
    # Удаление пунктуации
    if remove_punctuation:
        # Удаляем все знаки пунктуации, кроме пробелов
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
    
    # Нормализация пробелов
    normalized = normalize_whitespace(normalized)
    
    return normalized.strip()


def normalize_whitespace(text: str) -> str:
    """
    Нормализует пробельные символы.
    
    - Заменяет множественные пробелы на один
    - Заменяет табы и переносы строк на пробелы
    - Удаляет пробелы в начале и конце
    
    Args:
        text: Исходный текст
    
    Returns:
        Текст с нормализованными пробелами
    """
    if not text:
        return ""
    
    # Заменяем все виды пробелов на обычный пробел
    normalized = re.sub(r'\s+', ' ', text)
    
    return normalized.strip()


def normalize_asic_name(name: str) -> str:
    """
    Нормализует название ASIC-майнера для поиска и сравнения.
    
    - Приводит к нижнему регистру
    - Удаляет содержимое в скобках
    - Заменяет дефисы, подчеркивания, слеши на пробелы
    - Удаляет лишние пробелы
    
    Args:
        name: Название ASIC
    
    Returns:
        Нормализованное название
    """
    if not name:
        return ""
    
    # Нижний регистр
    normalized = name.lower()
    
    # Удаление содержимого в скобках (например, "(2023)" или "(Pro)")
    normalized = re.sub(r'\s*\([^)]*\)', '', normalized)
    
    # Замена разделителей на пробелы
    normalized = re.sub(r'[-_/]', ' ', normalized)
    
    # Нормализация пробелов
    normalized = normalize_whitespace(normalized)
    
    return normalized.strip()


def remove_emoji(text: str) -> str:
    """
    Удаляет emoji из текста.
    
    Args:
        text: Исходный текст
    
    Returns:
        Текст без emoji
    """
    if not text:
        return ""
    
    # Паттерн для всех emoji
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002600-\U000026FF"  # Miscellaneous Symbols
        "\U00002700-\U000027BF"  # Dingbats
        "]+",
        flags=re.UNICODE
    )
    
    return emoji_pattern.sub('', text)


def transliterate_to_latin(text: str) -> str:
    """
    Транслитерирует кириллицу в латиницу (русский -> английский).
    
    Полезно для нормализации пользовательского ввода.
    
    Args:
        text: Текст с кириллицей
    
    Returns:
        Транслитерированный текст
    """
    if not text:
        return ""
    
    # Таблица транслитерации (ГОСТ 7.79-2000, система Б)
    translit_table = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd',
        'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i',
        'й': 'j', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
        'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
        'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'ch',
        'ш': 'sh', 'щ': 'shh', 'ъ': '', 'ы': 'y', 'ь': '',
        'э': 'e', 'ю': 'yu', 'я': 'ya',
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D',
        'Е': 'E', 'Ё': 'Yo', 'Ж': 'Zh', 'З': 'Z', 'И': 'I',
        'Й': 'J', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N',
        'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T',
        'У': 'U', 'Ф': 'F', 'Х': 'H', 'Ц': 'C', 'Ч': 'Ch',
        'Ш': 'Sh', 'Щ': 'Shh', 'Ъ': '', 'Ы': 'Y', 'Ь': '',
        'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya'
    }
    
    result = []
    for char in text:
        result.append(translit_table.get(char, char))
    
    return ''.join(result)