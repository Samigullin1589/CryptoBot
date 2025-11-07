# bot/utils/redis_lock.py
"""
Универсальная распределенная блокировка Redis.
Используется для критических секций и предотвращения race conditions.
"""
import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class LockAcquisitionError(Exception):
    """Исключение при невозможности получить блокировку."""
    pass


class LockReleaseError(Exception):
    """Исключение при ошибке освобождения блокировки."""
    pass


class RedisLock:
    """
    Асинхронный менеджер контекста для распределенной блокировки Redis.
    
    Реализует паттерн Redlock для надежной распределенной блокировки.
    
    Использование:
        async with RedisLock(redis_client, "resource_key", timeout=60):
            # Критическая секция
            await do_critical_work()
    
    Или явное управление:
        lock = RedisLock(redis_client, "resource_key")
        if await lock.acquire():
            try:
                await do_critical_work()
            finally:
                await lock.release()
    """
    
    # Константы
    DEFAULT_TIMEOUT = 60  # секунды
    DEFAULT_RETRY_DELAY = 0.1  # секунды
    LOCK_PREFIX = "lock:"
    
    def __init__(
        self,
        redis_client: redis.Redis,
        key: str,
        timeout: int = DEFAULT_TIMEOUT,
        wait_timeout: Optional[int] = None,
        retry_delay: float = DEFAULT_RETRY_DELAY
    ):
        """
        Инициализация блокировки.
        
        Args:
            redis_client: Клиент Redis
            key: Ключ ресурса для блокировки
            timeout: Время жизни блокировки (TTL) в секундах
            wait_timeout: Максимальное время ожидания получения блокировки
            retry_delay: Задержка между попытками получения блокировки
        """
        self.redis = redis_client
        self.key = f"{self.LOCK_PREFIX}{key}"
        self.timeout = timeout
        self.wait_timeout = wait_timeout
        self.retry_delay = retry_delay
        
        # Уникальный токен владельца блокировки
        self.token = self._generate_token()
        
        # Состояние
        self.is_acquired = False
        self._acquisition_time: Optional[float] = None
        
        logger.debug(f"🔧 RedisLock created: {self.key} (timeout={timeout}s)")
    
    @staticmethod
    def _generate_token() -> str:
        """Генерация уникального токена владельца."""
        return str(uuid.uuid4())
    
    async def acquire(self) -> bool:
        """
        Попытка получить блокировку атомарно.
        
        Returns:
            True если блокировка получена, False в противном случае
        """
        try:
            # Атомарная операция SET NX PX
            # NX - установить только если не существует
            # PX - timeout в миллисекундах
            result = await self.redis.set(
                self.key,
                self.token,
                nx=True,
                px=self.timeout * 1000
            )
            
            self.is_acquired = bool(result)
            
            if self.is_acquired:
                self._acquisition_time = asyncio.get_event_loop().time()
                logger.debug(f"✅ Lock acquired: {self.key}")
            else:
                logger.debug(f"⚠️ Lock not acquired: {self.key}")
            
            return self.is_acquired
            
        except Exception as e:
            logger.error(f"❌ Error acquiring lock {self.key}: {e}", exc_info=True)
            return False
    
    async def release(self) -> None:
        """
        Безопасное освобождение блокировки.
        
        Использует Lua скрипт для атомарной проверки владельца и удаления.
        
        Raises:
            LockReleaseError: При ошибке освобождения блокировки
        """
        if not self.is_acquired:
            logger.debug(f"Lock {self.key} not acquired, nothing to release")
            return
        
        # Lua скрипт для атомарного освобождения
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        
        try:
            result = await self.redis.eval(
                lua_script,
                1,
                self.key,
                self.token
            )
            
            if result == 1:
                # Вычисляем время удержания блокировки
                if self._acquisition_time:
                    hold_time = asyncio.get_event_loop().time() - self._acquisition_time
                    logger.debug(
                        f"✅ Lock released: {self.key} "
                        f"(held for {hold_time:.2f}s)"
                    )
                else:
                    logger.debug(f"✅ Lock released: {self.key}")
            else:
                logger.warning(
                    f"⚠️ Failed to release lock {self.key}: "
                    "lock expired or taken by another owner"
                )
            
        except Exception as e:
            logger.error(f"❌ Error releasing lock {self.key}: {e}", exc_info=True)
            raise LockReleaseError(f"Failed to release lock {self.key}") from e
        finally:
            self.is_acquired = False
            self._acquisition_time = None
    
    async def extend(self, additional_time: int) -> bool:
        """
        Продление времени жизни блокировки.
        
        Args:
            additional_time: Дополнительное время в секундах
        
        Returns:
            True если продление успешно, False в противном случае
        """
        if not self.is_acquired:
            logger.warning(f"Cannot extend lock {self.key}: not acquired")
            return False
        
        # Lua скрипт для атомарного продления
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("pexpire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        
        try:
            result = await self.redis.eval(
                lua_script,
                1,
                self.key,
                self.token,
                additional_time * 1000
            )
            
            if result == 1:
                logger.debug(f"✅ Lock extended: {self.key} (+{additional_time}s)")
                return True
            else:
                logger.warning(f"⚠️ Failed to extend lock {self.key}: not owner")
                self.is_acquired = False
                return False
                
        except Exception as e:
            logger.error(f"❌ Error extending lock {self.key}: {e}", exc_info=True)
            return False
    
    async def __aenter__(self):
        """Вход в асинхронный контекстный менеджер."""
        start_time = asyncio.get_event_loop().time()
        attempt = 0
        
        while True:
            attempt += 1
            
            # Попытка получить блокировку
            if await self.acquire():
                if attempt > 1:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    logger.debug(
                        f"✅ Lock acquired after {attempt} attempts "
                        f"in {elapsed:.2f}s: {self.key}"
                    )
                return self
            
            # Проверка таймаута ожидания
            if self.wait_timeout is not None:
                elapsed_time = asyncio.get_event_loop().time() - start_time
                
                if elapsed_time >= self.wait_timeout:
                    logger.error(
                        f"❌ Lock acquisition timeout ({self.wait_timeout}s) "
                        f"after {attempt} attempts: {self.key}"
                    )
                    raise LockAcquisitionError(
                        f"Failed to acquire lock {self.key} "
                        f"after {self.wait_timeout}s ({attempt} attempts)"
                    )
            
            # Логируем каждые 10 попыток
            if attempt % 10 == 0:
                logger.debug(
                    f"⏳ Still waiting for lock {self.key} "
                    f"(attempt {attempt})..."
                )
            
            # Ждем перед следующей попыткой
            await asyncio.sleep(self.retry_delay)
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Выход из асинхронного контекстного менеджера."""
        await self.release()
        
        # Логируем исключения если они были
        if exc_type is not None:
            logger.debug(
                f"⚠️ Exception during lock {self.key}: "
                f"{exc_type.__name__}: {exc_val}"
            )
        
        return False  # Не подавляем исключения


# Удобная фабричная функция
@asynccontextmanager
async def redis_lock(
    redis_client: redis.Redis,
    key: str,
    timeout: int = RedisLock.DEFAULT_TIMEOUT,
    wait_timeout: Optional[int] = None
):
    """
    Контекстный менеджер для Redis блокировки.
    
    Пример:
        async with redis_lock(redis, "my_resource", timeout=60):
            await do_work()
    """
    lock = RedisLock(redis_client, key, timeout, wait_timeout)
    async with lock:
        yield lock