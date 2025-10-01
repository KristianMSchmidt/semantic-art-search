from django.core.management.base import BaseCommand, CommandError

from etl.services.image_load_service import ImageLoadService


class Command(BaseCommand):
    help = "Load thumbnail images from museum URLs to S3 bucket"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of records to process in each batch (default: 100)",
        )
        parser.add_argument(
            "--museum",
            type=str,
            choices=["smk", "cma", "rma", "met"],
            help="Filter by specific museum (e.g. smk, cma, rma, met). Default: all museums",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force reload all images regardless of current image_loaded status",
        )
        parser.add_argument(
            "--max-batches",
            type=int,
            default=None,
            help="Maximum number of batches to process (default: no limit)",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0.2,
            help="Delay in seconds between image downloads (default: 0.2)",
        )
        parser.add_argument(
            "--batch-delay",
            type=int,
            default=5,
            help="Delay in seconds between batches (default: 5)",
        )

    def handle(self, **options):
        batch_size = options["batch_size"]
        museum_filter = options["museum"]
        force_reload = options["force"]
        max_batches = options["max_batches"]
        delay_seconds = options["delay"]
        batch_delay_seconds = options["batch_delay"]

        museum_text = f" for {museum_filter.upper()}" if museum_filter else " for all museums"
        force_text = " (force reload enabled)" if force_reload else ""

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting image loading pipeline{museum_text}{force_text} "
                f"(batch_size={batch_size}, delay={delay_seconds}s, "
                f"batch_delay={batch_delay_seconds}s, max_batches={max_batches})..."
            )
        )

        try:
            service = ImageLoadService()

            # Reset processed tracking if force reload is enabled
            if force_reload:
                service.reset_processed_tracking()

            # Run continuous batch processing
            total_stats = {"success": 0, "error": 0, "total": 0}
            batch_num = 1

            while True:
                # Check if we've hit the batch limit
                if max_batches and batch_num > max_batches:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Reached maximum batch limit ({max_batches}). Stopping."
                        )
                    )
                    break

                self.stdout.write(
                    self.style.HTTP_INFO(f"\n>>> Processing batch {batch_num}...")
                )

                # Process one batch
                stats = service.run_batch_processing(
                    batch_size=batch_size,
                    museum_filter=museum_filter,
                    force_reload=force_reload,
                    delay_seconds=delay_seconds,
                    batch_delay_seconds=batch_delay_seconds
                )

                # If no records were processed, we're done
                if stats["total"] == 0:
                    self.stdout.write("No more records to process. Complete!")
                    break

                # Update totals
                for key in total_stats:
                    total_stats[key] += stats[key]

                # Show batch progress with clear formatting
                self.stdout.write(
                    self.style.SUCCESS(f"\n=== BATCH {batch_num} COMPLETE ===")
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Batch {batch_num}: {stats['total']} records "
                        f"(success={stats['success']}, error={stats['error']})"
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Total Progress: {total_stats['total']} records processed "
                        f"(success={total_stats['success']}, error={total_stats['error']})"
                    )
                )
                self.stdout.write("=" * 50)

                batch_num += 1

            # Final summary
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nImage loading complete! "
                    f"Processed {batch_num - 1} batches. "
                    f"Total: {total_stats['total']}, "
                    f"Success: {total_stats['success']}, "
                    f"Errors: {total_stats['error']}"
                )
            )

            if total_stats["error"] > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"Warning: {total_stats['error']} records failed to process. "
                        "Check logs for details."
                    )
                )

        except Exception as e:
            raise CommandError(f"Image loading pipeline failed: {str(e)}")