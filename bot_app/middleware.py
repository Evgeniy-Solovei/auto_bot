from __future__ import annotations

import os
from typing import Any, Awaitable, Callable

import httpx
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from dotenv import load_dotenv

from bot_app.api_client import api_client


load_dotenv()


class AccessMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self.access_control = os.getenv("BOT_ACCESS_CONTROL", "False").lower() == "true"

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not self.access_control:
            return await handler(event, data)

        user = data.get("event_from_user")
        if not user:
            return None

        try:
            access = await api_client.check_access(user.id)
        except httpx.HTTPError:
            await self._answer(event, "Не удалось проверить доступ. Попробуйте позже.")
            return None

        if not access.get("allowed"):
            await self._answer(event, "Доступ к боту не выдан. Передайте администратору ваш Telegram ID: " + str(user.id))
            return None

        data["access_user"] = access
        return await handler(event, data)

    async def _answer(self, event: TelegramObject, text: str) -> None:
        if isinstance(event, Message):
            await event.answer(text)
        elif isinstance(event, CallbackQuery):
            if event.message:
                await event.message.answer(text)
            await event.answer()
