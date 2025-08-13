# ===============================================================
# Файл: bot/health_check_server.py (НОВЫЙ ФАЙЛ)
# Описание: Легковесный aiohttp-сервер, который отвечает
#           только на health check запросы от Render.
# ===============================================================
import os
from aiohttp import web

async def health_check(request: web.Request) -> web.Response:
    """Отвечает 'ok', если сервер запущен."""
    return web.json_response({"status": "ok"})

def main():
    app = web.Application()
    app.router.add_get("/healthz", health_check)
    port = int(os.environ.get("PORT", 10000))
    web.run_app(app, host='0.0.0.0', port=port)

if __name__ == "__main__":
    main()