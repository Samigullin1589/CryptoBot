import logging
import backoff
import aiohttp
from aiohttp import ClientError, ClientTimeout

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

def setup_logging():
    """Просто чтобы функция была, если вы захотите усложнить логирование."""
    pass

logger = logging.getLogger(__name__)

# Это декоратор, который будет повторять запрос в случае определенных ошибок
@backoff.on_exception(backoff.expo,
                      (ClientError, asyncio.TimeoutError),
                      max_tries=3,
                      max_time=60,
                      on_giveup=lambda details: logger.error(
                          f"Запрос не удался после {details['tries']} попыток. "
                          f"URL: {details['args'][1]}, Ошибка: {details['exception']}"
                      ))
async def make_request(session: aiohttp.ClientSession, url: str, method: str = "GET", **kwargs) -> dict | str | None:
    """
    Универсальная функция для выполнения асинхронных HTTP-запросов с тайм-аутом и повторными попытками.
    """
    timeout = ClientTimeout(total=10) # 10-секундный тайм-аут для запроса
    try:
        async with session.request(method, url, timeout=timeout, **kwargs) as response:
            if response.status == 200:
                # Пытаемся декодировать JSON, если не получается - возвращаем текст
                try:
                    return await response.json()
                except aiohttp.ContentTypeError:
                    return await response.text()
            else:
                logger.warning(f"Ошибка запроса к {url}. Статус: {response.status}, Ответ: {await response.text()}")
                # Вызываем исключение, чтобы backoff сработал
                response.raise_for_status()
    except asyncio.TimeoutError:
        logger.warning(f"Тайм-аут при запросе к {url}")
        raise  # Перевыбрасываем исключение для backoff
    except ClientError as e:
        logger.error(f"Ошибка клиента при запросе к {url}: {e}")
        raise  # Перевыбрасываем исключение для backoff
    return None