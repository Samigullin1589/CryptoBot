# =================================================================================
# Файл: bot/utils/models.py (ВЕРСИЯ "ГЕНИЙ 3.0" - АВГУСТ 2025)
# Описание: Все Pydantic модели. Добавлена модель MiningEvent.
# =================================================================================

# Используем 'from __future__ import annotations' для соответствия стандартам 2025 года (PEP 563)
from __future__ import annotations
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field

# >>>>> НАЧАЛО ИСПРАВЛЕНИЯ: Добавлена недостающая модель MiningEvent <<<<<
class MiningEvent(BaseModel):
    """
    Модель динамического игрового события, влияющего на результат майнинга.
    Загружается из events_config.json.
    """
    name: str = Field(description="Название события")
    description: str = Field(description="Описание события для пользователя")
    probability: float = Field(ge=0.0, le=1.0, description="Вероятность возникновения (0.0-1.0)")
    # Используем Field для установки значений по умолчанию, соответствующих отсутствию эффекта
    profit_multiplier: float = Field(default=1.0, description="Множитель дохода (напр., 1.5 для +50%)")
    cost_multiplier: float = Field(default=1.0, description="Множитель затрат (напр., 0.5 для -50%)")
# >>>>> КОНЕЦ ИСПРАВЛЕНИЯ <<<<<

class UserProfile(BaseModel):
    """Профиль пользователя Telegram."""
    user_id: int
    username: str
    full_name: str
    language_code: str

class AsicMiner(BaseModel):
    """Модель данных для ASIC-майнера."""
    id: str
    name: str
    hashrate: str
    power: int
    algorithm: str
    profitability: float
    price: float

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

class Achievement(BaseModel):
    """
    Модель для достижения. Загружается из achievements_config.json.
    """
    id: str
    name: str
    description: str
    reward_coins: float
    trigger_event: str
    trigger_conditions: Optional[Dict[str, Any]] = None

class MiningSessionResult(BaseModel):
    """Результаты завершенной майнинг-сессии."""
    asic_name: str
    user_tariff_name: str
    gross_earned: float
    total_electricity_cost: float
    net_earned: float
    event_description: Optional[str] = None
    # Используем Optional[Achievement] благодаря from __future__ import annotations
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
    correct_option: int # Индекс правильного ответа
    explanation: str