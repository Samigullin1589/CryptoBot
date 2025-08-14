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


# Админские фабрики: используем разделитель "|" вместо ":" чтобы значения могли содержать двоеточия.
class AdminCallback(CallbackData, prefix="admin", sep="|"):
    action: str
    value: Optional[str] = None
    section: Optional[str] = None
    page: Optional[int] = None


class GameAdminCallback(CallbackData, prefix="adgame", sep="|"):
    action: str
    value: Optional[str] = None
    page: Optional[int] = None
