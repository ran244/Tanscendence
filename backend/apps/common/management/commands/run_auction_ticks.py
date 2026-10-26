"""Test-safe scheduled-task trigger: run one auction tick immediately."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run one auction tick (activate due events, close due lots, closing-soon alerts)."

    def handle(self, *args, **options):
        from apps.auctions.services.closing import (
            activate_due_events,
            close_due_lots,
            closing_soon_alerts,
        )

        activated = activate_due_events()
        closed = close_due_lots()
        alerted = closing_soon_alerts()
        self.stdout.write(self.style.SUCCESS(
            f"activated={len(activated)} events, closed={len(closed)} lots, "
            f"closing-soon alerts={alerted}"
        ))