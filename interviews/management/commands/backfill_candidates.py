from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from interviews.models import Candidate, InterviewResponse


class Command(BaseCommand):
    help = "Backfill Candidate records from InterviewResponse legacy fields and link responses to candidates."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate the backfill without writing to the database.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Number of InterviewResponse rows to update per batch.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        batch_size: int = options["batch_size"]
        # Detect if legacy fields are present; if not, no-op gracefully
        legacy_fields = {f.name for f in InterviewResponse._meta.get_fields() if hasattr(f, "name")}
        if not {"candidate_email", "candidate_name"}.issubset(legacy_fields):
            self.stdout.write(self.style.SUCCESS("Legacy fields not present; nothing to backfill."))
            return

        qs = (
            InterviewResponse.objects.filter(candidate__isnull=True)
            .filter(~Q(candidate_email__isnull=True), ~Q(candidate_email__exact=""))
            .order_by("id")
        )

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("No InterviewResponse rows require backfill."))
            return

        self.stdout.write(f"Found {total} InterviewResponse rows without candidate link.")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN mode: no changes will be committed."))

        linked = 0
        created_candidates = 0
        updated_candidate_names = 0
        skipped = 0

        to_update = []

        def flush_batch():
            nonlocal to_update, linked
            if not to_update:
                return
            if dry_run:
                # In dry run, don't commit
                to_update.clear()
                return
            with transaction.atomic():
                InterviewResponse.objects.bulk_update(to_update, ["candidate"])
            linked += len(to_update)
            to_update.clear()

        for resp in qs.iterator(chunk_size=batch_size):
            email = (getattr(resp, "candidate_email", "") or "").strip().lower()
            name = (getattr(resp, "candidate_name", "") or "").strip()

            if not email:
                skipped += 1
                continue

            # Create or get candidate by unique email
            cand, created = Candidate.objects.get_or_create(
                email=email,
                defaults={"full_name": name},
            )
            if created:
                created_candidates += 1
            elif name and not cand.full_name:
                # Backfill name if missing
                if not dry_run:
                    cand.full_name = name
                    cand.save(update_fields=["full_name"])
                updated_candidate_names += 1

            # Link response to candidate
            resp.candidate = cand
            to_update.append(resp)

            if len(to_update) >= batch_size:
                flush_batch()

        # Flush remaining updates
        flush_batch()

        # Summary
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS("Backfill complete" + (" (DRY RUN)" if dry_run else ""))
        )
        self.stdout.write(f"  Candidate rows created: {created_candidates}")
        self.stdout.write(f"  Candidate names updated: {updated_candidate_names}")
        self.stdout.write(f"  InterviewResponses linked: {linked if not dry_run else len(qs)}")
        if skipped:
            self.stdout.write(f"  InterviewResponses skipped (missing/blank email): {skipped}")
