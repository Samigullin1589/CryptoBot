# bot/core/health.py
"""
Health check HTTP server для Render и мониторинга.
"""
import asyncio
from typing import Optional

from aiohttp import web
from loguru import logger


class HealthServer:
    """HTTP сервер для health checks."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 10000):
        self.host = host
        self.port = port
        self.runner: Optional[web.AppRunner] = None
        self._app: Optional[web.Application] = None
    
    def _create_app(self) -> web.Application:
        """Создание aiohttp приложения."""
        app = web.Application()
        app.router.add_get("/health", self._health_check)
        app.router.add_get("/healthz", self._health_check)
        app.router.add_get("/ready", self._readiness_check)
        app.router.add_get("/live", self._liveness_check)
        return app
    
    async def _health_check(self, request: web.Request) -> web.Response:
        """Основной health check endpoint."""
        return web.json_response({
            "status": "healthy",
            "service": "cryptobot",
            "version": "3.1.0"
        })
    
    async def _readiness_check(self, request: web.Request) -> web.Response:
        """Readiness probe - готов ли сервис принимать запросы."""
        return web.json_response({
            "status": "ready",
            "service": "cryptobot"
        })
    
    async def _liveness_check(self, request: web.Request) -> web.Response:
        """Liveness probe - жив ли сервис."""
        return web.json_response({
            "status": "alive",
            "service": "cryptobot"
        })
    
    async def start(self) -> None:
        """Запуск HTTP сервера."""
        self._app = self._create_app()
        self.runner = web.AppRunner(self._app)
        
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()
        
        logger.info(f"🏥 Health check server started on {self.host}:{self.port}")
        logger.info(f"   - Health: http://{self.host}:{self.port}/health")
        logger.info(f"   - Ready:  http://{self.host}:{self.port}/ready")
        logger.info(f"   - Live:   http://{self.host}:{self.port}/live")
        
        # Держим сервер запущенным
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            logger.info("⚠️ Health server cancelled")
            raise
    
    async def stop(self) -> None:
        """Остановка HTTP сервера."""
        if self.runner:
            logger.info("🛑 Stopping health server...")
            await self.runner.cleanup()
            logger.info("✅ Health server stopped")