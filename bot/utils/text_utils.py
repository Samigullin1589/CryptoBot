# bot/utils/text_utils.py
# =================================================================================
# Файл: bot/utils/text_utils.py (ВЕРСИЯ "Distinguished Engineer" - ПРОДАКШН)
# Описание: Утилиты для безопасной обработки текста.
# ИСПРАВЛЕНИЕ: Добавлена недостающая функция sanitize_html.
# =================================================================================

import bleach

# Список тегов, разрешенных для форматирования в Telegram
ALLOWED_TAGS = ['b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 'a', 'code', 'pre']

def sanitize_html(text: str) -> str:
    """
    Безопасно очищает HTML-строку, оставляя только теги,
    которые разрешены для форматирования в Telegram.

    Это защищает от XSS-атак и нежелательного форматирования.

    :param text: Входная строка с HTML.
    :return: Очищенная и безопасная строка.
    """
    if not text:
        return ""
    
    # Используем bleach для очистки, оставляя только разрешенные теги
    cleaned_text = bleach.clean(text, tags=ALLOWED_TAGS, strip=True)
    return cleaned_text

def escape_html(text: str) -> str:
    """
    Экранирует специальные HTML-символы (<, >, &) для безопасного вывода.
    """
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

