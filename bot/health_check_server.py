# bot/health_check_server.py
import logging
import os

from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def health_check(request: web.Request) -> web.Response:
    logger.info("✅ Health check endpoint '/health' called")
    return web.json_response({"status": "ok", "service": "cryptobot"})


def main() -> None:
    port = int(os.environ.get("PORT", 10000))
    
    app = web.Application()
    app.router.add_get("/health", health_check)
    app.router.add_get("/healthz", health_check)
    
    logger.info(f"🏥 Starting health check server on 0.0.0.0:{port}")
    web.run_app(app, host="0.0.0.0", port=port, access_log=None)


if __name__ == "__main__":
    main()