# bot/utils/text/formatter.py
"""
Форматирование и преобразование текста.
"""
import re
import json
from typing import Any, Dict, List, Optional


def clean_json_string(raw_json: str) -> str:
    """
    Очищает строку JSON от markdown-разметки и лишних символов.
    
    Убирает обертки типа ```json ... ``` которые часто добавляют LLM.
    
    Args:
        raw_json: Сырая строка JSON
    
    Returns:
        Очищенная строка JSON
    """
    if not raw_json:
        return ""
    
    # Удаляем markdown code blocks
    cleaned = re.sub(
        r'```[a-zA-Z]*\n?(.*?)\n?```',
        r'\1',
        raw_json,
        flags=re.DOTALL
    )
    
    # Удаляем inline code markers
    cleaned = cleaned.replace('`', '')
    
    # Находим первую открывающую скобку { или [
    start_idx = -1
    for i, char in enumerate(cleaned):
        if char in '{[':
            start_idx = i
            break
    
    # Находим последнюю закрывающую скобку } или ]
    end_idx = -1
    for i in range(len(cleaned) - 1, -1, -1):
        if cleaned[i] in '}]':
            end_idx = i + 1
            break
    
    # Извлекаем JSON
    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
        return cleaned[start_idx:end_idx].strip()
    
    return cleaned.strip()


def clip_text(text: str, max_length: int, ellipsis: str = "...") -> str:
    """
    Обрезает текст до максимальной длины, стараясь не разрывать слова.
    
    Args:
        text: Исходный текст
        max_length: Максимальная длина
        ellipsis: Строка для обозначения обрезки
    
    Returns:
        Обрезанный текст
    """
    if not text or len(text) <= max_length:
        return text
    
    # Резервируем место под ellipsis
    actual_length = max_length - len(ellipsis)
    if actual_length <= 0:
        return ellipsis
    
    # Обрезаем
    clipped = text[:actual_length]
    
    # Ищем последний пробел, чтобы не разрывать слова
    last_space = clipped.rfind(' ')
    if last_space > actual_length * 0.8:  # Если пробел не слишком далеко
        clipped = clipped[:last_space]
    
    return clipped + ellipsis


def truncate_with_ellipsis(
    text: str,
    max_length: int,
    position: str = "end"
) -> str:
    """
    Обрезает текст с многоточием в указанной позиции.
    
    Args:
        text: Исходный текст
        max_length: Максимальная длина
        position: Позиция многоточия ("start", "middle", "end")
    
    Returns:
        Обрезанный текст с многоточием
    """
    if not text or len(text) <= max_length:
        return text
    
    if position == "start":
        # "...остаток текста"
        return "..." + text[-(max_length - 3):]
    
    elif position == "middle":
        # "начало...конец"
        side_length = (max_length - 3) // 2
        return text[:side_length] + "..." + text[-side_length:]
    
    else:  # end (по умолчанию)
        # "текст..."
        return text[:max_length - 3] + "..."


def format_list(
    items: List[Any],
    numbered: bool = False,
    bullet: str = "•"
) -> str:
    """
    Форматирует список элементов в строку.
    
    Args:
        items: Список элементов
        numbered: Использовать нумерацию
        bullet: Символ маркера для ненумерованных списков
    
    Returns:
        Отформатированная строка
    """
    if not items:
        return ""
    
    lines = []
    for i, item in enumerate(items, 1):
        if numbered:
            lines.append(f"{i}. {item}")
        else:
            lines.append(f"{bullet} {item}")
    
    return "\n".join(lines)


def format_dict(
    data: Dict[str, Any],
    indent: int = 0,
    separator: str = ":"
) -> str:
    """
    Форматирует словарь в читаемую строку.
    
    Args:
        data: Словарь для форматирования
        indent: Уровень отступа
        separator: Разделитель ключ-значение
    
    Returns:
        Отформатированная строка
    """
    if not data:
        return ""
    
    lines = []
    indent_str = "  " * indent
    
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{indent_str}{key}{separator}")
            lines.append(format_dict(value, indent + 1, separator))
        elif isinstance(value, list):
            lines.append(f"{indent_str}{key}{separator}")
            for item in value:
                lines.append(f"{indent_str}  • {item}")
        else:
            lines.append(f"{indent_str}{key}{separator} {value}")
    
    return "\n".join(lines)


def format_bytes(size: int) -> str:
    """
    Форматирует размер в байтах в человеко-читаемый формат.
    
    Args:
        size: Размер в байтах
    
    Returns:
        Отформатированная строка (например, "1.5 MB")
    """
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    unit_index = 0
    size_float = float(size)
    
    while size_float >= 1024 and unit_index < len(units) - 1:
        size_float /= 1024
        unit_index += 1
    
    if unit_index == 0:
        return f"{int(size_float)} {units[unit_index]}"
    else:
        return f"{size_float:.2f} {units[unit_index]}"


def format_number(number: float, decimals: int = 2) -> str:
    """
    Форматирует число с разделителями тысяч.
    
    Args:
        number: Число
        decimals: Количество знаков после запятой
    
    Returns:
        Отформатированная строка (например, "1,234.56")
    """
    return f"{number:,.{decimals}f}"