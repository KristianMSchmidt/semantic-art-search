from django.core.management.base import BaseCommand, CommandError
from etl.pipeline.extract.factory import get_extractor
from etl.pipeline.extract.extract import run_extract, extract_single_museum


class Command(BaseCommand):
    help = "Upsert raw data for specified museum(s) or all museums"

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "-m",
            "--museum",
            dest="museum",
            choices=["smk", "cma", "rma", "met", "aic"],
            help="Slug of the museum to upsert (e.g. smk, cma, rma, met, aic)",
        )
        group.add_argument(
            "--all",
            action="store_true",
            help="Run extraction for all supported museums",
        )
        parser.add_argument(
            "--force-refetch",
            action="store_true",
            help="Force refetch all items regardless of existing data",
        )

    def handle(self, *args, **options):
        force_refetch = options.get("force_refetch", False)

        if options["all"]:
            message = "Starting upsert of raw data for ALL museums..."
            if force_refetch:
                message += " (force refetch enabled)"
            self.stdout.write(self.style.SUCCESS(message))
            try:
                run_extract(force_refetch=force_refetch)
                self.stdout.write(
                    self.style.SUCCESS("Upsert of raw data for ALL museums complete!")
                )
            except Exception as e:
                raise CommandError(f"Extraction pipeline failed: {str(e)}")
        else:
            museum = options["museum"]
            extractor = get_extractor(museum, force_refetch=force_refetch)
            if not extractor:
                raise CommandError(f"No extractor found for museum: {museum}")

            message = f"Starting upsert of raw data ({museum.upper()})..."
            if force_refetch:
                message += " (force refetch enabled)"
            self.stdout.write(self.style.SUCCESS(message))
            try:
                extract_single_museum(museum, force_refetch=force_refetch)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Upsert of raw data ({museum.upper()}) complete!"
                    )
                )
            except Exception as e:
                raise CommandError(f"Extraction failed for {museum}: {str(e)}")
