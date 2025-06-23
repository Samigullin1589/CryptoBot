from typing import Optional
from pydantic import BaseModel, Field

class CryptoCoin(BaseModel):
    """
    Pydantic-модель для хранения данных о криптовалюте.
    Использует псевдонимы для унификации данных из разных API.
    """
    id: str
    symbol: str
    name: str
    price: float
    # Pydantic будет искать 'price_change_percentage_24h' (от CoinGecko)
    # или 'percent_change_24h' (от CoinPaprika) и помещать значение в это поле.
    price_change_24h: Optional[float] = Field(None, validation_alias='price_change_percentage_24h')
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
    source: Optional[str] = None