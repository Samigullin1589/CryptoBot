# bot/core/signals.py
"""
Обработка системных сигналов для graceful shutdown.
"""
import asyncio
import signal
from typing import Set

from loguru import logger


class SignalHandler:
    """Обработчик системных сигналов для корректного завершения."""
    
    def __init__(self, shutdown_event: asyncio.Event):
        self.shutdown_event = shutdown_event
        self._signals_received: Set[signal.Signals] = set()
    
    def setup(self) -> None:
        """Установка обработчиков сигналов."""
        # Список сигналов для обработки
        signals_to_handle = [signal.SIGINT, signal.SIGTERM]
        
        for sig in signals_to_handle:
            try:
                signal.signal(sig, self._signal_handler)
                logger.debug(f"✅ Signal handler registered for {sig.name}")
            except ValueError:
                # В некоторых окружениях (Windows) не все сигналы доступны
                logger.warning(f"⚠️ Cannot register handler for {sig.name}")
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Обработчик сигнала."""
        sig = signal.Signals(signum)
        
        if sig in self._signals_received:
            logger.warning(f"⚠️ {sig.name} received again - forcing shutdown")
            # При повторном сигнале - жесткое завершение
            raise KeyboardInterrupt
        
        self._signals_received.add(sig)
        logger.info(f"🛑 Received {sig.name} - initiating graceful shutdown")
        
        # Устанавливаем событие завершения
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self.shutdown_event.set)
        except RuntimeError:
            # Если event loop еще не запущен
            logger.warning("⚠️ Cannot set shutdown event - event loop not running")