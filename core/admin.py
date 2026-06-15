import csv

from django.contrib import admin
from django.utils.html import format_html
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group, User
from django.db.models import Sum
from django.http import HttpResponse

from core.models import Car, CarPhoto, DefectPhoto, Expense, ExpenseCategory, ExpensePhoto, TelegramUser


class AdminUserProxy(User):
    class Meta:
        proxy = True
        verbose_name = "Пользователь админки"
        verbose_name_plural = "Пользователи админки"


class AdminUserAdmin(UserAdmin):
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Личные данные", {"fields": ("first_name", "last_name", "email")}),
        ("Права доступа", {"fields": ("is_active", "is_staff", "is_superuser", "user_permissions")}),
        ("Важные даты", {"fields": ("last_login", "date_joined")}),
    )
    filter_horizontal = ("user_permissions",)


admin.site.unregister(User)
admin.site.register(AdminUserProxy, AdminUserAdmin)
admin.site.unregister(Group)



def admin_image_preview(file_field, width=160):
    if not file_field:
        return "Фото не загружено"
    return format_html(
        '<a href="{}" target="_blank"><img src="{}" style="max-width:{}px;max-height:120px;border-radius:6px;object-fit:cover;" /></a>',
        file_field.url,
        file_field.url,
        width,
    )


class NoEmptyChoiceAdminMixin:
    no_empty_choice_fields = ()
    no_empty_fk_fields = ()

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        formfield = super().formfield_for_choice_field(db_field, request, **kwargs)
        if db_field.name in self.no_empty_choice_fields:
            formfield.empty_label = None
            formfield.choices = [choice for choice in formfield.choices if choice[0] != ""]
        return formfield

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name in self.no_empty_fk_fields:
            formfield.empty_label = None
        return formfield


@admin.register(TelegramUser)
class TelegramUserAdmin(NoEmptyChoiceAdminMixin, admin.ModelAdmin):
    no_empty_choice_fields = ("role",)
    list_display = ("telegram_id", "full_name", "username", "role", "is_active", "created_at")
    list_filter = ("role", "is_active", "created_at")
    search_fields = ("telegram_id", "username", "full_name")
    ordering = ("-created_at",)


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)


class CarPhotoInline(admin.TabularInline):
    model = CarPhoto
    extra = 0
    fields = ("image", "photo_preview", "photo_file_id", "created_by", "created_at")
    readonly_fields = ("photo_preview", "created_at")
    autocomplete_fields = ("created_by",)

    def photo_preview(self, obj):
        return admin_image_preview(getattr(obj, "image", None))
    photo_preview.short_description = "Фото"


class DefectPhotoInline(admin.TabularInline):
    model = DefectPhoto
    extra = 0
    fields = ("image", "defect_image_preview", "photo_file_id", "comment", "created_by", "created_at")
    readonly_fields = ("created_at", "defect_image_preview")
    autocomplete_fields = ("created_by",)

    def defect_image_preview(self, obj):
        return admin_image_preview(getattr(obj, "image", None))
    defect_image_preview.short_description = "Фото дефекта"


class ExpensePhotoInline(admin.TabularInline):
    model = ExpensePhoto
    extra = 0
    fields = ("image", "photo_preview", "photo_file_id", "created_at")
    readonly_fields = ("photo_preview", "created_at")

    def photo_preview(self, obj):
        return admin_image_preview(getattr(obj, "image", None))
    photo_preview.short_description = "Фото"


class ExpenseInline(admin.TabularInline):
    model = Expense
    extra = 0
    fields = ("amount", "currency", "description", "category", "employee", "spent_at")
    autocomplete_fields = ("category", "employee")


@admin.action(description="Экспорт выбранных заказов в CSV")
def export_cars_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="orders.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["ID", "Название", "Марка", "Модель", "VIN/номер", "Статус", "Этап", "Фото авто file_id", "Фото VIN file_id", "Итого расходов", "Создан"])
    for car in queryset.annotate(total=Sum("expenses__amount")):
        writer.writerow([car.id, car.title, car.brand, car.model, car.vin_or_plate or car.vin, car.get_status_display(), car.get_repair_stage_display(), car.car_photo_file_id, car.vin_photo_file_id, car.total or 0, car.created_at])
    return response


