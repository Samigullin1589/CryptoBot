# bot/services/advanced_security/inspectors/__init__.py
"""
Инспекторы для анализа различных аспектов сообщений.
"""

from bot.services.advanced_security.inspectors.text_inspector import TextInspector
from bot.services.advanced_security.inspectors.domain_inspector import DomainInspector
from bot.services.advanced_security.inspectors.phrase_inspector import PhraseInspector
from bot.services.advanced_security.inspectors.image_inspector import ImageInspector

__all__ = [
    "TextInspector",
    "DomainInspector",
    "PhraseInspector",
    "ImageInspector",
]