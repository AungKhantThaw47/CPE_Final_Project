#!/usr/bin/env python3
"""
Script to clean DVB news articles from GCS bucket.
Fetches articles from crawler bucket, cleans them, and stores in cleaned bucket.
"""

import hashlib
import os
import re
import sys
from datetime import datetime, timedelta
from google.cloud import storage
from typing import List, Dict, Optional, Tuple


if "/workspace" not in sys.path:
    sys.path.append("/workspace")

from utils.neo4j_utils import (
    query_latest_folder_hash_from_neo4j_env,
    query_latest_hash_from_neo4j_env,
    write_folder_hash_to_neo4j_env,
)

# Common Myanmar author name patterns
AUTHOR_NAME_PATTERN = re.compile(r'^[\u1000-\u109F\u200B-\u200D\uAA60-\uAA7F]{2,20}$')

# Source citation patterns
SOURCE_PATTERNS = [
    re.compile(r'^Source\s*:\s*.+', re.IGNORECASE),
    re.compile(r'^ရင်းမြစ်\s*:\s*.+'),
    re.compile(r'^သတင်းရင်းမြစ်\s*:\s*.+'),
]

def is_likely_author_name(line):
    """Check if a line is likely an author name."""
    line = line.strip()
    
    if not line:
        return False
    
    if AUTHOR_NAME_PATTERN.match(line):
        return True
    
    clean_line = line.replace('။', '').replace('၊', '').strip()
    
    if len(clean_line) <= 15 and AUTHOR_NAME_PATTERN.match(clean_line):
        return True
    
    return False


def is_source_citation(line):
    """Check if a line is a source citation."""
    line = line.strip()
    
    if not line:
        return False
    
    for pattern in SOURCE_PATTERNS:
        if pattern.match(line):
            return True
    
    return False


def clean_text_content(content: str) -> tuple:
    """
    Clean text content by removing author names and source citations.
    Returns (cleaned_content, was_modified)
    """
    if not content:
        return content, False
    
    lines = content.split('\n')
    modified = False
    
    # Remove trailing empty lines
    while lines and lines[-1].strip() == '':
        lines.pop()
    
    if not lines:
        return content, False
    
    # Remove author names and source citations from the end
    while lines:
        last_line = lines[-1].strip()
        
        if is_likely_author_name(last_line):
            lines.pop()
            modified = True
            while lines and lines[-1].strip() == '':
                lines.pop()
        elif is_source_citation(last_line):
            lines.pop()
            modified = True
            while lines and lines[-1].strip() == '':
                lines.pop()
        else:
            break
    
    if modified and lines:
        cleaned_content = '\n'.join(lines)
        if not cleaned_content.endswith('\n'):
            cleaned_content += '\n'
        return cleaned_content, True
    
    return content, False


def resolve_latest_hash_for_date(bucket, prefix_path: str, date_str: str) -> Optional[str]:
    """Resolve the latest hash folder under a prefix/date by blob update time.

    This is only a fallback when Neo4j is unavailable or empty at runtime.
    """
    pattern = re.compile(rf"^{re.escape(prefix_path)}/([^/]+)/{re.escape(date_str)}/")
    latest_by_hash = {}

    for blob in bucket.list_blobs(prefix=f"{prefix_path}/"):
        match = pattern.match(blob.name)
        if not match:
            continue
        hash_value = match.group(1)
        current = latest_by_hash.get(hash_value)
        updated = blob.updated or datetime.min
        if current is None or updated > current:
            latest_by_hash[hash_value] = updated

    if not latest_by_hash:
        return None

    return max(latest_by_hash.items(), key=lambda item: item[1])[0]


def compute_folder_hash(previous_folder_hash: str, content_hash: str) -> str:
    """Compute the next FolderHash from the previous folder hash and content hash."""
    previous_folder_hash = (previous_folder_hash or "").strip()
    content_hash = (content_hash or "").strip()

    if not previous_folder_hash:
        return content_hash
    if not content_hash:
        return previous_folder_hash

    return hashlib.sha256(f"{previous_folder_hash}:{content_hash}".encode("utf-8")).hexdigest()


