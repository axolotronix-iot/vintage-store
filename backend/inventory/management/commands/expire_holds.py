from django.core.management.base import BaseCommand

from inventory.services import expire_holds


class Command(BaseCommand):
    help = "Expire every active hold past its expiry."

    def handle(self, *args, **options):
        count = expire_holds()
        self.stdout.write(f"Expired {count} hold(s).")
