# bot/utils/text/sanitizer.py
"""
Санитизация и экранирование HTML для безопасного вывода.
"""
import re
import bleach
from typing import List, Optional


# Теги, разрешенные для форматирования в Telegram
TELEGRAM_ALLOWED_TAGS = [
    'b', 'strong',           # Жирный
    'i', 'em',               # Курсив
    'u', 'ins',              # Подчеркнутый
    's', 'strike', 'del',    # Зачеркнутый
    'a',                     # Ссылка
    'code',                  # Inline код
    'pre',                   # Блок кода
    'tg-spoiler',            # Спойлер (Telegram)
    'tg-emoji'               # Кастомные emoji (Telegram)
]

# Атрибуты для разрешенных тегов
TELEGRAM_ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    'code': ['class'],
    'pre': ['class'],
    'tg-emoji': ['emoji-id']
}


def sanitize_html(
    text: str,
    allowed_tags: Optional[List[str]] = None,
    strip: bool = True
) -> str:
    """
    Безопасно очищает HTML, оставляя только разрешенные теги.
    
    По умолчанию оставляет только теги, поддерживаемые Telegram.
    
    Args:
        text: HTML строка
        allowed_tags: Список разрешенных тегов (по умолчанию Telegram теги)
        strip: Удалять неразрешенные теги (True) или экранировать (False)
    
    Returns:
        Очищенный HTML
    """
    if not text:
        return ""
    
    if allowed_tags is None:
        allowed_tags = TELEGRAM_ALLOWED_TAGS
    
    return bleach.clean(
        text,
        tags=allowed_tags,
        attributes=TELEGRAM_ALLOWED_ATTRIBUTES,
        strip=strip
    )


def escape_html(text: str) -> str:
    """
    Экранирует специальные HTML-символы для безопасного вывода.
    
    Экранирует: <, >, &, ", '
    
    Args:
        text: Исходный текст
    
    Returns:
        Экранированный текст
    """
    if not text:
        return ""
    
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def strip_html(text: str) -> str:
    """
    Полностью удаляет все HTML теги из текста.
    
    Args:
        text: HTML строка
    
    Returns:
        Текст без тегов
    """
    if not text:
        return ""
    
    # Используем bleach для безопасного удаления всех тегов
    return bleach.clean(text, tags=[], strip=True)


def safe_html(text: str, telegram_mode: bool = True) -> str:
    """
    Делает HTML безопасным для использования.
    
    Комбинирует санитизацию и экранирование для максимальной безопасности.
    
    Args:
        text: HTML строка
        telegram_mode: Использовать теги Telegram (True) или полностью экранировать (False)
    
    Returns:
        Безопасный HTML
    """
    if not text:
        return ""
    
    if telegram_mode:
        # Оставляем только безопасные теги Telegram
        return sanitize_html(text)
    else:
        # Полностью экранируем
        return escape_html(text)