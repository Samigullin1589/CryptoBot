import os
from bot.config.settings import Settings

def test_settings_loads():
    s = Settings()
    assert s.BOT_TOKEN.get_secret_value() == os.environ["BOT_TOKEN"]
    assert str(s.REDIS_URL).startswith(os.environ["REDIS_URL"])
