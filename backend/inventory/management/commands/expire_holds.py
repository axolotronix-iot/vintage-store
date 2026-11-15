from django.core.management.base import BaseCommand

from inventory import services


class Command(BaseCommand):
    help = "Expire holds that are past their expiry."

    def handle(self, *args, **options):
        count = services.expire_holds()
        self.stdout.write(f"Apartados expirados: {count}")
