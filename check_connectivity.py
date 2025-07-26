# ===============================================================
# Файл: check_connectivity.py
# Описание: Простой скрипт для диагностики сетевых проблем на сервере.
# Запустите его командой: python check_connectivity.py
# ===============================================================

import socket
import ssl
import requests

# Список хостов, которые мы должны "видеть"
HOSTS_TO_CHECK = [
    "min-api.cryptocompare.com",
    "api.coingecko.com",
    "mempool.space",
    "api.blockchair.com",
    "chain.api.btc.com",
    "google.com" # Проверяем доступ к внешнему миру в целом
]

def check_host(hostname: str):
    """Проверяет разрешение DNS и доступность порта 443 для хоста."""
    print(f"--- Проверка {hostname} ---")
    
    # Шаг 1: Проверка DNS
    try:
        ip_address = socket.gethostbyname(hostname)
        print(f"✅ [DNS]     : Успешно. {hostname} -> {ip_address}")
    except socket.gaierror:
        print(f"❌ [DNS]     : КРИТИЧЕСКИЙ СБОЙ. Не удалось определить IP-адрес для {hostname}.")
        print(f"            : Это главная причина ошибки 'Name or service not known'.")
        return

    # Шаг 2: Проверка TCP-соединения к порту 443 (HTTPS)
    try:
        # Устанавливаем короткий таймаут, чтобы не ждать долго
        socket.setdefaulttimeout(5)
        
        # Создаем TCP сокет
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Пытаемся подключиться
        sock.connect((hostname, 443))
        sock.close()
        print(f"✅ [TCP:443] : Успешно. Порт 443 (HTTPS) открыт и доступен.")
    except Exception as e:
        print(f"❌ [TCP:443] : СБОЙ. Не удалось подключиться к {hostname} на порт 443.")
        print(f"            : Возможная причина - блокировка файрволом.")
        print(f"            : Ошибка: {e}")
        return

    # Шаг 3: Проверка полного HTTPS запроса (для продвинутой диагностики)
    try:
        response = requests.get(f"https://{hostname}", timeout=10)
        if 200 <= response.status_code < 500: # Любой ответ, кроме серверной ошибки
             print(f"✅ [HTTPS]   : Успешно. Сайт ответил со статусом {response.status_code}.")
        else:
             print(f"⚠️  [HTTPS]   : Ошибка. Сайт ответил с кодом {response.status_code}.")
    except requests.exceptions.RequestException as e:
        print(f"❌ [HTTPS]   : СБОЙ. Не удалось выполнить HTTPS запрос.")
        print(f"            : Ошибка: {e}")


if __name__ == "__main__":
    print("="*50)
    print("Запуск скрипта для диагностики сетевого подключения...")
    print("="*50)
    for host in HOSTS_TO_CHECK:
        check_host(host)
        print("-" * 50)
