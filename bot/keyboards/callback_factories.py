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


# Угроза/модерация: стандартный разделитель ":" подходит, значения — числа/простые строки.
# Порядок полей важен — он соответствует ожидаемой схеме 'threat:<action>:<user_id>:<message_id>:<chat_id>'
class ThreatCallback(CallbackData, prefix="threat"):
    action: str            # ban | pardon | ignore
    user_id: Optional[int] = None
    message_id: Optional[int] = None
    chat_id: Optional[int] = None


# Цены/топ-ASIC/инфо — максимально совместимая фабрика:
# поддерживает как value, так и именованные поля symbol/fiat/page/source,
# чтобы соответствовать различным существующим вызовам .pack(...)
class PriceCallback(CallbackData, prefix="price"):
    action: str
    value: Optional[str] = None
    symbol: Optional[str] = None
    fiat: Optional[str] = None
    page: Optional[int] = None
    source: Optional[str] = None