# Make this later.
# Dag to process raw metadata:
#     should_process = processed_at is null OR fetched_at > processed_at
#     should also depend on the hash of the raw data and the embedding model
#     potentially re-process if processed_at is older than a certain threshold (e.g., 1 year) to cach image updates not reflected in the raw data
