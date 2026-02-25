#!/usr/bin/env python3
"""Quick script to check what's in the crawler bucket."""

from google.cloud import storage

bucket_name = "cpe-final-project-crawler-data"

client = storage.Client()
bucket = client.bucket(bucket_name)

print("Checking bucket contents...")
print("=" * 60)

# List all prefixes (dates)
blobs = list(bucket.list_blobs(prefix="dvb/", delimiter="/"))
prefixes = list(bucket.list_blobs(prefix="dvb/", delimiter="/").prefixes)

print(f"Bucket: gs://{bucket_name}")
print(f"\nDate folders found:")
for prefix in prefixes:
    print(f"  - {prefix}")
    
    # Count files in each date
    date_blobs = list(bucket.list_blobs(prefix=prefix))
    txt_count = len([b for b in date_blobs if b.name.endswith('.txt')])
    json_count = len([b for b in date_blobs if b.name.endswith('.json')])
    
    print(f"    Text files: {txt_count}")
    print(f"    JSON files: {json_count}")

if not prefixes:
    print("  No date folders found!")
    print("\nListing all files in dvb/:")
    all_blobs = list(bucket.list_blobs(prefix="dvb/"))
    for blob in all_blobs[:10]:
        print(f"  - {blob.name}")
