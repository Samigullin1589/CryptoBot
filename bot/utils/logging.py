import sys
from loguru import logger
from src.bot.config import AppConfig

def setup_logging(config: AppConfig):
    """
    Настраивает логгер loguru для вывода в консоль с форматированием и цветом.
    """
    logger.remove()
    logger.add(
        sys.stderr,
        level=config.log_level.upper(),
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        ),
        colorize=True,
    )
    logger.info("Система логирования успешно настроена.")