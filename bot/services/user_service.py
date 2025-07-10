import redis.asyncio as redis
from bot.config.settings import settings

class UserService:
    """
    Сервис для управления данными и настройками пользователей.
    """
    def __init__(self, redis_client: redis.Redis):
        """
        Инициализирует сервис с клиентом Redis.
        """
        self.redis = redis_client
        # Определяем стоимость по умолчанию из файла настроек
        default_tariff_name = settings.DEFAULT_ELECTRICITY_TARIFF
        self.default_cost = settings.ELECTRICITY_TARIFFS[default_tariff_name]["cost_per_hour"]

    def _get_user_cost_key(self, user_id: int) -> str:
        """Формирует ключ для хранения стоимости э/э пользователя в Redis."""
        return f"user:{user_id}:electricity_cost"

    async def get_user_electricity_cost(self, user_id: int) -> float:
        """
        Получает стоимость электроэнергии для пользователя из Redis.
        Если стоимость не установлена, возвращает значение по умолчанию из настроек.
        """
        cost_key = self._get_user_cost_key(user_id)
        saved_cost = await self.redis.get(cost_key)
        
        if saved_cost:
            return float(saved_cost)
        
        return self.default_cost

    async def set_user_electricity_cost(self, user_id: int, cost: float):
        """Сохраняет стоимость электроэнергии для пользователя в Redis."""
        cost_key = self._get_user_cost_key(user_id)
        await self.redis.set(cost_key, cost)

