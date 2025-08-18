# bot/services/image_vision_service.py
from __future__ import annotations

from io import BytesIO
from typing import Any

from PIL import Image


class ImageVisionService:
    """
    Lightweight image analysis facade.
    - If AI provider Gemini is configured via google-generativeai,
      it will ask the model to classify spammy/advertising images and return extracted text.
    - Otherwise, optionally performs a naive OCR if pytesseract is installed.
    """

    def __init__(self, ai_content_service=None):
        self.ai = ai_content_service

        # optional local OCR
        try:  # lazy optional dependency
            import pytesseract  # noqa: F401

            self._has_tesseract = True
        except Exception:
            self._has_tesseract = False

    @staticmethod
    def _img_from_bytes(photo_bytes: bytes) -> Image.Image:
        return Image.open(BytesIO(photo_bytes)).convert("RGB")

    def _ocr_local(self, img: Image.Image) -> str:
        if not self._has_tesseract:
            return ""
        try:
            import pytesseract

            return pytesseract.image_to_string(img, lang="eng+rus")
        except Exception:
            return ""

    async def analyze(self, photo_bytes: bytes) -> tuple[bool, dict[str, Any]]:
        """
        Returns tuple (is_spam, details)
        details includes { 'extracted_text': str, 'model': 'gemini'|'tesseract'|None, 'explanation': str }
        """
        img = self._img_from_bytes(photo_bytes)

        # Try AI provider first (Gemini Vision via your AIContentService)
        if self.ai and getattr(self.ai, "analyze_image_for_spam", None):
            try:
                ok, explanation, extracted = await self.ai.analyze_image_for_spam(img)
                return bool(ok), {
                    "extracted_text": extracted or "",
                    "model": "gemini",
                    "explanation": explanation or "",
                }
            except Exception:
                pass  # hard-failover to local OCR

        # Fallback: local OCR (very naive)
        text = self._ocr_local(img)
        is_spam = False
        exp = ""

        text_l = (text or "").lower()
        for kw in (
            "успей",
            "бонус",
            "подписывайся",
            "промокод",
            "зарегистрируйся",
            "выплаты",
            "онлайн",
            "ставки",
            "казино",
        ):
            if kw in text_l:
                is_spam = True
                exp = f"Keyword '{kw}' found in OCR"
                break

        return is_spam, {
            "extracted_text": text or "",
            "model": "tesseract" if self._has_tesseract else None,
            "explanation": exp,
        }
