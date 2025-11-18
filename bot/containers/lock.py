# bot/containers/lock.py
"""
Менеджер instance lock для предотвращения множественных запусков бота.
"""
import asyncio
import time
import uuid
from typing import Optional

from loguru import logger
from redis.asyncio import Redis


class InstanceLockManager:
    """
    Менеджер блокировки экземпляра для предотвращения дублирующих запусков.
    
    Использует Redis для распределенной блокировки с:
    - Уникальным instance ID
    - Автоматическим обновлением TTL
    - Очисткой устаревших блокировок
    - Безопасным освобождением
    """
    
    # Константы
    DEFAULT_LOCK_KEY = "bot:instance_lock"
    DEFAULT_TTL = 15  # секунды (уменьшено с 30 для быстрого истечения при сбое)
    STALE_LOCK_MULTIPLIER = 2  # Блокировка считается устаревшей после TTL * 2
    REFRESH_INTERVAL_DIVISOR = 3  # Обновляем каждые TTL / 3 (каждые 5 сек)
    
    def __init__(
        self,
        redis: Redis,
        lock_key: str = DEFAULT_LOCK_KEY,
        ttl: int = DEFAULT_TTL
    ):
        """
        Инициализация менеджера блокировки.
        
        Args:
            redis: Клиент Redis
            lock_key: Ключ для блокировки в Redis
            ttl: Time To Live блокировки в секундах
        """
        self.redis = redis
        self.lock_key = lock_key
        self.ttl = ttl
        
        # Уникальный ID этого экземпляра
        self._instance_id = self._generate_instance_id()
        
        # Состояние блокировки
        self._lock_acquired = False
        self._refresh_task: Optional[asyncio.Task] = None
        self._cleanup_registered = False

        logger.debug(f"🔧 InstanceLockManager initialized with instance_id: {self._instance_id}")
        logger.debug(f"🔧 Lock TTL: {self.ttl}s, Refresh interval: {self.ttl / self.REFRESH_INTERVAL_DIVISOR:.1f}s")
    
    @staticmethod
    def _generate_instance_id() -> str:
        """Генерация уникального ID экземпляра."""
        # UUID + timestamp для гарантии уникальности
        return f"{uuid.uuid4().hex}_{int(time.time() * 1000)}"
    
    async def acquire_lock(self) -> bool:
        """
        Получение блокировки экземпляра.
        
        Returns:
            True если блокировка успешно получена, False в противном случае
        """
        try:
            # Проверяем существующую блокировку
            if not await self._check_and_cleanup_stale_lock():
                logger.warning("⚠️ Instance lock is held by another active process")
                return False
            
            # Пытаемся установить блокировку атомарно
            result = await self.redis.set(
                self.lock_key,
                self._instance_id,
                nx=True,  # Установить только если не существует
                ex=self.ttl  # С автоматическим истечением
            )
            
            if result:
                self._lock_acquired = True
                # Запускаем задачу обновления TTL
                self._refresh_task = asyncio.create_task(
                    self._refresh_lock_loop(),
                    name="instance_lock_refresh"
                )
                logger.info(f"✅ Instance lock acquired: {self.lock_key}")
                return True
            else:
                logger.warning("⚠️ Failed to acquire lock (race condition)")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error acquiring instance lock: {e}", exc_info=True)
            return False
    
    async def _check_and_cleanup_stale_lock(self) -> bool:
        """
        Проверка и очистка устаревшей блокировки.
        
        Returns:
            True если можно продолжать (нет блокировки или она была очищена),
            False если блокировка активна
        """
        try:
            existing_lock = await self.redis.get(self.lock_key)
            
            if not existing_lock:
                # Блокировки нет - можно продолжать
                return True
            
            # Проверяем TTL существующей блокировки
            ttl = await self.redis.ttl(self.lock_key)
            
            if ttl == -1:
                # Блокировка без TTL - это ошибка, очищаем
                logger.warning("⚠️ Found lock without TTL, cleaning up")
                await self.redis.delete(self.lock_key)
                return True
            
            if ttl <= 0:
                # Блокировка истекла или скоро истечет
                logger.warning(f"⚠️ Found expired/expiring lock (TTL: {ttl}s), cleaning up")
                await self.redis.delete(self.lock_key)
                return True
            
            # Блокировка активна
            logger.debug(f"Active lock found with TTL: {ttl}s")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking stale lock: {e}", exc_info=True)
            # В случае ошибки лучше не пытаться получить блокировку
            return False
    
    async def _refresh_lock_loop(self) -> None:
        """Цикл обновления TTL блокировки."""
        refresh_interval = self.ttl / self.REFRESH_INTERVAL_DIVISOR
        
        logger.debug(f"🔄 Lock refresh loop started (interval: {refresh_interval}s)")
        
        try:
            while self._lock_acquired:
                await asyncio.sleep(refresh_interval)
                
                if not self._lock_acquired:
                    break
                
                # Проверяем, что блокировка все еще наша
                current_lock = await self.redis.get(self.lock_key)
                
                if current_lock != self._instance_id:
                    logger.error(
                        "⚠️ Lock was taken by another process! "
                        f"Expected: {self._instance_id}, Got: {current_lock}"
                    )
                    self._lock_acquired = False
                    break
                
                # Обновляем TTL
                await self.redis.expire(self.lock_key, self.ttl)
                logger.debug(f"🔄 Lock TTL refreshed: {self.lock_key}")
                
        except asyncio.CancelledError:
            logger.debug("Lock refresh loop cancelled")
        except Exception as e:
            logger.error(f"❌ Error in lock refresh loop: {e}", exc_info=True)
            self._lock_acquired = False
    
    async def release_lock(self, force: bool = False) -> None:
        """
        Освобождение блокировки.

        Args:
            force: Принудительное освобождение (игнорирует проверки)
        """
        if not self._lock_acquired and not force:
            logger.debug("Lock not acquired, nothing to release")
            return

        try:
            # Останавливаем флаг
            self._lock_acquired = False

            # Отменяем задачу обновления
            if self._refresh_task and not self._refresh_task.done():
                self._refresh_task.cancel()
                try:
                    await self._refresh_task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.warning(f"⚠️ Error waiting for refresh task: {e}")

            # Безопасно удаляем блокировку только если она наша
            # Используем Lua скрипт для атомарности
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """

            result = await self.redis.eval(
                lua_script,
                1,
                self.lock_key,
                self._instance_id
            )

            if result == 1:
                logger.info(f"✅ Instance lock released: {self.lock_key} (instance: {self._instance_id[:8]}...)")
            else:
                logger.warning(
                    f"⚠️ Lock was already taken by another process or expired (instance: {self._instance_id[:8]}...)"
                )

        except Exception as e:
            logger.error(f"❌ Error releasing lock: {e}", exc_info=True)
            # В случае ошибки, пытаемся удалить lock принудительно (без проверки владельца)
            if force:
                try:
                    await self.redis.delete(self.lock_key)
                    logger.warning(f"⚠️ Forcefully deleted lock: {self.lock_key}")
                except Exception as force_err:
                    logger.error(f"❌ Failed to force delete lock: {force_err}")
    
    def is_acquired(self) -> bool:
        """Проверка, получена ли блокировка."""
        return self._lock_acquired

    def get_instance_id(self) -> str:
        """Возвращает instance ID."""
        return self._instance_id