def fetch_articles_from_gcs(bucket_name: str, date_str: Optional[str] = None,
                            prefix_path: str = "dvb") -> Tuple[List[Dict], str]:
    """Fetch all articles from GCS bucket for a specific date."""
    if not date_str:
        # Default to yesterday to align with crawler/classifier date windows.
        yesterday = datetime.now() - timedelta(days=1)
        date_str = yesterday.strftime('%Y-%m-%d')
    
    print("=" * 60)
    print("Fetching Articles from GCS Bucket")
    print("=" * 60)
    print(f"📦 Bucket: gs://{bucket_name}")
    print(f"📅 Date: {date_str}")
    print(f"📂 Prefix root: {prefix_path}/")
    print()
    
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        
        source_hash = os.environ.get("SOURCE_CONTENT_HASH", "").strip()
        if not source_hash:
            source_hash = query_latest_hash_from_neo4j_env("job:dvb-crawler-job") or ""
        if not source_hash:
            source_hash = resolve_latest_hash_for_date(bucket, prefix_path, date_str) or ""
        if not source_hash:
            print("⚠️  No source hash found in Neo4j or GCS fallback for job:dvb-crawler-job; returning empty input set.")
            return [], ""

        prefix = f"{prefix_path}/{source_hash}/{date_str}/"

        print(f"📂 Resolved source path: {prefix}")
        blobs = list(bucket.list_blobs(prefix=prefix))
        
        txt_blobs = [b for b in blobs if b.name.endswith('.txt')]
        json_blobs = [b for b in blobs if b.name.endswith('.json')]
        
        print(f"📊 Found {len(blobs)} total files")
        print(f"   - Text articles: {len(txt_blobs)}")
        print(f"   - JSON metadata: {len(json_blobs)}")
        print()
        
        if not txt_blobs:
            print("⚠️  No text articles found!")
            return [], source_hash
        
        articles = []
        for blob in txt_blobs:
            articles.append({
                'blob_name': blob.name,
                'filename': os.path.basename(blob.name),
                'size': blob.size,
                'bucket': bucket_name,
                'date': date_str
            })
        
        print(f"✅ Successfully fetched {len(articles)} article references")
        return articles, source_hash
        
    except Exception as e:
        print(f"❌ Error fetching articles: {e}")
        raise


def read_article_from_gcs(bucket_name: str, blob_name: str) -> Optional[str]:
    """Read a single article from GCS."""
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        content = blob.download_as_text()
        return content
        
    except Exception as e:
        print(f"❌ Error reading {blob_name}: {e}")
        return None


def upload_cleaned_article(content: str, bucket_name: str, destination_path: str) -> str:
    """Upload cleaned article content to GCS.

    Returns:
        str: one of "uploaded", "exists", "error"
    """
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(destination_path)

        if blob.exists():
            return "exists"
        
        blob.upload_from_string(content, content_type='text/plain')
        return "uploaded"
        
    except Exception as e:
        print(f"❌ Error uploading to {destination_path}: {e}")
        return "error"


def process_and_clean_articles(source_bucket: str, target_bucket: str, 
                               date_str: Optional[str] = None, 
                               prefix_path: str = "dvb") -> Dict[str, int]:
    """Process all articles: fetch, clean, and upload to target bucket."""
    if not date_str:
        yesterday = datetime.now() - timedelta(days=1)
        date_str = yesterday.strftime('%Y-%m-%d')
    
    print()
    print("=" * 60)
    print("Processing and Cleaning Articles")
    print("=" * 60)
    print(f"📥 Source root: gs://{source_bucket}/{prefix_path}/")
    print()
    
    articles, source_hash = fetch_articles_from_gcs(source_bucket, date_str, prefix_path)
    os.environ["SOURCE_CONTENT_HASH"] = source_hash
    print(f"🔎 Source content hash: {source_hash}")
    print(f"📤 Target root: gs://{target_bucket}/dvb_cleaned/")
    previous_folder_hash = query_latest_folder_hash_from_neo4j_env("dvb/", target_bucket) or source_hash
    cleaner_content_hash = (
        os.environ.get("CONTENT_HASH", "").strip()
        or query_latest_hash_from_neo4j_env("job:dvb-text-cleaner-job")
        or ""
    )
    output_hash = compute_folder_hash(previous_folder_hash, cleaner_content_hash)
    os.environ["DVB_CLEANED_FOLDER_HASH"] = output_hash

    print(f"🧬 Output hash: {output_hash}")
    print(f"📤 Target: gs://{target_bucket}/dvb_cleaned/{output_hash}/{date_str}/")
    print(f"🔗 Previous folder hash: {previous_folder_hash}")
    print(f"🧾 Cleaner content hash: {cleaner_content_hash or 'NONE'}")

    if source_hash:
        print(f"🔎 Source hash: {source_hash}")
    else:
        print("🔎 Source hash: legacy/non-hash path")
    
    if not articles:
        return {"total": 0, "cleaned": 0, "unchanged": 0, "skipped_existing": 0, "errors": 0}
    
    stats = {"total": len(articles), "cleaned": 0, "unchanged": 0, "skipped_existing": 0, "errors": 0}
    
    print(f"Processing {stats['total']} articles...")
    print()
    
    for i, article in enumerate(articles, 1):
        filename = article['filename']
        print(f"[{i}/{stats['total']}] {filename}")
        
        content = read_article_from_gcs(source_bucket, article['blob_name'])
        
        if content is None:
            stats['errors'] += 1
            print(f"  ❌ Failed to read")
            continue
        
        cleaned_content, was_modified = clean_text_content(content)
        
        destination_path = f"dvb_cleaned/{output_hash}/{date_str}/{filename}"
        upload_status = upload_cleaned_article(cleaned_content, target_bucket, destination_path)

        if upload_status == "uploaded":
            if was_modified:
                stats['cleaned'] += 1
                print(f"  ✅ Cleaned and uploaded")
            else:
                stats['unchanged'] += 1
                print(f"  ⏭️  No changes, uploaded as-is")
        elif upload_status == "exists":
            stats['skipped_existing'] += 1
            print(f"  ⏭️  Output already exists, skipped")
        else:
            stats['errors'] += 1
            print(f"  ❌ Upload failed")
    
    return stats


