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
            choices=["smk", "cma", "rma", "met"],
            help="Slug of the museum to upsert (e.g. smk, cma, rma, met)",
        )
        group.add_argument(
            "--all",
            action="store_true",
            help="Run extraction for all supported museums",
        )

    def handle(self, *args, **options):
        if options["all"]:
            self.stdout.write(
                self.style.SUCCESS("Starting upsert of raw data for ALL museums...")
            )
            try:
                run_extract()
                self.stdout.write(
                    self.style.SUCCESS("Upsert of raw data for ALL museums complete!")
                )
            except Exception as e:
                raise CommandError(f"Extraction pipeline failed: {str(e)}")
        else:
            museum = options["museum"]
            extractor = get_extractor(museum)
            if not extractor:
                raise CommandError(f"No extractor found for museum: {museum}")

            self.stdout.write(
                self.style.SUCCESS(f"Starting upsert of raw data ({museum.upper()})...")
            )
            try:
                extract_single_museum(museum)
                self.stdout.write(
                    self.style.SUCCESS(f"Upsert of raw data ({museum.upper()}) complete!")
                )
            except Exception as e:
                raise CommandError(f"Extraction failed for {museum}: {str(e)}")
