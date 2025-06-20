# Файл: bot/utils/async_cache_local.py
# Локальная копия библиотеки async-cache

import asyncio
from functools import wraps

def cached(cache):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                # Преобразуем аргументы в ключ, который можно хэшировать
                key = str(args) + str(sorted(kwargs.items()))
                if key in cache:
                    return cache[key]
                
                result = await func(*args, **kwargs)
                cache[key] = result
                return result
            except TypeError:
                # Если что-то пошло не так с ключом, просто выполняем без кэша
                return await func(*args, **kwargs)
        return wrapper
    return decorator