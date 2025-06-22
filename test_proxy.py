import asyncio
import aiohttp

# Прокси, который вы предоставили
PROXY_URL = "http://mh0a3lpxyu-res-country-US-state-4736286-city-4684888-hold-session-session-68579631e679b:9CgE9HtEuHel1Jbq@93.190.143.48:9999"

# Целевой URL, который мы не могли получить напрямую
TARGET_URL = "https://whattomine.com/asics.json"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
}

async def main():
    print(f"--- Тестирую подключение к {TARGET_URL} через прокси... ---")
    try:
        # Используем aiohttp для асинхронного запроса
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            # Передаем URL прокси в параметре 'proxy'
            # Увеличим таймаут до 45 секунд, так как прокси могут быть медленнее
            async with session.get(TARGET_URL, proxy=PROXY_URL, timeout=45) as response:
                status = response.status
                print(f"Статус-код ответа: {status}")

                if status == 200:
                    print("\nУСПЕХ! Данные через прокси получены.")
                    data = await response.json(content_type=None) # Игнорируем content-type для надежности
                    asic_count = len(data.get('asics', []))
                    print(f"Удалось загрузить информацию о {asic_count} ASIC-майнерах.")
                else:
                    print(f"\nОШИБКА! Сервер ответил с ошибкой.")
                    print("Текст ответа:", await response.text())

    except aiohttp.ClientConnectorError as e:
        print(f"\nКРИТИЧЕСКАЯ ОШИБКА ПОДКЛЮЧЕНИЯ: Не удалось подключиться к прокси-серверу.")
        print(f"Детали: {e}")
    except Exception as e:
        print(f"\nКРИТИЧЕСКАЯ ОШИБКА: Произошло исключение во время выполнения скрипта.")
        print(f"Детали: {e}")

if __name__ == "__main__":
    asyncio.run(main())