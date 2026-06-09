from django.core.management.base import BaseCommand

from core.models import ExpenseCategory


DEFAULT_CATEGORIES = ["Детали", "Работа", "Сторонние услуги", "Прочее"]


class Command(BaseCommand):
    help = "Create default expense categories."

    def handle(self, *args, **options):
        created = 0
        ExpenseCategory.objects.exclude(name__in=DEFAULT_CATEGORIES).update(is_active=False)
        for name in DEFAULT_CATEGORIES:
            category, was_created = ExpenseCategory.objects.get_or_create(name=name)
            if not category.is_active:
                category.is_active = True
                category.save(update_fields=["is_active"])
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Categories ready. Active: {len(DEFAULT_CATEGORIES)}. Created: {created}"))
