from decimal import Decimal

from rest_framework import serializers

from core.models import Car, DefectPhoto, Expense


class TelegramUserInputSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField()
    username = serializers.CharField(required=False, allow_blank=True, max_length=150)
    full_name = serializers.CharField(required=False, allow_blank=True, max_length=255)


class CarInputSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    brand = serializers.CharField(required=False, allow_blank=True, max_length=120)
    model = serializers.CharField(required=False, allow_blank=True, max_length=120)
    vin_or_plate = serializers.CharField(required=False, allow_blank=True, max_length=64)
    vin = serializers.CharField(required=False, allow_blank=True, max_length=64)
    status = serializers.ChoiceField(required=False, choices=Car.Status.choices)
    repair_stage = serializers.ChoiceField(required=False, choices=Car.RepairStage.choices)
    description = serializers.CharField(required=False, allow_blank=True)
    car_photo_file_id = serializers.CharField(required=False, allow_blank=True, max_length=1024)
    car_photo_path = serializers.CharField(required=False, allow_blank=True, max_length=1024)
    vin_photo_file_id = serializers.CharField(required=False, allow_blank=True, max_length=1024)
    vin_photo_path = serializers.CharField(required=False, allow_blank=True, max_length=1024)
    photos = serializers.ListField(child=serializers.DictField(), required=False)
    created_by_telegram_id = serializers.IntegerField(required=False)


class CarPatchSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, max_length=255)
    brand = serializers.CharField(required=False, allow_blank=True, max_length=120)
    model = serializers.CharField(required=False, allow_blank=True, max_length=120)
    vin_or_plate = serializers.CharField(required=False, allow_blank=True, max_length=64)
    vin = serializers.CharField(required=False, allow_blank=True, max_length=64)
    status = serializers.ChoiceField(required=False, choices=Car.Status.choices)
    repair_stage = serializers.ChoiceField(required=False, choices=Car.RepairStage.choices)
    description = serializers.CharField(required=False, allow_blank=True)
    car_photo_file_id = serializers.CharField(required=False, allow_blank=True, max_length=1024)
    car_photo_path = serializers.CharField(required=False, allow_blank=True, max_length=1024)
    vin_photo_file_id = serializers.CharField(required=False, allow_blank=True, max_length=1024)
    vin_photo_path = serializers.CharField(required=False, allow_blank=True, max_length=1024)


class CarStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Car.Status.choices)


class CarStageSerializer(serializers.Serializer):
    repair_stage = serializers.ChoiceField(choices=Car.RepairStage.choices)


class DefectPhotoInputSerializer(serializers.Serializer):
    car_id = serializers.IntegerField()
    photo_file_id = serializers.CharField(required=False, allow_blank=True, max_length=1024)
    image_path = serializers.CharField(required=False, allow_blank=True, max_length=1024)
    photos = serializers.ListField(child=serializers.DictField(), required=False)
    comment = serializers.CharField(required=False, allow_blank=True)
    created_by_telegram_id = serializers.IntegerField(required=False)


class ExpenseInputSerializer(serializers.Serializer):
    car_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    currency = serializers.ChoiceField(required=False, choices=[("BYN", "BYN"), ("USD", "USD")])
    description = serializers.CharField(max_length=255)
    category_id = serializers.IntegerField(required=False, allow_null=True)
    category_name = serializers.CharField(required=False, allow_blank=True, max_length=120)
    employee_telegram_id = serializers.IntegerField(required=False)
    comment = serializers.CharField(required=False, allow_blank=True)
    receipt_photo_file_id = serializers.CharField(required=False, allow_blank=True, max_length=1024)
    receipt_photo_path = serializers.CharField(required=False, allow_blank=True, max_length=1024)
    photos = serializers.ListField(child=serializers.DictField(), required=False)


class ExpensePatchSerializer(serializers.Serializer):
    amount = serializers.DecimalField(required=False, max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    currency = serializers.ChoiceField(required=False, choices=[("BYN", "BYN"), ("USD", "USD")])
    description = serializers.CharField(required=False, max_length=255)
    category_id = serializers.IntegerField(required=False, allow_null=True)
    category_name = serializers.CharField(required=False, allow_blank=True, max_length=120)
    comment = serializers.CharField(required=False, allow_blank=True)
    receipt_photo_file_id = serializers.CharField(required=False, allow_blank=True, max_length=1024)
    receipt_photo_path = serializers.CharField(required=False, allow_blank=True, max_length=1024)
    updated_by_telegram_id = serializers.IntegerField(required=False)


def serialize_car(car, total=None, expenses_count=None, total_by_currency=None) -> dict:
    return {
        "id": car.id,
        "title": car.title,
        "brand": car.brand,
        "model": car.model,
        "make_model": car.vehicle_label,
        "vin_or_plate": car.vin_or_plate or car.vin,
        "vin": car.vin_or_plate or car.vin,
        "status": car.status,
        "status_display": car.get_status_display(),
        "repair_stage": car.repair_stage,
        "repair_stage_display": car.get_repair_stage_display(),
        "description": car.description,
        "car_photo_file_id": car.car_photo_file_id,
        "car_photo_url": car.car_photo.url if car.car_photo else "",
        "vin_photo_file_id": car.vin_photo_file_id,
        "vin_photo_url": car.vin_photo.url if car.vin_photo else "",
        "created_by": str(car.created_by) if car.created_by_id else None,
        "created_at": car.created_at,
        "updated_at": car.updated_at,
        "completed_at": car.completed_at,
        "archived_at": car.archived_at,
        "total_expenses": total,
        "total_expenses_by_currency": total_by_currency or {},
        "expenses_count": expenses_count,
    }


def serialize_expense(expense: Expense) -> dict:
    return {
        "id": expense.id,
        "car_id": expense.car_id,
        "car": str(expense.car),
        "amount": expense.amount,
        "currency": expense.currency,
        "description": expense.description,
        "category": expense.category.name if expense.category_id else None,
        "category_id": expense.category_id,
        "employee": str(expense.employee) if expense.employee_id else None,
        "employee_id": expense.employee_id,
        "comment": expense.comment,
        "receipt_photo_file_id": expense.receipt_photo_file_id,
        "receipt_photo_url": expense.receipt_photo.url if expense.receipt_photo else "",
        "spent_at": expense.spent_at,
        "created_at": expense.created_at,
        "updated_at": expense.updated_at,
        "updated_by": str(expense.updated_by) if expense.updated_by_id else None,
    }


def serialize_defect_photo(photo: DefectPhoto) -> dict:
    return {
        "id": photo.id,
        "car_id": photo.car_id,
        "car": str(photo.car),
        "photo_file_id": photo.photo_file_id,
        "image_url": photo.image.url if photo.image else "",
        "comment": photo.comment,
        "created_by": str(photo.created_by) if photo.created_by_id else None,
        "created_at": photo.created_at,
    }
