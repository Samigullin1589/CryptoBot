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


# Угроза/модерация
class ThreatCallback(CallbackData, prefix="threat"):
    action: str            # ban | pardon | ignore
    user_id: Optional[int] = None
    message_id: Optional[int] = None
    chat_id: Optional[int] = None


# Цены/топ-ASIC/инфо
class PriceCallback(CallbackData, prefix="price"):
    action: str
    value: Optional[str] = None
    symbol: Optional[str] = None
    fiat: Optional[str] = None
    page: Optional[int] = None
    source: Optional[str] = None


# ASIC: используем гибкое множество полей (часто встречающиеся в проекте),
# и разделитель "|" чтобы action мог содержать подтипы через ":" (например, "top:page").
class AsicCallback(CallbackData, prefix="asic", sep="|"):
    action: str
    value: Optional[str] = None
    asic_id: Optional[str] = None
    page: Optional[int] = None
    sort: Optional[str] = None
    vendor: Optional[str] = None


# Новости (источники, категории, пагинация)
class NewsCallback(CallbackData, prefix="news"):
    action: str                    # source | category | page | open | refresh
    source: Optional[str] = None   # cryptopanic | newsapi | rss | ...
    category: Optional[str] = None
    value: Optional[str] = None
    page: Optional[int] = None