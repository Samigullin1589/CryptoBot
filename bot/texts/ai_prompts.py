# ===============================================================
# Файл: bot/texts/ai_prompts.py (ПРОДАКШН-ВЕРСИЯ 2025 - ОКОНЧАТЕЛЬНАЯ v3)
# ===============================================================
from typing import Dict

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

def get_airdrop_alpha_prompt(news_context: str) -> str:
    """Промпт для поиска Airdrop-возможностей в новостном контексте."""
    return (
        "Действуй как крипто-исследователь. На основе предоставленных новостей, определи 3 самых перспективных проекта без токена, у которых вероятен airdrop. "
        "Для каждого проекта предоставь: 'id' (уникальный идентификатор в одно слово), 'name', 'description' (короткое описание), 'status', "
        "'tasks' (список из 3-5 действий) и 'guide_url'. "
        "ВСЕ ТЕКСТОВЫЕ ДАННЫЕ ДОЛЖНЫ БЫТЬ НА РУССКОМ ЯЗЫКЕ. Если информации недостаточно, верни пустой массив. Контекст:\n\n"
        f"{news_context}"
    )

def get_mining_alpha_prompt(news_context: str) -> str:
    """Промпт для поиска майнинг-возможностей в новостном контексте."""
    return (
        "Действуй как майнинг-аналитик. На основе предоставленных новостей, определи 3 самые актуальные майнинг-возможности (ASIC/GPU/CPU). "
        "Для каждой предоставь: 'id', 'name', 'description', 'algorithm', 'hardware' (рекомендуемое оборудование), 'status' и 'guide_url'. "
        "ВСЕ ТЕКСТОВЫЕ ДАННЫЕ ДОЛЖНЫ БЫТЬ НА РУССКОМ ЯЗЫКЕ. Если информации недостаточно, верни пустой массив. Контекст:\n\n"
        f"{news_context}"
    )

def get_quiz_question_prompt() -> str:
    """Промпт для генерации вопроса для викторины."""
    return (
        "Создай интересный и не слишком сложный вопрос для викторины на тему криптовалют или майнинга. "
        "Предоставь 'question' (вопрос), 'options' (массив из 4 строк: 3 неверных ответа и 1 верный) и "
        "'correct_option_index' (индекс правильного ответа от 0 до 3). "
        "Вопрос и ответы должны быть на русском языке. Ответы не должны быть слишком очевидными."
    )

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
