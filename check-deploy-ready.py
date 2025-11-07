#!/usr/bin/env python3
"""
Скрипт проверки готовности проекта к развертыванию на Render
Запустите перед деплоем: python check_deploy_ready.py
"""

import os
import sys
from pathlib import Path

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.END}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.END}")

def check_file_exists(filepath, description):
    """Проверка существования файла"""
    if Path(filepath).exists():
        print_success(f"{description}: найден")
        return True
    else:
        print_error(f"{description}: НЕ НАЙДЕН ({filepath})")
        return False

def check_requirements_txt():
    """Проверка requirements.txt"""
    if not check_file_exists('requirements.txt', 'requirements.txt'):
        return False
    
    with open('requirements.txt', 'r') as f:
        content = f.read()
        required_packages = ['aiogram', 'redis', 'aiohttp']
        
        for package in required_packages:
            if package.lower() in content.lower():
                print_success(f"  - {package} присутствует")
            else:
                print_warning(f"  - {package} отсутствует")
    
    return True

def check_env_example():
    """Проверка .env.example"""
    if not check_file_exists('.env.example', '.env.example'):
        return False
    
    with open('.env.example', 'r') as f:
        content = f.read()
        required_vars = ['BOT_TOKEN', 'ADMIN_IDS', 'REDIS_URL']
        
        for var in required_vars:
            if var in content:
                print_success(f"  - {var} присутствует")
            else:
                print_warning(f"  - {var} отсутствует")
    
    return True

def check_gitignore():
    """Проверка .gitignore"""
    if not check_file_exists('.gitignore', '.gitignore'):
        print_warning("Создайте .gitignore для защиты секретов")
        return False
    
    with open('.gitignore', 'r') as f:
        content = f.read()
        important = ['.env', '__pycache__', '*.pyc', '*.db']
        
        for item in important:
            if item in content:
                print_success(f"  - {item} игнорируется")
            else:
                print_warning(f"  - {item} не игнорируется")
    
    return True

def check_main_file():
    """Проверка основного файла бота"""
    main_files = ['bot/main.py', 'main.py']
    found = False
    
    for filepath in main_files:
        if Path(filepath).exists():
            print_success(f"Основной файл: {filepath}")
            found = True
            break
    
    if not found:
        print_error("Основной файл бота не найден")
        return False
    
    return True

def check_health_check():
    """Проверка health check сервера"""
    health_files = ['bot/health_check_server.py', 'health_check_server.py']
    found = False
    
    for filepath in health_files:
        if Path(filepath).exists():
            print_success(f"Health check сервер: {filepath}")
            
            with open(filepath, 'r') as f:
                content = f.read()
                if '/health' in content:
                    print_success("  - Endpoint /health найден")
                else:
                    print_warning("  - Endpoint /health не найден")
            
            found = True
            break
    
    if not found:
        print_warning("Health check сервер не найден (рекомендуется)")
    
    return True

def check_structure():
    """Проверка структуры проекта"""
    print_info("\nПроверка структуры проекта:")
    
    required_dirs = ['bot', 'bot/handlers', 'bot/services']
    for directory in required_dirs:
        if Path(directory).exists():
            print_success(f"  - {directory}/")
        else:
            print_warning(f"  - {directory}/ не найден")

def check_render_config():
    """Проверка конфигурации Render"""
    if check_file_exists('render.yaml', 'render.yaml'):
        with open('render.yaml', 'r') as f:
            content = f.read()
            
            checks = {
                'type: web': 'Web service',
                'type: redis': 'Redis service',
                'BOT_TOKEN': 'BOT_TOKEN variable',
                'REDIS_URL': 'REDIS_URL variable',
                'healthCheckPath': 'Health check'
            }
            
            for key, description in checks.items():
                if key in content:
                    print_success(f"  - {description} настроен")
                else:
                    print_warning(f"  - {description} не настроен")
        
        return True
    return False

def check_python_version():
    """Проверка версии Python"""
    version = sys.version_info
    print_info(f"\nТекущая версия Python: {version.major}.{version.minor}.{version.micro}")
    
    if version.major == 3 and version.minor >= 9:
        print_success("Версия Python подходит (>= 3.9)")
    else:
        print_warning("Рекомендуется Python 3.9 или выше")
    
    if check_file_exists('runtime.txt', 'runtime.txt'):
        with open('runtime.txt', 'r') as f:
            runtime_version = f.read().strip()
            print_info(f"Версия в runtime.txt: {runtime_version}")

def main():
    print(f"\n{Colors.BLUE}{'='*60}")
    print("🚀 ПРОВЕРКА ГОТОВНОСТИ К РАЗВЕРТЫВАНИЮ НА RENDER")
    print(f"{'='*60}{Colors.END}\n")
    
    checks = [
        ("Конфигурационные файлы", [
            lambda: check_file_exists('render.yaml', 'render.yaml'),
            lambda: check_file_exists('runtime.txt', 'runtime.txt'),
            check_requirements_txt,
            check_env_example,
            check_gitignore,
        ]),
        ("Структура проекта", [
            check_main_file,
            check_health_check,
            check_structure,
        ]),
        ("Настройки Render", [
            check_render_config,
        ]),
        ("Окружение", [
            check_python_version,
        ])
    ]
    
    all_passed = True
    
    for section_name, section_checks in checks:
        print(f"\n{Colors.BLUE}► {section_name}{Colors.END}")
        print("-" * 60)
        
        for check in section_checks:
            try:
                if not check():
                    all_passed = False
            except Exception as e:
                print_error(f"Ошибка при проверке: {e}")
                all_passed = False
    
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    
    if all_passed:
        print_success("\n✓ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
        print_info("\nСледующие шаги:")
        print("  1. Закоммитьте изменения: git add . && git commit -m 'Ready for deploy'")
        print("  2. Запушьте в GitHub: git push origin main")
        print("  3. Создайте Blueprint на Render.com")
        print("  4. Добавьте переменные окружения (BOT_TOKEN, ADMIN_IDS)")
        print("  5. Запустите деплой!")
    else:
        print_warning("\n⚠ ОБНАРУЖЕНЫ ПРОБЛЕМЫ!")
        print_info("\nИсправьте предупреждения и ошибки перед деплоем")
        print_info("См. DEPLOYMENT_GUIDE.md для подробной информации")
    
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}\n")

if __name__ == '__main__':
    main()