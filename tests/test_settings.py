import importlib


def test_settings_loads(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "42:AAAbbb")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("ADMIN_USER_IDS", "123")

    settings_module = importlib.import_module("bot.config.settings")
    importlib.reload(settings_module)
    s = settings_module.Settings()
    assert s.BOT_TOKEN.get_secret_value() == "42:AAAbbb"
    assert str(s.REDIS_URL).startswith("redis://localhost:6379/0")
    assert s.admin_ids == [123]

