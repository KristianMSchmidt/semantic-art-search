import importlib
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Upsert raw data for the specified museum (smk, cma, rma, met, ...)"

    def add_arguments(self, parser):
        parser.add_argument(
            "-m",
            "--museum",
            dest="museum",
            choices=["smk", "cma", "rma", "met"],
            required=True,
            help="Slug of the museum to upsert (e.g. smk, cma, rma, met)",
        )

    def handle(self, *args, **options):
        museum = options["museum"]
        module_name = f"etl.scripts.extraction.{museum}_extraction"
        func_name = f"store_raw_data_{museum}"

        try:
            module = importlib.import_module(module_name)
            extractor = getattr(module, func_name)
        except ImportError:
            raise CommandError(f"No extraction module found at `{module_name}`")
        except AttributeError:
            raise CommandError(f"No function `{func_name}()` in `{module_name}`")

        self.stdout.write(
            self.style.SUCCESS(f"Starting upsert of raw data ({museum.upper()})...")
        )
        extractor()
        self.stdout.write(
            self.style.SUCCESS(f"Upsert of raw data ({museum.upper()}) complete!")
        )
