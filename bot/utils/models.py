# ===============================================================
# Файл: bot/utils/models.py (ОБНОВЛЕН)
# Описание: Добавлены Pydantic-модели для структурирования
# рыночных данных, получаемых от MarketDataService.
# ===============================================================

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

# --- Модели для ASIC-майнеров ---

class AsicMiner(BaseModel):
    """Модель данных для одного ASIC-майнера."""
    name: str
    profitability: Optional[float] = None
    power: Optional[int] = None
    algorithm: Optional[str] = "Unknown"
    hashrate: Optional[str] = "N/A"
    efficiency: Optional[str] = "N/A"
    source: Optional[str] = None
    
    # Pydantic v2 требует model_dump вместо dict()
    def model_dump(self, **kwargs) -> Dict[str, Any]:
        return super().model_dump(**kwargs)

# --- Модели для криптовалют ---

class CoinInfo(BaseModel):
    """Модель данных для информации о криптовалюте."""
    id: str
    symbol: str
    name: str
    algorithm: Optional[str] = "Unknown"

class PriceInfo(BaseModel):
    """Модель для хранения детальной информации о цене монеты."""
    id: str
    symbol: str
    name: str
    price: float
    price_change_24h: Optional[float] = None
    algorithm: Optional[str] = "Unknown"
    
# --- Модели для новостей ---

class NewsArticle(BaseModel):
    """Модель данных для новостной статьи."""
    title: str
    body: str
    url: str
    ai_summary: Optional[str] = None

# --- Модели для MarketDataService (НОВЫЕ) ---

class FearAndGreedIndex(BaseModel):
    """Модель для Индекса Страха и Жадности."""
    value: int
    value_classification: str

class HalvingInfo(BaseModel):
    """Модель для информации о халвинге."""
    remaining_blocks: int
    estimated_date: datetime
    current_reward: float
    next_reward: float

class NetworkStatus(BaseModel):
    """Модель для статуса сети Bitcoin."""
    difficulty: float
    mempool_txs: int
    fastest_fee: int

# --- Модели для Профиля Пользователя ---

class UserProfile(BaseModel):
    """Модель данных для профиля пользователя в чате."""
    user_id: int
    chat_id: int
    join_timestamp: int
    last_activity_timestamp: int
    trust_score: int = 100
    is_admin: bool = False
    has_immunity: bool = False
    is_banned: bool = False
    mute_until: int = 0
