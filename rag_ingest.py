#!/usr/bin/env python3
import os
import sys

from rag_service.ingestion import ingest_directory


def main():
    project_root = os.path.expanduser("~/PROJECTS/PIVOT")
    raw_dir = os.path.join(project_root, "data/raw")
    logical_collection = os.environ.get("LOGICAL_COLLECTION", "My_Project_History")

    if not os.path.isdir(raw_dir):
        print(f"Raw data directory not found: {raw_dir}")
        sys.exit(1)

    print(f"Starting ingestion from: {raw_dir}")
    results = ingest_directory(raw_dir, logical_collection=logical_collection)
    total = len(results)
    ok = sum(1 for r in results if r.get("status") == "ingested")
    skipped = sum(1 for r in results if r.get("status", "").startswith("skipped"))
    errors = [r for r in results if r.get("status") == "error"]

    print(f"Processed {total} files: {ok} ingested, {skipped} skipped, {len(errors)} errors.")
    if errors:
        for r in errors[:10]:
            print(f" - {r.get('file')}: {r.get('error')}")
        if len(errors) > 10:
            print(f" ... and {len(errors)-10} more")


if __name__ == "__main__":
    main()
