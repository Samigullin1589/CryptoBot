from pydantic import BaseModel
from typing import Optional, List

class CryptoCoin(BaseModel):
    id: str
    symbol: str
    name: str
    platforms: Optional[dict] = None

class AsicMiner(BaseModel):
    name: str
    profitability: float  # в USD
    algorithm: str
    power: int  # в Ваттах

class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    correct_option_index: int