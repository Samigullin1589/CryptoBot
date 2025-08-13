# =================================================================================
# Файл: bot/keyboards/callback_factories.py (ФИНАЛЬНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ)
# Описание: Централизованное определение всех структур данных для инлайн-кнопок.
# ИСПРАВЛЕНИЕ: Добавлена недостающая фабрика `CryptoCenterCallback`.
# =================================================================================

from aiogram.filters.callback_data import CallbackData
from typing import Optional

# --- ОБЩИЕ ---
class MenuCallback(CallbackData, prefix="menu"):
    level: int
    action: str

class PaginatorCallback(CallbackData, prefix="paginator"):
    action: str
    page: int

# --- ПУБЛИЧНЫЕ РАЗДЕЛЫ ---
class PriceCallback(CallbackData, prefix="price"):
    action: str
    coin_id: Optional[str] = None

class NewsCallback(CallbackData, prefix="news"):
    action: str
    source_key: Optional[str] = None

class AsicCallback(CallbackData, prefix="asic"):
    action: str
    page: Optional[int] = None
    asic_id: Optional[str] = None

class OnboardingCallback(CallbackData, prefix="onboarding"):
    action: str

class QuizCallback(CallbackData, prefix="quiz"):
    action: str
    is_correct: Optional[int] = None

class CryptoCenterCallback(CallbackData, prefix="cc"):
    action: str
    page: Optional[int] = None
    project_id: Optional[str] = None
    task_index: Optional[int] = None

# --- ИНСТРУМЕНТЫ ---
class CalculatorCallback(CallbackData, prefix="calc"):
    action: str
    value: Optional[str] = None
    page: Optional[int] = None
    asic_index: Optional[int] = None

# --- ИГРА ---
class GameCallback(CallbackData, prefix="game"):
    action: str
    value: Optional[str] = None
    page: Optional[int] = None

class MarketCallback(CallbackData, prefix="market"):
    action: str
    listing_id: Optional[str] = None
    asic_id: Optional[str] = None
    page: Optional[int] = None

# --- АДМИН-ПАНЕЛЬ ---
class AdminCallback(CallbackData, prefix="admin"):
    action: str
    value: Optional[str] = None

class GameAdminCallback(CallbackData, prefix="game_admin"):
    action: str

class ThreatCallback(CallbackData, prefix="threat"):
    action: str
    user_id: int
    chat_id: int