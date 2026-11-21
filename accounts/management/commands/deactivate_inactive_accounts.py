
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from accounts.models import User


class Command(BaseCommand):
    help = "Automatically deactivate accounts inactive for 30 days."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
        )

    def handle(self, *args, **options):
        days = options["days"]
        dry_run = options["dry_run"]

        if days < 0:
            self.stdout.write(
                self.style.ERROR("Days cannot be negative.")
            )
            return

        cutoff = timezone.now() - timedelta(days=days)

        inactive_accounts = User.objects.filter(
            role__in=["student", "teacher", "staff"],
            is_active=True,
        ).exclude(
            role="staff",
            staff_position="admin",
        ).filter(
            Q(last_login__lt=cutoff)
            | Q(
                last_login__isnull=True,
                date_joined__lt=cutoff,
            )
        )

        count = inactive_accounts.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: {count} account(s) would be deactivated."
                )
            )
            return

        inactive_accounts.update(is_active=False)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully deactivated {count} inactive account(s)."
            )
        )
