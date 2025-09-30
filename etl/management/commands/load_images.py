from django.core.management.base import BaseCommand, CommandError

from etl.pipeline.load.load_images.service import ImageLoadService


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
            help="Filter by specific museum (e.g. smk, cma, rma, met)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be processed without actually downloading images",
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
        dry_run = options["dry_run"]
        max_batches = options["max_batches"]
        delay_seconds = options["delay"]
        batch_delay_seconds = options["batch_delay"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No images will be downloaded")
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting image loading pipeline (batch_size={batch_size}, "
                f"museum_filter={museum_filter}, dry_run={dry_run}, "
                f"max_batches={max_batches}, delay={delay_seconds}s, "
                f"batch_delay={batch_delay_seconds}s)..."
            )
        )

        try:
            service = ImageLoadService()

            if dry_run:
                # For dry run, just show what records would be processed
                records = service.get_records_needing_processing(
                    batch_size, museum_filter
                )
                record_count = len(records)

                self.stdout.write(
                    f"Found {record_count} records that would be processed:"
                )
                for record in records[:10]:  # Show first 10
                    should_process, reason = service.should_process_image(record)
                    status = "PROCESS" if should_process else "SKIP"
                    self.stdout.write(
                        f"  [{status}] {record.museum_slug}:{record.object_number} - {reason}"
                    )

                if record_count > 10:
                    self.stdout.write(f"  ... and {record_count - 10} more records")
            else:
                # Run continuous batch processing
                total_stats = {"success": 0, "skipped": 0, "error": 0, "total": 0}
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
                        batch_size, museum_filter, delay_seconds, batch_delay_seconds
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
                            f"(success={stats['success']}, skipped={stats['skipped']}, error={stats['error']})"
                        )
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Total Progress: {total_stats['total']} records processed "
                            f"(success={total_stats['success']}, skipped={total_stats['skipped']}, error={total_stats['error']})"
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
                        f"Skipped: {total_stats['skipped']}, "
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