@admin.register(Car)
class CarAdmin(NoEmptyChoiceAdminMixin, admin.ModelAdmin):
    def car_photo_preview(self, obj):
        return admin_image_preview(getattr(obj, "car_photo", None))
    car_photo_preview.short_description = "Фото авто"

    def vin_photo_preview(self, obj):
        return admin_image_preview(getattr(obj, "vin_photo", None))
    vin_photo_preview.short_description = "Фото VIN"

    no_empty_choice_fields = ("status", "repair_stage")
    list_display = ("title", "brand", "model", "vin_or_plate", "status", "repair_stage", "has_photo", "has_vin_photo", "total_amount", "created_by", "updated_at")
    list_filter = ("status", "repair_stage", "created_at")
    search_fields = ("title", "brand", "model", "vin_or_plate", "vin", "description")
    autocomplete_fields = ("created_by",)
    inlines = (CarPhotoInline, DefectPhotoInline, ExpenseInline,)
    actions = (export_cars_csv,)
    readonly_fields = ("car_photo_preview", "vin_photo_preview")
    fieldsets = (
        ("Заказ", {"fields": ("title", "brand", "model", "vin_or_plate", "vin", "description", "car_photo", "car_photo_preview", "car_photo_file_id", "vin_photo", "vin_photo_preview", "vin_photo_file_id")} ),
        ("Статус", {"fields": ("status", "repair_stage", "completed_at", "archived_at")} ),
        ("Служебное", {"fields": ("created_by",)}),
    )

    @admin.display(description="Фото", boolean=True)
    def has_photo(self, obj: Car):
        return bool(obj.car_photo_file_id or obj.car_photo)

    @admin.display(description="Фото VIN", boolean=True)
    def has_vin_photo(self, obj: Car):
        return bool(obj.vin_photo_file_id or obj.vin_photo)

    @admin.display(description="Итого расходов")
    def total_amount(self, obj: Car):
        return obj.total_expenses


@admin.action(description="Экспорт выбранных расходов в CSV")
def export_expenses_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="expenses.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["ID", "Заказ", "Сумма", "Валюта", "Описание", "Категория", "Создал", "Изменил", "Дата", "Комментарий", "Фото file_id"])
    for expense in queryset.select_related("car", "category", "employee", "updated_by"):
        writer.writerow([expense.id, expense.car, expense.amount, expense.currency, expense.description, expense.category or "", expense.employee or "", expense.updated_by or "", expense.spent_at, expense.comment, expense.receipt_photo_file_id])
    return response


@admin.register(Expense)
class ExpenseAdmin(NoEmptyChoiceAdminMixin, admin.ModelAdmin):
    def receipt_photo_preview(self, obj):
        return admin_image_preview(getattr(obj, "receipt_photo", None))
    receipt_photo_preview.short_description = "Фото расхода"

    no_empty_fk_fields = ("car", "category", "employee")
    list_display = ("car", "amount", "currency", "description", "category", "employee", "updated_by", "spent_at")
    list_filter = ("category", "spent_at", "car__status")
    search_fields = ("car__title", "car__brand", "car__model", "car__vin_or_plate", "description", "comment")
    autocomplete_fields = ("car", "category", "employee", "updated_by")
    date_hierarchy = "spent_at"
    inlines = (ExpensePhotoInline,)
    actions = (export_expenses_csv,)


@admin.register(DefectPhoto)
class DefectPhotoAdmin(NoEmptyChoiceAdminMixin, admin.ModelAdmin):
    def defect_image_preview(self, obj):
        return admin_image_preview(getattr(obj, "image", None))
    defect_image_preview.short_description = "Фото дефекта"

    no_empty_fk_fields = ("car",)
    list_display = ("car", "created_by", "created_at", "short_comment")
    list_filter = ("created_at", "car__status")
    search_fields = ("car__title", "car__brand", "car__model", "car__vin_or_plate", "comment", "photo_file_id")
    autocomplete_fields = ("car", "created_by")

    @admin.display(description="Комментарий")
    def short_comment(self, obj: DefectPhoto):
        return obj.comment[:80]


@admin.register(CarPhoto)
class CarPhotoAdmin(NoEmptyChoiceAdminMixin, admin.ModelAdmin):
    no_empty_fk_fields = ("car",)
    list_display = ("car", "photo_preview", "created_by", "created_at")
    search_fields = ("car__title", "car__brand", "car__model", "photo_file_id")
    autocomplete_fields = ("car", "created_by")
    readonly_fields = ("photo_preview", "created_at")

    def photo_preview(self, obj):
        return admin_image_preview(getattr(obj, "image", None))
    photo_preview.short_description = "Фото"


@admin.register(ExpensePhoto)
class ExpensePhotoAdmin(NoEmptyChoiceAdminMixin, admin.ModelAdmin):
    no_empty_fk_fields = ("expense",)
    list_display = ("expense", "photo_preview", "created_at")
    search_fields = ("expense__description", "expense__car__title", "photo_file_id")
    autocomplete_fields = ("expense",)
    readonly_fields = ("photo_preview", "created_at")

    def photo_preview(self, obj):
        return admin_image_preview(getattr(obj, "image", None))
    photo_preview.short_description = "Фото"
