# ===============================================================
# Файл: bot/health_check_server.py (НОВЫЙ ФАЙЛ)
# Описание: Легковесный aiohttp-сервер, который отвечает
#           только на health check запросы от Render.
# ===============================================================
import logging
import os

from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def health_check(request: web.Request) -> web.Response:
    """Отвечает 'ok', если сервер запущен."""
    logger.info("Health check endpoint '/healthz' was called.")
    return web.json_response({"status": "ok"})

def main() -> None:
    """Запускает веб-сервер."""
    # Render предоставляет порт через переменную окружения PORT
    port = int(os.environ.get("PORT", 10000))

    app = web.Application()
    app.router.add_get("/healthz", health_check)

    logger.info(f"Starting health check server on 0.0.0.0:{port}")
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
