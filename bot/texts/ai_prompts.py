# ===============================================================
# Файл: bot/texts/ai_prompts.py (ПРОДАКШН-ВЕРСИЯ 2025 - ФИНАЛЬНАЯ)
# Описание: Централизованное хранилище для всех промптов, используемых AI.
# ИСПРАВЛЕНИЕ: Добавлена недостающая функция get_personalized_alpha_prompt.
# Старые, неперсонализированные промпты удалены для чистоты кода.
# ===============================================================
from typing import Dict, Any, List

def get_summary_prompt(text_to_summarize: str) -> str:
    """Промпт для генерации краткого саммари новости."""
    return (
        "You are a crypto news analyst. Read the following news article and provide a very short, "
        "one-sentence summary in Russian (10-15 words max) that captures the main point. "
        f"Be concise and informative. Here is the article: \n\n{text_to_summarize}"
    )

def get_consultant_prompt(user_question: str) -> str:
    """Системный промпт для AI-консультанта."""
    return (
        "You are a helpful and friendly crypto assistant bot. Your name is CryptoBot. "
        "Answer the user's question clearly and concisely in Russian. "
        "Do not give financial advice. You can use emojis to make the conversation more engaging. "
        "Your primary knowledge is in cryptocurrencies and mining. Avoid answering questions on other topics. "
        f"Here is the user's question: {user_question}"
    )

def get_quiz_question_prompt() -> str:
    """Промпт для генерации вопроса для викторины."""
    return (
        "Создай интересный и не слишком сложный вопрос для викторины на тему криптовалют или майнинга. "
        "Предоставь 'question' (вопрос), 'options' (массив из 4 строк: 3 неверных ответа и 1 верный) и "
        "'correct_option_index' (индекс правильного ответа от 0 до 3). "
        "Вопрос и ответы должны быть на русском языке. Ответы не должны быть слишком очевидными."
    )

# ИСПРАВЛЕНО: Добавлена единая функция для генерации персонализированных промптов.
def get_personalized_alpha_prompt(news_context: str, user_profile: Dict[str, List[str]], alpha_type: str) -> str:
    """
    Создает персонализированный промпт для поиска 'альфы' (ценной информации).

    :param news_context: Строка с последними новостями для анализа.
    :param user_profile: Словарь с интересами пользователя (теги и монеты).
    :param alpha_type: Тип искомой информации ('airdrop' или 'mining').
    :return: Финальный промпт для AI.
    """
    # 1. Формируем строку с профилем пользователя
    tags = user_profile.get('tags')
    coins = user_profile.get('interacted_coins')
    
    profile_parts = []
    if tags:
        profile_parts.append(f"темы (теги): {', '.join(tags)}")
    if coins:
        profile_parts.append(f"монеты, с которыми он взаимодействовал: {', '.join(coins)}")

    profile_str = ", ".join(profile_parts) if profile_parts else "общие интересы в криптовалюте"

    # 2. Выбираем конкретную задачу на основе alpha_type
    if alpha_type == "airdrop":
        task_description = (
            "Твоя конкретная задача — найти 3 самых перспективных проекта без токена, у которых вероятен airdrop. "
            "Удели особое внимание проектам, связанным с интересами пользователя. "
            "Для каждого проекта предоставь: 'id' (уникальный идентификатор в одно слово), 'name', 'description' (короткое описание), 'status', "
            "'tasks' (список из 3-5 конкретных действий для получения дропа) и 'guide_url'."
        )
    elif alpha_type == "mining":
        task_description = (
            "Твоя конкретная задача — найти 3 самые актуальные майнинг-возможности (ASIC/GPU/CPU). "
            "Отдай приоритет возможностям, которые соответствуют интересам пользователя. "
            "Для каждой предоставь: 'id', 'name', 'description', 'algorithm', 'hardware' (рекомендуемое оборудование), 'status' и 'guide_url'."
        )
    else:
        task_description = "Проанализируй новости на предмет общих инвестиционных возможностей."

    # 3. Собираем финальный промпт
    final_prompt = (
        "Ты — элитный крипто-аналитик. Твоя задача — найти персонализированные инвестиционные возможности, основываясь на профиле интересов пользователя и свежем новостном контексте. "
        "ВСЕ ТЕКСТОВЫЕ ДАННЫЕ в твоем ответе ДОЛЖНЫ БЫТЬ НА РУССКОМ ЯЗЫКЕ.\n\n"
        f"ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ: Пользователь интересуется: {profile_str}.\n\n"
        f"ЗАДАЧА: {task_description}\n\n"
        "Если в новостях недостаточно информации для поиска релевантных возможностей, верни пустой массив.\n\n"
        f"НОВОСТНОЙ КОНТЕКСТ ДЛЯ АНАЛИЗА:\n{news_context}"
    )
    
    return final_prompt

# --- Функции для получения JSON-схем остаются без изменений ---

def get_airdrop_json_schema() -> Dict:
    """JSON-схема для Airdrop-возможностей."""
    return {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "id": {"type": "STRING"},
                "name": {"type": "STRING"},
                "description": {"type": "STRING"},
                "status": {"type": "STRING"},
                "tasks": {"type": "ARRAY", "items": {"type": "STRING"}},
                "guide_url": {"type": "STRING"}
            },
            "required": ["id", "name", "description", "status", "tasks"]
        }
    }

def get_mining_json_schema() -> Dict:
    """JSON-схема для майнинг-возможностей."""
    return {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "id": {"type": "STRING"},
                "name": {"type": "STRING"},
                "description": {"type": "STRING"},
                "algorithm": {"type": "STRING"},
                "hardware": {"type": "STRING"},
                "status": {"type": "STRING"},
                "guide_url": {"type": "STRING"}
            },
            "required": ["id", "name", "description", "algorithm", "hardware"]
        }
    }

def get_quiz_json_schema() -> Dict:
    """JSON-схема для вопроса викторины."""
    return {
        "type": "OBJECT",
        "properties": {
            "question": {"type": "STRING"},
            "options": {"type": "ARRAY", "items": {"type": "STRING"}},
            "correct_option_index": {"type": "INTEGER"}
        },
        "required": ["question", "options", "correct_option_index"]
    }
