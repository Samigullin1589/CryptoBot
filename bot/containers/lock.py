# bot/containers/lock.py
import asyncio
import time
from typing import Optional

from loguru import logger
from redis.asyncio import Redis


class InstanceLockManager:
    def __init__(self, redis: Redis, lock_key: str = "bot:instance_lock", ttl: int = 30):
        self.redis = redis
        self.lock_key = lock_key
        self.ttl = ttl
        self._lock_acquired = False
        self._refresh_task: Optional[asyncio.Task] = None
        self._instance_id = f"{time.time()}"

    async def acquire_lock(self) -> bool:
        try:
            existing_lock = await self.redis.get(self.lock_key)
            
            if existing_lock:
                try:
                    lock_timestamp = float(existing_lock)
                    lock_age = time.time() - lock_timestamp
                    
                    if lock_age > self.ttl * 2:
                        logger.warning(
                            f"⚠️ Found stale lock (age: {lock_age:.1f}s), releasing it"
                        )
                        await self.redis.delete(self.lock_key)
                    else:
                        logger.warning(f"⚠️ Instance lock held by another active process")
                        return False
                except ValueError:
                    logger.warning("⚠️ Invalid lock format, releasing it")
                    await self.redis.delete(self.lock_key)
            
            result = await self.redis.set(
                self.lock_key,
                self._instance_id,
                nx=True,
                ex=self.ttl
            )
            
            if result:
                self._lock_acquired = True
                self._refresh_task = asyncio.create_task(self._refresh_lock())
                logger.info(f"✅ Instance lock acquired: {self.lock_key}")
                return True
            else:
                logger.warning(f"⚠️ Failed to acquire lock after cleanup")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to acquire lock: {e}")
            return False

    async def _refresh_lock(self):
        try:
            while self._lock_acquired:
                await asyncio.sleep(self.ttl / 2)
                if self._lock_acquired:
                    current_lock = await self.redis.get(self.lock_key)
                    
                    if current_lock == self._instance_id:
                        await self.redis.set(
                            self.lock_key,
                            self._instance_id,
                            ex=self.ttl
                        )
                        logger.debug(f"🔄 Lock TTL refreshed: {self.lock_key}")
                    else:
                        logger.warning("⚠️ Lock was taken by another process")
                        self._lock_acquired = False
                        break
        except asyncio.CancelledError:
            logger.debug("Lock refresh task cancelled")
        except Exception as e:
            logger.error(f"Error refreshing lock: {e}")

    async def release_lock(self):
        if not self._lock_acquired:
            return
        
        try:
            self._lock_acquired = False
            
            if self._refresh_task:
                self._refresh_task.cancel()
                try:
                    await self._refresh_task
                except asyncio.CancelledError:
                    pass
            
            current_lock = await self.redis.get(self.lock_key)
            
            if current_lock == self._instance_id:
                await self.redis.delete(self.lock_key)
                logger.info(f"✅ Instance lock released: {self.lock_key}")
            else:
                logger.warning("⚠️ Lock was already taken by another process")
            
        except Exception as e:
            logger.error(f"Error releasing lock: {e}")