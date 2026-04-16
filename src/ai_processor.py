"""AI-генерация фото на документы через BotHub (OpenAI-совместимый клиент)."""

import base64
import io
import logging

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)
from PIL import Image

from src.constants import AI_PROMPT

logger = logging.getLogger(__name__)

BOTHUB_BASE_URL = "https://openai.bothub.chat/v1"
MODEL = "gemini-3-pro-image-preview"
MAX_DIMENSION = 1024


class AIProcessingError(Exception):
    pass


def _compress_image(image_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


class AIProcessor:
    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=BOTHUB_BASE_URL,
            timeout=120.0,
        )

    @property
    def is_configured(self) -> bool:
        return bool(self._client.api_key)

    async def generate_document_photo(self, image_bytes: bytes) -> bytes:
        if not self.is_configured:
            raise AIProcessingError("BOTHUB_API_KEY не задан в .env")

        b64_image = _compress_image(image_bytes)

        try:
            response = await self._client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": AI_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{b64_image}",
                                },
                            },
                        ],
                    },
                ],
                extra_body={
                    "image_config": {
                        "aspect_ratio": "3:4",
                        "image_size": "2K",
                    },
                    "response_modalities": ["IMAGE", "TEXT"],
                },
            )
        except AuthenticationError:
            raise AIProcessingError("Неверный BOTHUB_API_KEY. Проверь ключ и попробуй ещё раз.")
        except RateLimitError:
            raise AIProcessingError("Лимит запросов исчерпан. Попробуй позже.")
        except APITimeoutError:
            raise AIProcessingError("Таймаут при обработке изображения. Попробуй ещё раз.")
        except APIConnectionError:
            raise AIProcessingError("Не удалось подключиться к AI-сервису. Попробуй ещё раз.")
        except BadRequestError:
            raise AIProcessingError("AI-сервис отклонил запрос. Попробуй другое фото.")
        except APIStatusError as e:
            # e.status_code is usually available; keep message short for user
            raise AIProcessingError(f"Ошибка AI-сервиса ({getattr(e, 'status_code', '???')}). Попробуй ещё раз.")
        except Exception as e:
            logger.exception("BotHub API call failed")
            raise AIProcessingError("Неожиданная ошибка AI-сервиса. Попробуй ещё раз.")

        message = response.choices[0].message

        if hasattr(message, "images") and message.images:
            img = message.images[0]
            url = img["image_url"]["url"] if isinstance(img, dict) else img.image_url.url
            b64_data = url.split(",", 1)[1]
            return base64.b64decode(b64_data)

        raise AIProcessingError("AI не вернул изображение")

    async def close(self) -> None:
        await self._client.close()
