# =================================================================================
# Файл: bot/utils/redis_lock.py (ВЕРСИЯ "ГЕНИЙ 3.1" - АВГУСТ 2025)
# Описание: Асинхронный менеджер контекста для распределенной блокировки Redis.
# Обеспечивает предотвращение Race Conditions и Cache Stampede.
# =================================================================================

import asyncio
import logging
import uuid

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class LockAcquisitionError(Exception):
    """Исключение, возникающее, если блокировка не может быть получена."""

    pass


class RedisLock:
    """
    Асинхронный менеджер контекста для распределенной блокировки Redis.

    Использование:
    async with RedisLock(redis_client, "my_resource", timeout=300, wait_timeout=60):
        # Критическая секция
        ...
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        key: str,
        timeout: int = 60,
        wait_timeout: int | None = None,
    ):
        """
        :param redis_client: Экземпляр клиента Redis.
        :param key: Ключ ресурса для блокировки.
        :param timeout: Время жизни блокировки в секундах (TTL). Гарантирует освобождение при сбое.
        :param wait_timeout: Максимальное время ожидания получения блокировки в секундах.
        """
        self.redis = redis_client
        # Добавляем префикс для организации ключей в Redis
        self.key = f"lock:{key}"
        self.timeout = timeout
        self.wait_timeout = wait_timeout
        # Уникальный токен для безопасного освобождения блокировки только владельцем
        self.token = str(uuid.uuid4())
        self.is_acquired = False

    async def acquire(self) -> bool:
        """
        Пытается получить блокировку атомарно.
        Использует SET NX PX для установки ключа, только если он не существует, с таймаутом.
        """
        # Атомарная операция SET NX PX (таймаут в миллисекундах)
        result = await self.redis.set(
            self.key, self.token, nx=True, px=self.timeout * 1000
        )
        self.is_acquired = bool(result)
        return self.is_acquired

    async def release(self):
        """
        Безопасно освобождает блокировку, только если текущий экземпляр является владельцем.
        Использует Lua-скрипт для атомарной проверки и удаления.
        """
        if not self.is_acquired:
            return

        # Атомарный Lua-скрипт: удалить ключ, только если его значение равно токену
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        try:
            # Выполняем скрипт
            result = await self.redis.eval(script, 1, self.key, self.token)
            if result == 0:
                logger.warning(
                    f"Не удалось освободить блокировку {self.key}. Возможно, она истекла и была получена кем-то другим."
                )
            else:
                logger.debug(f"Блокировка {self.key} освобождена.")
        except Exception as e:
            logger.error(f"Ошибка при освобождении блокировки Redis {self.key}: {e}")
        finally:
            self.is_acquired = False

    async def __aenter__(self):
        """Вход в асинхронный контекстный менеджер."""
        start_time = asyncio.get_running_loop().time()

        while True:
            if await self.acquire():
                logger.debug(f"Блокировка {self.key} успешно получена.")
                return self

            # Проверка таймаута ожидания
            if self.wait_timeout is not None:
                elapsed_time = asyncio.get_running_loop().time() - start_time
                if elapsed_time >= self.wait_timeout:
                    logger.error(
                        f"Таймаут ожидания ({self.wait_timeout}s) для получения блокировки {self.key}."
                    )
                    raise LockAcquisitionError(
                        f"Не удалось получить блокировку {self.key} за {self.wait_timeout} секунд."
                    )

            # Фиксированный интервал перед повторной попыткой
            await asyncio.sleep(0.1)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Выход из асинхронного контекстного менеджера."""
        await self.release()
