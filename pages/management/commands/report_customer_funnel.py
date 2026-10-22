import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from pages.selectors import get_funnel_report


class Command(BaseCommand):
    help = "Read-only anonymous funnel totals. Navigation requests are not unique human visitors; outcomes are period throughput, not a cohort."

    def add_arguments(self, parser):
        parser.add_argument("--start", required=True, help="Inclusive India-local date, YYYY-MM-DD")
        parser.add_argument("--end", help="Inclusive India-local date; defaults to today")

    def handle(self, *args, **options):
        try:
            start = date.fromisoformat(options["start"])
            end = date.fromisoformat(options["end"]) if options["end"] else timezone.localdate()
        except ValueError as error:
            raise CommandError("Use YYYY-MM-DD dates") from error
        if end < start or (end - start).days > 365:
            raise CommandError("Choose an ordered date range of at most 366 days")
        self.stdout.write(json.dumps(get_funnel_report(start=start, end=end), sort_keys=True))
