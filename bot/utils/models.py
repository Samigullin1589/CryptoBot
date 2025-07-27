# ===============================================================
# Файл: bot/utils/models.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Определяет Pydantic-модели для структурирования
# данных, используемых в различных частях бота.
# ===============================================================

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime  # <-- ИСПРАВЛЕНИЕ: Добавлен необходимый импорт

# --- Модели для пользователей и ролей ---

class UserRole(Enum):
    """Определяет иерархию ролей пользователей."""
    BANNED = 0
    USER = 1
    MODERATOR = 2
    ADMIN = 3
    SUPER_ADMIN = 4

class UserProfile(BaseModel):
    """Модель для хранения полного профиля пользователя в Redis."""
    user_id: int
    chat_id: int
    role: UserRole = UserRole.USER
    join_timestamp: float
    trust_score: int = 100
    is_banned: bool = False
    mute_until_timestamp: float = 0
    violations_count: int = 0
    last_activity_timestamp: float = 0.0
    message_count: int = 0
    conversation_history: List[Dict[str, Any]] = []

# --- Модели для ASIC-майнеров ---

class AsicMiner(BaseModel):
    """Модель для представления данных об ASIC-майнере."""
    name: str
    profitability: Optional[float] = None
    algorithm: Optional[str] = None
    power: Optional[int] = None
    hashrate: Optional[str] = None
    efficiency: Optional[str] = None
    source: Optional[str] = None

# --- Модели для криптовалют ---

class CoinInfo(BaseModel):
    """Модель для представления базовой информации о криптовалюте."""
    id: str
    symbol: str
    name: str
    algorithm: Optional[str] = "Unknown"

class PriceInfo(BaseModel):
    """Модель для представления рыночных данных о криптовалюте."""
    coin: CoinInfo
    price: float
    price_change_24h: Optional[float] = None

# --- Модели для рыночных данных ---

class FearAndGreedIndex(BaseModel):
    """Модель для Индекса страха и жадности."""
    value: int
    classification: str

class HalvingInfo(BaseModel):
    """Модель для данных о халвинге Bitcoin."""
    remaining_blocks: int
    estimated_date: datetime
    next_reward: float

class BtcNetworkStatus(BaseModel):
    """Модель для данных о состоянии сети Bitcoin."""
    difficulty: float
    mempool_transactions: int
    fastest_fee: int

# --- Модели для калькулятора доходности ---

class CalculationInput(BaseModel):
    """Модель для входных данных калькулятора."""
    hashrate_str: str
    power_consumption_watts: int
    electricity_cost_usd: float
    pool_commission_percent: float
    algorithm: str

class CalculationResult(BaseModel):
    """Модель для результатов расчета доходности."""
    inputs: CalculationInput
    market_data: Dict[str, Any]
    gross_revenue_usd_daily: float
    electricity_cost_usd_daily: float
    pool_fee_usd_daily: float
    total_expenses_usd_daily: float
    net_profit_usd_daily: float

# --- Модели для игры "Виртуальный Майнинг" ---

class MiningSessionResult(BaseModel):
    """Модеаль для результатов завершенной майнинг-сессии."""
    user_id: int
    asic_name: str
    user_tariff_name: str
    gross_earned: float
    total_electricity_cost: float
    net_earned: float
