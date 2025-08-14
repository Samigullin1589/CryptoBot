from aiogram import Router

router = Router(name="public")

# Подключаем обработчики безопасно, чтобы отсутствие какого-либо модуля не ломало загрузку.
# Порядок важен: start_handler раньше common_handler.
for _mod in (
    "start_handler",
    "price_handler",
    "asic_handler",
    "news_handler",
    "quiz_handler",
    "market_handler",
    "crypto_center_handler",
    "common_handler",
):
    try:
        module = __import__(f"{__package__}.{_mod}", fromlist=["router"])
        sub_router = getattr(module, "router", None)
        if sub_router is not None:
            router.include_router(sub_router)
    except Exception:
        # Избегаем падений при частичной конфигурации.
        pass
