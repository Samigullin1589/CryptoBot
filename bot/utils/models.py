from typing import Optional, List
from pydantic import BaseModel, Field, AliasChoices

class CryptoCoin(BaseModel):
    """
    Универсальная Pydantic-модель для данных о криптовалюте.
    Использует AliasChoices для корректной работы с разными API.
    """
    id: str
    symbol: str
    name: str
    
    # Pydantic будет искать 'current_price' (от CoinGecko) ИЛИ 'price' (от CoinPaprika)
    price: float = Field(..., validation_alias=AliasChoices('current_price', 'price'))
    
    # То же самое для изменения цены за 24 часа
    price_change_24h: Optional[float] = Field(None, validation_alias=AliasChoices('price_change_percentage_24h', 'percent_change_24h'))
    
    algorithm: Optional[str] = None

class AsicMiner(BaseModel):
    """
    Pydantic-модель для хранения данных об ASIC-майнере.
    """
    name: str
    profitability: float
    algorithm: Optional[str] = None
    hashrate: Optional[str] = None
    power: Optional[int] = None
    efficiency: Optional[str] = None # <<< ДОБАВЛЕНО ЭТО ПОЛЕ
    source: Optional[str] = None