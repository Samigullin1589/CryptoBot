# ===============================================================
# Файл: bot/utils/models.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Центральный файл для всех Pydantic-моделей данных,
# используемых в приложении. Обеспечивает строгую типизацию
# и валидацию данных между сервисами.
# ===============================================================
import time
from datetime import datetime
from enum import Enum
from typing import Optional, List, Any

from pydantic import BaseModel, Field, field_validator, conint

# --- Модели для пользователей и ролей ---

class UserRole(Enum):
    """Определяет иерархию ролей пользователей."""
    BANNED = 0
    USER = 10
    MODERATOR = 20
    ADMIN = 30
    SUPER_ADMIN = 40

class UserProfile(BaseModel):
    """Модель для хранения полного профиля пользователя в чате."""
    user_id: int
    chat_id: int
    role: UserRole = UserRole.USER
    join_timestamp: float = Field(default_factory=time.time)
    trust_score: int = 100
    violations_count: int = 0
    last_activity_timestamp: float = Field(default_factory=time.time)
    message_count: int = 0
    conversation_history_json: str = "[]"

# --- Модели для ASIC и майнинга ---

class AsicMiner(BaseModel):
    """Модель данных для одного ASIC-майнера."""
    name: str
    profitability: Optional[float] = None
    algorithm: Optional[str] = 'Unknown'
    power: Optional[int] = None
    hashrate: Optional[str] = 'N/A'
    efficiency: Optional[str] = 'N/A'
    source: Optional[str] = 'Unknown'
    
    @field_validator('power', mode='before')
    @classmethod
    def clean_power(cls, v: Any) -> Optional[int]:
        if isinstance(v, str) and v.isdigit():
            return int(v)
        if isinstance(v, int):
            return v
        return None

class CalculationInput(BaseModel):
    """Модель для входных данных калькулятора доходности."""
    hashrate_str: str
    power_consumption_watts: int
    electricity_cost: float
    pool_commission: float
    algorithm: str

class CalculationResult(BaseModel):
    """Модель для результатов расчета доходности."""
    btc_price_usd: float
    usd_rub_rate: float
    network_hashrate_ths: float
    block_reward_btc: float
    gross_revenue_usd_daily: float
    electricity_cost_usd_daily: float
    pool_fee_usd_daily: float
    total_expenses_usd_daily: float
    net_profit_usd_daily: float

class MiningSessionResult(BaseModel):
    """Модель для результатов завершенной майнинг-сессии."""
    asic_name: str
    user_tariff_name: str
    gross_earned: float
    total_electricity_cost: float
    net_earned: float

# --- Модели для рыночных данных ---

# --- НОВАЯ МОДЕЛЬ, КОТОРОЙ НЕ ХВАТАЛО ---
class FearAndGreedIndex(BaseModel):
    """Модель для данных Индекса Страха и Жадности."""
    value: int
    value_classification: str
# --- КОНЕЦ НОВОЙ МОДЕЛИ ---

class HalvingInfo(BaseModel):
    """Модель для данных о халвинге Bitcoin."""
    remaining_blocks: int
    estimated_date: datetime
    current_reward: float
    next_reward: float

class NetworkStatus(BaseModel):
    """Модель для данных о состоянии сети Bitcoin."""
    difficulty: float
    mempool_txs: int
    fastest_fee: int

class NewsArticle(BaseModel):
    """Модель для одной новостной статьи."""
    title: str
    body: str
    url: str
    source: str

class CoinInfo(BaseModel):
    """Модель для базовой информации о криптовалюте."""
    coin: str  # Тикер, например, "BTC"
    name: str  # Полное имя, например, "Bitcoin"
    algorithm: str

class PriceInfo(BaseModel):
    """Модель для полной информации о цене криптовалюты."""
    id: str  # ID монеты в CoinGecko, например, "bitcoin"
    name: str
    symbol: str
    price: float
    price_change_24h: Optional[float] = Field(alias='price_change_percentage_24h', default=0.0)
    algorithm: str

# --- Модели для викторины ---

class QuizQuestion(BaseModel):
    """Модель для одного вопроса викторины."""
    question: str = Field(..., max_length=300)
    options: List[str] = Field(..., min_length=4, max_length=4)
    correct_option_index: conint(ge=0, lt=4)

    @field_validator('options')
    @classmethod
    def check_options_length(cls, options: List[str]) -> List[str]:
        for option in options:
            if len(option) > 100:
                raise ValueError("Длина варианта ответа не должна превышать 100 символов")
        return options
