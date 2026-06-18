from __future__ import annotations

import asyncio
import os
from time import monotonic
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
        self.callback_cooldown = float(os.getenv("BOT_CALLBACK_COOLDOWN_SECONDS", "1.0"))
        self._callback_locks: dict[tuple[int, int, int], asyncio.Lock] = {}
        self._callback_last: dict[tuple[int, int, int], float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, CallbackQuery):
            return await self._handle_callback(handler, event, data)
        return await self._handle_access(handler, event, data)

    async def _handle_callback(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        key = self._callback_key(event)
        now = monotonic()
        last_processed = self._callback_last.get(key, 0.0)
        if now - last_processed < self.callback_cooldown:
            await event.answer("Кнопка уже обработана.")
            return None

        lock = self._callback_locks.setdefault(key, asyncio.Lock())
        if lock.locked():
            await event.answer("Кнопка уже обрабатывается.")
            return None

        await lock.acquire()
        try:
            result = await self._handle_access(handler, event, data)
            self._callback_last[key] = monotonic()
            self._cleanup_callback_guards()
            return result
        finally:
            lock.release()

    async def _handle_access(
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

    def _callback_key(self, event: CallbackQuery) -> tuple[int, int, int]:
        user_id = event.from_user.id if event.from_user else 0
        message = event.message
        chat_id = message.chat.id if message and message.chat else 0
        message_id = message.message_id if message else 0
        return user_id, chat_id, message_id

    def _cleanup_callback_guards(self) -> None:
        if len(self._callback_last) <= 5000:
            return
        cutoff = monotonic() - 60
        stale_keys = [key for key, updated_at in self._callback_last.items() if updated_at < cutoff]
        for key in stale_keys:
            self._callback_last.pop(key, None)
            lock = self._callback_locks.get(key)
            if lock and not lock.locked():
                self._callback_locks.pop(key, None)

    async def _answer(self, event: TelegramObject, text: str) -> None:
        if isinstance(event, Message):
            await event.answer(text)
        elif isinstance(event, CallbackQuery):
            if event.message:
                await event.message.answer(text)
            await event.answer()
