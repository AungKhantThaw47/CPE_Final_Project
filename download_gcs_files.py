from google.cloud import storage
import os
import argparse
import sys


def download_files(bucket_name: str,
                   prefix: str = "",
                   local_folder: str = "Event Annotate",
                   credentials_path: str | None = None,
                   only_txt: bool = True,
                   overwrite: bool = False):
    """Download files from a GCS bucket prefix into a local folder.

    - If `credentials_path` is provided, it will be used to authenticate.
    - If not provided, the default application credentials are used.
    - By default only files ending with `.txt` are downloaded; set
      `only_txt=False` to download all files.
    """

    # Create GCS client
    if credentials_path:
        client = storage.Client.from_service_account_json(credentials_path)
    else:
        client = storage.Client()

    bucket = client.bucket(bucket_name)

    # Ensure local folder exists
    os.makedirs(local_folder, exist_ok=True)

    blobs = bucket.list_blobs(prefix=prefix)

    downloaded = 0
    errors = 0

    for blob in blobs:
        # Skip GCS "folders"
        if blob.name.endswith("/"):
            continue

        if only_txt and not blob.name.endswith(".txt"):
            continue

        filename = os.path.basename(blob.name)
        local_path = os.path.join(local_folder, filename)

        if os.path.exists(local_path) and not overwrite:
            print(f"Skipping existing: {local_path}")
            continue

        try:
            blob.download_to_filename(local_path)
            print(f"Downloaded: {blob.name} -> {local_path}")
            downloaded += 1
        except Exception as e:
            print(f"Failed to download {blob.name}: {e}")
            errors += 1

    print(f"\nDone. Downloaded: {downloaded}. Errors: {errors}.")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Download files from GCS prefix")
    p.add_argument("--bucket", "-b", required=True, help="GCS bucket name")
    p.add_argument("--prefix", "-p", default="", help="GCS prefix/folder (optional)")
    p.add_argument("--out", "-o", default="Event Annotate", help="Local output folder")
    p.add_argument("--credentials", "-c", default=None, help="Path to service account JSON")
    p.add_argument("--all", action="store_true", help="Download all files instead of only .txt")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing local files")
    return p.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    download_files(bucket_name=args.bucket,
                   prefix=args.prefix,
                   local_folder=args.out,
                   credentials_path=args.credentials,
                   only_txt=not args.all,
                   overwrite=args.overwrite)