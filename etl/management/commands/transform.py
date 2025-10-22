from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run the ETL transform pipeline to process raw metadata"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Number of records to process in each batch (default: 1000)",
        )
        parser.add_argument(
            "--museum",
            type=str,
            choices=["smk", "cma", "rma", "met", "aic"],
            help="Process records for specific museum only (default: all museums)",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        museum = options.get("museum")

        museum_text = f" for {museum.upper()}" if museum else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Starting transform pipeline{museum_text} (batch_size={batch_size})..."
            )
        )

        try:
            # Import and run the transform pipeline
            from etl.pipeline.transform.transform import run_transform

            run_transform(batch_size=batch_size, museum=museum)
            self.stdout.write(
                self.style.SUCCESS("Transform pipeline completed successfully!")
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Transform pipeline failed: {str(e)}"))
            raise
