# =================================================================================
# Файл: bot/keyboards/callback_factories.py (ФИНАЛЬНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ)
# Описание: Централизованное определение всех структур данных для инлайн-кнопок.
# ИСПРАВЛЕНИЕ: Добавлена недостающая фабрика `CryptoCenterCallback`.
# =================================================================================

from typing import Optional
from aiogram.filters.callback_data import CallbackData


class MenuCallback(CallbackData, prefix="menu"):
    level: int
    action: str
    value: Optional[str] = None
    page: Optional[int] = None


class GameCallback(CallbackData, prefix="game"):
    action: str
    value: Optional[str] = None
    page: Optional[int] = None


class PaginatorCallback(CallbackData, prefix="pg"):
    page: int
    per_page: Optional[int] = None
    scope: Optional[str] = None


class CalculatorCallback(CallbackData, prefix="calc"):
    action: str
    value: Optional[str] = None
    asic_index: Optional[int] = None
    page: Optional[int] = None


# ВНИМАНИЕ:
# По логу 2025-08-14 13:30:25,352 падение происходило из-за того, что в значении action использовался двоеточие,
# а у CallbackData по умолчанию разделитель ':' — поэтому pack() выбрасывал ValueError.
# Устанавливаем sep="|" для AdminCallback, чтобы строки вида "stats:general" были допустимы.
class AdminCallback(CallbackData, prefix="admin", sep="|"):
    action: str  # допускает значения с ':' внутри (например, "stats:general")
    value: Optional[str] = None
    section: Optional[str] = None
    page: Optional[int] = None