if __name__ == "__main__":
    # Pipeline mode - reads from GCS_BUCKET environment variable
    # Uses same bucket by default (single-bucket layout), with optional override.
    print("Test")
    source_bucket = os.environ.get('GCS_BUCKET')
    date_str = os.environ.get('PROCESS_DATE')
    prefix_path = os.environ.get('GCS_PREFIX', 'dvb')
    
    if not source_bucket:
        print("❌ Error: GCS_BUCKET environment variable not set")
        exit(1)
    
    target_bucket = os.environ.get('GCS_CLEANED_BUCKET', source_bucket)
    
    print("=" * 60)
    print("DVB Article Cleaner - Pipeline Mode Test")
    print("=" * 60)
    print(f"Configuration:")
    print(f"  Source bucket: {source_bucket}")
    print(f"  Target bucket: {target_bucket}")
    print(f"  Process date: {date_str or 'yesterday (default)'}")
    print(f"  Prefix: {prefix_path}")
    print()
    
    # Process and clean articles
    stats = process_and_clean_articles(source_bucket, target_bucket, date_str, prefix_path)
    
    print()
    print("=" * 60)
    print("Cleaning Complete!")
    print("=" * 60)
    print(f"📊 Statistics:")
    print(f"   Total articles: {stats['total']}")
    print(f"   ✅ Cleaned: {stats['cleaned']}")
    print(f"   ⏭️  Unchanged: {stats['unchanged']}")
    print(f"   ⏭️  Skipped existing outputs: {stats['skipped_existing']}")
    print(f"   ❌ Errors: {stats['errors']}")
    print()
    
    if stats['errors'] > 0:
        print(f"⚠️  Completed with {stats['errors']} errors")
        exit(1)

    print("✅ All articles processed successfully!")
    final_date = date_str or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    output_hash = os.environ.get("DVB_CLEANED_FOLDER_HASH", "").strip()
    print(f"   Cleaned data: gs://{target_bucket}/dvb_cleaned/{output_hash}/{final_date}/")

    # Create completion marker file to trigger classifier
    try:
        client = storage.Client()
        marker_path = f"dvb_cleaned/{output_hash}/{final_date}/_COMPLETE"
        marker_blob = client.bucket(target_bucket).blob(marker_path)
        if marker_blob.exists():
            print(f"   Completion marker already exists: gs://{target_bucket}/{marker_path}")
        else:
            marker_blob.upload_from_string("", content_type='text/plain')
            print(f"   Completion marker: gs://{target_bucket}/{marker_path}")
    except Exception as e:
        print(f"   ⚠️  Failed to create completion marker: {e}")

    # Write the cleaned folder hash to Neo4j so downstream jobs query the folder lineage directly.
    if write_folder_hash_to_neo4j_env("dvb_cleaned/", output_hash, target_bucket, "job:dvb-text-cleaner-job"):
        print(f"   ✅ Folder hash saved to Neo4j: dvb_cleaned/ → {output_hash}")
    else:
        print(f"   ⚠️  Neo4j folder hash write skipped (not configured or failed)")

    exit(0)
