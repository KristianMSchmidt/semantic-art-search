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
            "--start-id",
            type=int,
            default=0,
            help="Start processing from this ID (default: 0)",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        start_id = options["start_id"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting transform pipeline (batch_size={batch_size}, start_id={start_id})..."
            )
        )

        try:
            # Import and run the transform pipeline
            from etl.pipeline.transform.transform import run_transform
            run_transform(batch_size=batch_size, start_id=start_id)
            self.stdout.write(
                self.style.SUCCESS("Transform pipeline completed successfully!")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Transform pipeline failed: {str(e)}")
            )
            raise