# ===============================================================
# Файл: bot/utils/models.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Содержит все Pydantic-модели для статической
# типизации данных во всем приложении.
# ===============================================================
from pydantic import BaseModel, Field, conint, field_validator
from typing import List, Optional, Any
from enum import Enum
from datetime import datetime

# --- Модели для ролей и профиля пользователя ---

class UserRole(Enum):
    """Определяет иерархию ролей пользователей."""
    BANNED = 0
    USER = 10
    MODERATOR = 20
    ADMIN = 30
    SUPER_ADMIN = 40

class UserProfile(BaseModel):
    """Профиль пользователя в определенном чате."""
    user_id: int
    chat_id: int
    join_timestamp: float
    role: UserRole = UserRole.USER
    trust_score: int = 100
    is_banned: bool = False
    mute_until_timestamp: float = 0
    violations_count: int = 0
    last_activity_timestamp: float = 0.0
    message_count: int = 0
    conversation_history_json: str = "[]"
    
# --- Модели для данных о криптовалютах и ASIC-майнерах ---

class CoinInfo(BaseModel):
    """Информация о криптовалюте."""
    id: str
    symbol: str
    name: str
    algorithm: Optional[str] = "Unknown"

class PriceInfo(BaseModel):
    """Информация о рыночной цене криптовалюты."""
    name: str
    symbol: str
    price: float
    price_change_24h: Optional[float] = None
    algorithm: Optional[str] = "Unknown"

class AsicMiner(BaseModel):
    """Модель данных для ASIC-майнера."""
    name: str
    profitability: float
    power: Optional[int] = None
    algorithm: Optional[str] = "Unknown"
    hashrate: Optional[str] = "N/A"
    efficiency: Optional[str] = "N/A"
    source: Optional[str] = "Unknown"

# --- Модели для рыночных данных ---

class HalvingInfo(BaseModel):
    """Информация о следующем халвинге Bitcoin."""
    remaining_blocks: int
    estimated_date: datetime
    current_reward: float
    next_reward: float

class NetworkStatus(BaseModel):
    """Информация о текущем статусе сети Bitcoin."""
    difficulty: float
    mempool_transactions: int
    suggested_fee: str

class FearAndGreedIndex(BaseModel):
    """Модель для Индекса страха и жадности."""
    value: int
    value_classification: str

# --- Модели для Крипто-Центра и Новостей ---

class NewsArticle(BaseModel):
    """Модель для новостной статьи."""
    title: str
    url: str
    ai_summary: Optional[str] = None

class AirdropProject(BaseModel):
    """Модель для проекта с потенциальным Airdrop."""
    id: str
    name: str
    description: str
    status: str
    tasks: List[str]
    guide_url: Optional[str] = None

class MiningSignal(BaseModel):
    """Модель для майнинг-сигнала."""
    id: str
    name: str
    description: str
    algorithm: str
    hardware: str
    status: str
    guide_url: Optional[str] = None

# --- Модели для игры и калькулятора ---

class MiningSessionResult(BaseModel):
    """Результаты завершенной майнинг-сессии."""
    asic_name: str
    tariff_name: str
    gross_earned: float
    electricity_cost: float
    net_earned: float

class CalculationResult(BaseModel):
    """Результаты расчета доходности из калькулятора."""
    btc_price_usd: float
    usd_rub_rate: float
    network_hashrate_ths: float
    block_reward_btc: float
    pool_commission: float
    gross_revenue_usd_daily: float
    gross_revenue_usd_monthly: float
    gross_revenue_rub_daily: float
    gross_revenue_rub_monthly: float
    electricity_cost_usd_daily: float
    pool_fee_usd_daily: float
    total_expenses_usd_daily: float
    net_profit_usd_daily: float
    net_profit_usd_monthly: float
    net_profit_usd_yearly: float
    net_profit_rub_daily: float
    net_profit_rub_monthly: float
    net_profit_rub_yearly: float
