import asyncio
from functools import wraps

def cached(cache):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                key = str(args) + str(sorted(kwargs.items()))
                if key in cache:
                    return cache[key]

                result = await func(*args, **kwargs)
                cache[key] = result
                return result
            except TypeError:
                return await func(*args, **kwargs)
        return wrapper
    return decorator
