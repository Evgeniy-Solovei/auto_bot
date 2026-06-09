from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

import httpx
from dotenv import load_dotenv


load_dotenv(override=True)


class ApiClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("BOT_API_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/")
        self.api_key = os.getenv("INTERNAL_API_KEY", "")

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0, headers=self._headers()) as client:
            response = await client.request(method, path, **kwargs)
            response.raise_for_status()
            if response.content:
                return response.json()
            return None

    async def _download(self, path: str) -> bytes:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0, headers=self._headers()) as client:
            response = await client.get(path)
            response.raise_for_status()
            return response.content

    async def register_user(self, telegram_id: int, username: str, full_name: str) -> dict:
        return await self._request(
            "POST",
            "/telegram-users/",
            json={"telegram_id": telegram_id, "username": username, "full_name": full_name},
        )

    async def check_access(self, telegram_id: int) -> dict:
        return await self._request("GET", "/telegram-users/access/", params={"telegram_id": telegram_id})

    async def list_cars(self, status: str | None = None) -> list[dict]:
        params = {"status": status} if status else None
        return await self._request("GET", "/cars/", params=params)

    async def get_car(self, car_id: int) -> dict:
        return await self._request("GET", f"/cars/{car_id}/")

    async def create_car(self, payload: dict) -> dict:
        return await self._request("POST", "/cars/", json=payload)

    async def update_car(self, car_id: int, payload: dict) -> dict:
        return await self._request("PATCH", f"/cars/{car_id}/", json=payload)

    async def update_car_status(self, car_id: int, status: str) -> dict:
        return await self.update_car(car_id, {"status": status})

    async def update_car_stage(self, car_id: int, repair_stage: str) -> dict:
        return await self.update_car(car_id, {"repair_stage": repair_stage})

    async def list_defect_photos(self, car_id: int | None = None) -> list[dict]:
        params = {"car_id": car_id} if car_id else None
        return await self._request("GET", "/defect-photos/", params=params)

    async def create_defect_photo(
        self,
        car_id: int,
        photo_file_id: str,
        created_by_telegram_id: int,
        comment: str = "",
    ) -> dict:
        return await self._request(
            "POST",
            "/defect-photos/",
            json={
                "car_id": car_id,
                "photo_file_id": photo_file_id,
                "created_by_telegram_id": created_by_telegram_id,
                "comment": comment,
            },
        )

    async def list_expenses(self, car_id: int | None = None, employee_telegram_id: int | None = None) -> list[dict]:
        params = {}
        if car_id:
            params["car_id"] = car_id
        if employee_telegram_id:
            params["employee_telegram_id"] = employee_telegram_id
        return await self._request("GET", "/expenses/", params=params or None)

    async def create_expense(
        self,
        car_id: int,
        amount: Decimal,
        description: str,
        employee_telegram_id: int,
        category_id: int | None = None,
        category_name: str = "",
        currency: str = "BYN",
        comment: str = "",
        receipt_photo_file_id: str = "",
    ) -> dict:
        payload = {
            "car_id": car_id,
            "amount": str(amount),
            "currency": currency,
            "description": description,
            "employee_telegram_id": employee_telegram_id,
            "comment": comment,
            "receipt_photo_file_id": receipt_photo_file_id,
        }
        if category_id:
            payload["category_id"] = category_id
        elif category_name:
            payload["category_name"] = category_name
        return await self._request("POST", "/expenses/", json=payload)

    async def update_expense(self, expense_id: int, payload: dict) -> dict:
        return await self._request("PATCH", f"/expenses/{expense_id}/", json=payload)

    async def delete_expense(self, expense_id: int) -> None:
        await self._request("DELETE", f"/expenses/{expense_id}/")

    async def list_categories(self) -> list[dict]:
        return await self._request("GET", "/categories/")

    async def summary(self) -> list[dict]:
        return await self._request("GET", "/reports/summary/")

    async def download_report(self) -> bytes:
        return await self._download("/reports/export/")


api_client = ApiClient()
