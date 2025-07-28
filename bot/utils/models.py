# ===============================================================
# Файл: bot/utils/models.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Центральный файл для всех Pydantic-моделей данных,
# используемых в приложении. Обеспечивает строгую типизацию
# и валидацию данных.
# ===============================================================
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import IntEnum
from datetime import datetime

# --- Роли пользователей ---

class UserRole(IntEnum):
    """Определяет иерархию ролей пользователей."""
    BANNED = 0
    USER = 1
    MODERATOR = 10
    ADMIN = 100
    SUPER_ADMIN = 1000

# --- Основные модели данных ---

class UserProfile(BaseModel):
    """Профиль пользователя в чате."""
    user_id: int
    join_timestamp: float = Field(default_factory=datetime.now().timestamp)
    trust_score: int = 100
    violations_count: int = 0
    last_activity_timestamp: float = Field(default_factory=datetime.now().timestamp)
    role: UserRole = UserRole.USER
    conversation_history: List[Dict[str, Any]] = []

class AsicMiner(BaseModel):
    """Модель данных для ASIC-майнера."""
    name: str
    profitability: float
    power: Optional[int] = None
    algorithm: Optional[str] = None
    hashrate: Optional[str] = None
    efficiency: Optional[str] = None
    source: Optional[str] = None

class CoinInfo(BaseModel):
    """Модель данных для криптовалюты."""
    id: str
    symbol: str
    name: str
    algorithm: Optional[str] = "Unknown"

class PriceInfo(BaseModel):
    """Модель данных с информацией о цене криптовалюты."""
    name: str
    symbol: str
    price: float
    price_change_24h: Optional[float] = None
    algorithm: Optional[str] = "Unknown"

class NewsArticle(BaseModel):
    """Модель данных для новостной статьи."""
    title: str
    url: str
    body: str
    ai_summary: Optional[str] = None

# --- ИСПРАВЛЕНИЕ: Добавлена недостающая модель ---
class AIVerdict(BaseModel):
    """
    Структурированный вердикт от AI-анализатора безопасности.
    """
    is_spam: bool = Field(..., description="Является ли сообщение спамом.")
    threat_category: str = Field(..., description="Категория угрозы (PHISHING, SCAM, SOCIAL_ENGINEERING, NONE).")
    toxicity_score: float = Field(..., description="Оценка токсичности от 0.0 до 1.0.")
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---

class AirdropProject(BaseModel):
    """Модель для Airdrop-проекта, сгенерированного AI."""
    id: str
    name: str
    description: str
    status: str
    tasks: List[str]
    guide_url: Optional[str] = None

class MiningSignal(BaseModel):
    """Модель для майнинг-сигнала, сгенерированного AI."""
    id: str
    name: str
    description: str
    algorithm: str
    hardware: str
    status: str
    guide_url: Optional[str] = None

class FearAndGreedIndex(BaseModel):
    """Модель для Индекса страха и жадности."""
    value: int
    value_classification: str

class HalvingInfo(BaseModel):
    """Модель для данных о халвинге."""
    remaining_blocks: int
    estimated_date: datetime
    current_reward: float
    next_reward: float

class NetworkStatus(BaseModel):
    """Модель для статуса сети Bitcoin."""
    difficulty: float
    mempool_txs: int
    suggested_fee: int

class CalculationInput(BaseModel):
    """Входные данные для расчета доходности."""
    btc_price_usd: float
    network_hashrate_ths: float
    block_reward_btc: float
    usd_rub_rate: float

class CalculationResultData(BaseModel):
    """Результаты вычислений доходности."""
    gross_revenue_usd_daily: float
    gross_revenue_usd_monthly: float
    electricity_cost_usd_daily: float
    pool_fee_usd_daily: float
    total_expenses_usd_daily: float
    net_profit_usd_daily: float
    net_profit_usd_monthly: float
    net_profit_usd_yearly: float

class CalculationResult(BaseModel):
    """Полный результат расчета для форматирования."""
    input_data: CalculationInput
    calculation_data: CalculationResultData
    pool_commission: float

class MiningSessionResult(BaseModel):
    """Результат завершенной игровой майнинг-сессии."""
    asic_name: str
    gross_earned: float
    electricity_cost: float
    net_earned: float
    tariff_name: str

class QuizQuestion(BaseModel):
    """Модель для вопроса викторины."""
    question: str
    options: List[str]
    correct_option_index: int
