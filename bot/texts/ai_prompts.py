# ===============================================================
# Файл: bot/texts/ai_prompts.py (ПРОДАКШН-ВЕРСИЯ 2025 - ФИНАЛЬНАЯ)
# Описание: Централизованное хранилище для всех промптов, используемых AI.
# ИСПРАВЛЕНИЕ: Добавлена недостающая функция get_quiz_json_schema для
#              структурированной генерации вопросов викторины.
# ===============================================================
from typing import Dict, Any, List

def get_summary_prompt(text_to_summarize: str) -> str:
    """Промпт для генерации краткого саммари новости."""
    return (
        "You are a crypto news analyst. Read the following news article and provide a very short, "
        "one-sentence summary in Russian (10-15 words max) that captures the main point. "
        f"Be concise and informative. Here is the article: \n\n{text_to_summarize}"
    )

def get_consultant_prompt() -> str:
    """Системный промпт для AI-консультанта с функцией поиска."""
    return (
        "You are 'CryptoBot Co-Pilot', a world-class expert engineer in cryptocurrency and ASIC mining. "
        "Your primary capability is to answer user questions accurately and helpfully in Russian. "
        "You have access to a real-time Google search tool. You MUST use it for any questions that require up-to-date information (like prices, market caps, news, project statuses) or for topics you are not familiar with. "
        "Your knowledge base reflects mid-2025 market conditions. "
        "Structure your answers with clear headings (<b>bold text</b>), bullet points, and `code` blocks for technical terms. "
        "Always start by directly addressing the user's question. "
        "Conclude your answer with a '<b>Вывод:</b>' section. "
        "NEVER give financial advice. If a user asks for it, provide objective data and comparisons, and include a disclaimer that this is not financial advice. "
        "If a question is unrelated to crypto, blockchain, or finance, politely decline to answer."
    )

def get_quiz_question_prompt() -> str:
    """Промпт для генерации вопроса для викторины."""
    return (
        "Создай интересный и не слишком сложный вопрос для викторины на тему криптовалют или майнинга. "
        "Предоставь 'question' (вопрос), 'options' (массив из 4 строк: 3 неверных ответа и 1 верный) и "
        "'correct_option_index' (индекс правильного ответа от 0 до 3). "
        "Вопрос и ответы должны быть на русском языке. Ответы не должны быть слишком очевидными."
    )

def get_quiz_json_schema() -> Dict[str, Any]:
    """
    Возвращает JSON-схему, которой должен следовать AI при генерации вопроса викторины.
    """
    return {
        "type": "OBJECT",
        "properties": {
            "question": {
                "type": "STRING",
                "description": "Текст вопроса викторины на русском языке."
            },
            "options": {
                "type": "ARRAY",
                "description": "Массив из ровно 4-х строк с вариантами ответа.",
                "items": {"type": "STRING"}
            },
            "correct_option_index": {
                "type": "NUMBER",
                "description": "Индекс (от 0 до 3) правильного ответа в массиве 'options'."
            }
        },
        "required": ["question", "options", "correct_option_index"]
    }


def get_personalized_alpha_prompt(news_context: str, user_profile: Dict[str, List[str]], alpha_type: str) -> str:
    """
    Создает персонализированный промпт для поиска 'альфы' (ценной информации).
    """
    tags = user_profile.get('tags')
    coins = user_profile.get('interacted_coins')
    
    profile_parts = []
    if tags:
        profile_parts.append(f"темы (теги): {', '.join(tags)}")
    if coins:
        profile_parts.append(f"монеты, с которыми он взаимодействовал: {', '.join(coins)}")

    profile_str = ", ".join(profile_parts) if profile_parts else "общие интересы в криптовалюте"

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

    final_prompt = (
        "Ты — элитный крипто-аналитик. Твоя задача — найти персонализированные инвестиционные возможности, основываясь на профиле интересов пользователя и свежем новостном контексте. "
        "ВСЕ ТЕКСТОВЫЕ ДАННЫЕ в твоем ответе ДОЛЖНЫ БЫТЬ НА РУССКОМ ЯЗЫКЕ.\n\n"
        f"ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ: Пользователь интересуется: {profile_str}.\n\n"
        f"ЗАДАЧА: {task_description}\n\n"
        "Если в новостях недостаточно информации для поиска релевантных возможностей, верни пустой массив.\n\n"
        f"НОВОСТНОЙ КОНТЕКСТ ДЛЯ АНАЛИЗА:\n{news_context}"
    )
    
    return final_prompt