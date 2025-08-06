# =================================================================================
# Файл: bot/utils/models.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Полный и самодостаточный набор Pydantic-моделей для всего проекта.
# ИСПРАВЛЕНИЕ: Добавлено поле 'type' в модель Achievement.
# =================================================================================

from __future__ import annotations
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field

class Coin(BaseModel):
    """
    Pydantic-модель для представления данных о криптовалюте,
    получаемых от API CoinGecko.
    """
    id: str = Field(description="Уникальный идентификатор CoinGecko (например, 'bitcoin')")
    symbol: str = Field(description="Тикер монеты (например, 'btc')")
    name: str = Field(description="Полное название монеты (например, 'Bitcoin')")

class PriceInfo(BaseModel):
    """
    Модель для хранения детальной информации о цене криптовалюты.
    """
    price: float
    market_cap: Optional[float] = None
    volume_24h: Optional[float] = None
    change_24h: Optional[float] = None

class MiningEvent(BaseModel):
    """
    Модель динамического игрового события, влияющего на результат майнинга.
    Загружается из events_config.json.
    """
    name: str = Field(description="Название события")
    description: str = Field(description="Описание события для пользователя")
    probability: float = Field(ge=0.0, le=1.0, description="Вероятность возникновения (0.0-1.0)")
    profit_multiplier: float = Field(default=1.0, description="Множитель дохода (напр., 1.5 для +50%)")
    cost_multiplier: float = Field(default=1.0, description="Множитель затрат (напр., 0.5 для -50%)")

class UserProfile(BaseModel):
    """Профиль пользователя Telegram."""
    user_id: int
    username: Optional[str] = None
    full_name: str
    language_code: Optional[str] = None

class AsicMiner(BaseModel):
    """Модель данных для ASIC-майнера."""
    id: str
    name: str
    hashrate: str
    power: int
    algorithm: str
    profitability: Optional[float] = None
    price: Optional[float] = None

class NewsArticle(BaseModel):
    """Модель для новостной статьи."""
    title: str
    url: str
    body: str
    source: str
    timestamp: int
    ai_summary: Optional[str] = None

class AirdropProject(BaseModel):
    """Модель для Airdrop-проекта из Crypto Center."""
    id: str
    name: str
    description: str
    status: str
    tasks: List[str]
    guide_url: Optional[str] = None

# ИСПРАВЛЕНО: Добавлено поле 'type' для поддержки динамических достижений
class Achievement(BaseModel):
    """
    Модель для достижения. Загружается из achievements_config.json.
    """
    id: str
    name: str
    description: str
    reward_coins: float
    trigger_event: str
    type: str = "static" # 'static' или 'dynamic'
    trigger_conditions: Optional[Dict[str, Any]] = None

class MiningSessionResult(BaseModel):
    """Результаты завершенной майнинг-сессии."""
    asic_name: str
    user_tariff_name: str
    gross_earned: float
    total_electricity_cost: float
    net_earned: float
    event_description: Optional[str] = None
    unlocked_achievement: Optional[Achievement] = None

class MarketListing(BaseModel):
    """
    Модель для лота, выставленного на продажу на рынке.
    """
    id: str
    seller_id: int
    price: float
    created_at: int
    asic_data: str # Храним данные асика в виде JSON-строки

class QuizQuestion(BaseModel):
    """Модель для вопроса в викторине."""
    question: str
    options: List[str]
    correct_option_index: int # Индекс правильного ответа
    explanation: Optional[str] = None

class AIVerdict(BaseModel):
    """
    Модель для структурированного ответа от AI-анализатора безопасности.
    Определяет вердикт по проанализированному сообщению.
    """
    intent: str = Field(default="other", description="Основное намерение сообщения.")
    toxicity_score: float = Field(default=0.0, description="Оценка токсичности от 0.0 до 1.0.")
    is_potential_scam: bool = Field(default=False, description="True, если сообщение похоже на мошенничество.")
    is_potential_phishing: bool = Field(default=False, description="True, если сообщение содержит подозрительные ссылки.")
