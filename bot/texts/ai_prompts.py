# ===============================================================
# Файл: bot/texts/ai_prompts.py (ПРОДАКШН-ВЕРСИЯ 2025 - С АКТИВНЫМ ПОИСКОМ)
# Описание: Централизованное хранилище для всех промптов, используемых AI.
# ИСПРАВЛЕНИЕ: Промпт для 'alpha' полностью переработан для
#              активного использования AI-агентом поиска Google.
# ===============================================================
from typing import Dict, Any, List

def get_summary_prompt(text_to_summarize: str) -> str:
    return (
        "You are a crypto news analyst. Read the following news article and provide a very short, "
        "one-sentence summary in Russian (10-15 words max) that captures the main point. "
        f"Be concise and informative. Here is the article: \n\n{text_to_summarize}"
    )

def get_consultant_prompt() -> str:
    return (
        "You are 'CryptoBot Co-Pilot', a world-class expert engineer in cryptocurrency and ASIC mining. "
        "Your primary capability is to answer user questions accurately and helpfully in Russian. "
        "You have access to a real-time Google search tool. You MUST use it for any questions that require up-to-date information. "
        "Structure your answers with clear headings (<b>bold text</b>), bullet points, and `code` blocks for technical terms. "
        "NEVER give financial advice."
    )

def get_quiz_question_prompt() -> str:
    return (
        "Создай интересный и не слишком сложный вопрос для викторины на тему криптовалют или майнинга. "
        "Предоставь 'question', 'options' (массив из 4 строк) и 'correct_option_index' (индекс от 0 до 3). "
        "Вопрос и ответы должны быть на русском языке."
    )

def get_quiz_json_schema() -> Dict[str, Any]:
    return {
        "type": "OBJECT",
        "properties": {
            "question": {"type": "STRING"},
            "options": {"type": "ARRAY", "items": {"type": "STRING"}},
            "correct_option_index": {"type": "NUMBER"}
        },
        "required": ["question", "options", "correct_option_index"]
    }

def get_personalized_alpha_prompt(user_profile: Dict[str, List[str]], alpha_type: str) -> str:
    """
    Создает персонализированный промпт для поиска 'альфы', давая AI команду
    использовать встроенный поиск Google.
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
            "Твоя задача — выступить в роли элитного крипто-аналитика. "
            "Используй свой инструмент поиска Google, чтобы найти 3 самых перспективных и актуальных на сегодня проекта без токена, у которых высока вероятность airdrop. "
            "Для каждого проекта предоставь: 'id' (уникальный идентификатор), 'name', 'description' (короткое описание), 'status' (например, 'активный тестнет'), "
            "'tasks' (список из 3-5 конкретных действий для получения дропа) и, если возможно, 'guide_url'."
        )
    else: # mining
        task_description = (
            "Твоя задача — выступить в роли элитного майнинг-аналитика. "
            "Используй свой инструмент поиска Google, чтобы найти 3 самые актуальные и потенциально прибыльные майнинг-возможности (новые монеты, алгоритмы). "
            "Для каждой предоставь: 'id', 'name', 'description', 'algorithm', 'hardware' (рекомендуемое оборудование) и 'status'."
        )

    final_prompt = (
        f"{task_description}\n\n"
        f"Профиль интересов пользователя для дополнительного контекста и ранжирования: {profile_str}.\n"
        "ВСЕ ТЕКСТОВЫЕ ДАННЫЕ в твоем ответе ДОЛЖНЫ БЫТЬ НА РУССКОМ ЯЗЫКЕ."
    )
    
    return final_prompt