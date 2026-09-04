from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_date

from schemes.reminders import (
    build_scheme_reminder_plan,
    deliver_scheme_reminder,
    reminder_candidate_state,
)


class Command(BaseCommand):
    help = (
        "Preview scheme reminder candidates and, with --apply, send idempotent "
        "transactional emails while retaining delivery-attempt evidence."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Send pending reminders. Without this flag the command is read-only.",
        )
        parser.add_argument(
            "--as-of",
            help="India-local processing date in YYYY-MM-DD format (default: today).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=500,
            help="Maximum pending reminders to send in one run (default: 500).",
        )
        parser.add_argument(
            "--confirm-date-override",
            action="store_true",
            help=(
                "Confirm an intentional --apply run for a date other than the "
                "current India-local date."
            ),
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        limit = options["limit"]
        if limit < 1 or limit > 5000:
            raise CommandError("--limit must be between 1 and 5000.")

        as_of = self._parse_as_of(options.get("as_of"))
        if (
            apply
            and as_of != timezone.localdate()
            and not options["confirm_date_override"]
        ):
            raise CommandError(
                "Applying reminders for another date requires "
                "--confirm-date-override."
            )
        plan = build_scheme_reminder_plan(as_of=as_of)
        owner_audiences_enabled = any(
            [
                settings.SCHEME_REMINDER_OWNER_ELIGIBILITY,
                settings.SCHEME_REMINDER_OWNER_ALLOCATION_EXCEPTIONS,
                settings.SCHEME_REMINDER_OWNER_REDEMPTIONS,
            ]
        )
        configuration_errors = 0
        if owner_audiences_enabled and plan.owner_recipient_count == 0:
            configuration_errors += 1
        configuration_errors += plan.invalid_customer_recipient_count

        states = {"PENDING": 0, "ALREADY_SENT": 0, "RETRY_EXHAUSTED": 0}
        pending = []
        for candidate in plan.candidates:
            state = reminder_candidate_state(candidate)
            states[state] += 1
            if state == "PENDING":
                pending.append(candidate)

        sent = failed = exhausted = 0
        if apply and settings.SCHEME_REMINDERS_ENABLED:
            if owner_audiences_enabled and plan.owner_recipient_count == 0:
                raise CommandError(
                    "Owner reminders are enabled but no active owner email recipient exists."
                )
            for candidate in pending[:limit]:
                result = deliver_scheme_reminder(candidate)
                if result.outcome == "SENT":
                    sent += 1
                elif result.outcome == "FAILED":
                    failed += 1
                elif result.outcome == "RETRY_EXHAUSTED":
                    exhausted += 1
        elif apply:
            self.stdout.write(
                "scheme_reminders status=disabled; no email was sent"
            )

        mode = "apply" if apply else "dry-run"
        self.stdout.write(
            " ".join(
                [
                    "scheme_reminders",
                    f"status={'alert' if configuration_errors or failed or exhausted else 'ok'}",
                    f"release={settings.APP_RELEASE}",
                    f"mode={mode}",
                    f"enabled={str(settings.SCHEME_REMINDERS_ENABLED).lower()}",
                    f"as_of={as_of.isoformat()}",
                    f"candidates={len(plan.candidates)}",
                    f"pending={states['PENDING']}",
                    f"already_sent={states['ALREADY_SENT']}",
                    f"retry_exhausted={states['RETRY_EXHAUSTED'] + exhausted}",
                    f"sent={sent}",
                    f"failed={failed}",
                    f"owner_recipients={plan.owner_recipient_count}",
                    f"invalid_customer_recipients={plan.invalid_customer_recipient_count}",
                    f"truncated={max(0, len(pending) - limit) if apply else 0}",
                ]
            )
        )
        if apply and settings.SCHEME_REMINDERS_ENABLED and (
            failed or exhausted or plan.invalid_customer_recipient_count
        ):
            raise CommandError(
                "One or more reminder deliveries require owner review; successful "
                "deliveries remain recorded and will not be resent."
            )

    @staticmethod
    def _parse_as_of(raw_value):
        if not raw_value:
            return timezone.localdate()
        parsed = parse_date(raw_value)
        if parsed is None or not isinstance(parsed, date):
            raise CommandError("--as-of must use YYYY-MM-DD format.")
        return parsed
