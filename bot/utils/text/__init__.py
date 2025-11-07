# bot/utils/text/__init__.py
"""
Модуль текстовых утилит.
Предоставляет функции для нормализации, санитизации, парсинга и форматирования текста.
"""

from bot.utils.text.normalizer import (
    normalize_text,
    normalize_asic_name,
    normalize_whitespace,
    remove_emoji,
    transliterate_to_latin
)
from bot.utils.text.sanitizer import (
    sanitize_html,
    escape_html,
    strip_html,
    safe_html
)
from bot.utils.text.parser import (
    parse_power,
    parse_hashrate,
    extract_numbers,
    extract_urls
)
from bot.utils.text.formatter import (
    clean_json_string,
    clip_text,
    truncate_with_ellipsis,
    format_list,
    format_dict
)

__all__ = [
    # Normalizer
    "normalize_text",
    "normalize_asic_name",
    "normalize_whitespace",
    "remove_emoji",
    "transliterate_to_latin",
    # Sanitizer
    "sanitize_html",
    "escape_html",
    "strip_html",
    "safe_html",
    # Parser
    "parse_power",
    "parse_hashrate",
    "extract_numbers",
    "extract_urls",
    # Formatter
    "clean_json_string",
    "clip_text",
    "truncate_with_ellipsis",
    "format_list",
    "format_dict",
]