#!/usr/bin/env python3
"""
Crisis News Classifier Job

This batch job:
1. Reads cleaned articles from GCS for yesterday's date (or PROCESS_DATE env var)
2. Loads the crisis classification model
3. Classifies each article as crisis or non-crisis
4. Saves crisis articles to pending_review/ in the crisis bucket for admin review
"""

import os
import pickle
import logging
import sys
import re
from datetime import datetime, timedelta
from google.cloud import storage
from typing import List, Dict, Optional, Tuple
import hashlib


if "/workspace" not in sys.path:
    sys.path.append("/workspace")

from utils.neo4j_utils import (
    query_latest_hash_from_neo4j_env,
    query_latest_folder_hash_from_neo4j_env,
    query_folder_hash_derived_from_env,
    write_folder_hash_to_neo4j_env,
    create_main_pipeline_linkage_env,
)

# Heavy ML imports — required for model loading
try:
    import numpy as np
    from sklearn.base import BaseEstimator, TransformerMixin

    # Required for unpickling the Gemma model
    class GemmaEmbeddingVectorizer(BaseEstimator, TransformerMixin):
        """Sklearn-compatible transformer that returns mean-pooled Gemma embeddings."""

        def __init__(self, model_name="google/embeddinggemma-300m",
                     batch_size=32, normalize=True, device=None):
            self.model_name = model_name
            self.batch_size = batch_size
            self.normalize = normalize
            self.device = device
            self.model_ = None

        def fit(self, X, y=None):
            from sentence_transformers import SentenceTransformer
            self.model_ = SentenceTransformer(self.model_name, device=self.device)
            return self

        def transform(self, X):
            if self.model_ is None:
                from sentence_transformers import SentenceTransformer
                hf_token = os.environ.get("HF_TOKEN")
                self.model_ = SentenceTransformer(self.model_name, device=self.device, token=hf_token)
            texts = list(X)
            token_embeddings = self.model_.encode(
                texts,
                output_value="token_embeddings",
                convert_to_numpy=False,
                normalize_embeddings=False,
                show_progress_bar=False,
                batch_size=self.batch_size,
            )
            matrices = list(token_embeddings)
            pooled = np.vstack([m.numpy().mean(axis=0) for m in matrices]).astype(np.float32)
            if self.normalize:
                norms = np.linalg.norm(pooled, axis=1, keepdims=True)
                norms[norms == 0.0] = 1.0
                pooled = pooled / norms
            return pooled

except ImportError:
    pass  # Will fail gracefully at model load time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "crisis_model.pkl")


def load_crisis_model(model_path: str):
    """Load the pre-trained crisis classification model."""
    logger.info("=" * 60)
    logger.info("LOADING CRISIS CLASSIFICATION MODEL")
    logger.info("=" * 60)
    logger.info(f"📦 Model path: {model_path}")

    try:
        import __main__
        __main__.GemmaEmbeddingVectorizer = GemmaEmbeddingVectorizer

        with open(model_path, 'rb') as f:
            model = pickle.load(f)

        logger.info("✅ Model loaded successfully")
        logger.info(f"   Model type: {type(model).__name__}")
        return model

    except Exception as e:
        logger.error(f"❌ Error loading model: {e}")
        raise


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
    """Compute the next FolderHash from the previous folder hash and content hash.

    Matches the same formula used by the cleaner job: sha256("{previous}:{content}").
    """
    previous_folder_hash = (previous_folder_hash or "").strip()
    content_hash = (content_hash or "").strip()

    if not previous_folder_hash:
        return content_hash
    if not content_hash:
        return previous_folder_hash

    return hashlib.sha256(f"{previous_folder_hash}:{content_hash}".encode("utf-8")).hexdigest()


def fetch_cleaned_articles(bucket_name: str, date_str: str,
                           prefix_path: str = "dvb_cleaned") -> Tuple[List[Dict], str]:
    """Fetch cleaned articles from GCS bucket for a specific date."""
    logger.info("")
    logger.info("=" * 60)
    logger.info("FETCHING CLEANED ARTICLES FROM GCS")
    logger.info("=" * 60)
    logger.info(f"📦 Bucket: gs://{bucket_name}")
    logger.info(f"📅 Date: {date_str}")
    logger.info(f"📂 Prefix root: {prefix_path}/")
    logger.info("")

    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)

        source_hash = os.environ.get("SOURCE_CONTENT_HASH", "").strip()
        if not source_hash:
            # Traverse DERIVED_FROM from the latest dvb/ hash to find the matching dvb_cleaned/ hash.
            # Falls back to chain-tip query for backwards compatibility before edges are written.
            source_hash = (
                query_folder_hash_derived_from_env("dvb_cleaned/", "dvb/", bucket_name=bucket_name)
                or query_latest_folder_hash_from_neo4j_env("dvb_cleaned/", bucket_name)
                or ""
            )
        if not source_hash:
            source_hash = resolve_latest_hash_for_date(bucket, prefix_path, date_str) or ""
        if not source_hash:
            logger.warning(
                "⚠️  No source hash found in Neo4j or GCS fallback for folder dvb_cleaned/; returning empty input set.",
            )
            return [], ""

        prefix = f"{prefix_path}/{source_hash}/{date_str}/"

        logger.info(f"📂 Resolved source path: {prefix}")
        blobs = list(bucket.list_blobs(prefix=prefix))

        txt_blobs = [b for b in blobs
                     if b.name.endswith('.txt') and not b.name.endswith('_COMPLETE')]

        logger.info(f"📊 Found {len(blobs)} total files")
        logger.info(f"   - Text articles: {len(txt_blobs)}")
        logger.info("")

        if not txt_blobs:
            logger.warning("⚠️  No cleaned articles found!")
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

        logger.info(f"✅ Successfully fetched {len(articles)} article references")
        return articles, source_hash

    except Exception as e:
        logger.error(f"❌ Error fetching articles: {e}")
        raise


def read_article_from_gcs(bucket_name: str, blob_name: str) -> Optional[str]:
    """Read a single article text from GCS."""
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        return blob.download_as_text()
    except Exception as e:
        logger.error(f"❌ Error reading {blob_name}: {e}")
        return None


def classify_text(model, text: str) -> tuple:
    """Classify text as crisis or non-crisis. Returns (is_crisis, confidence)."""
    try:
        prediction = model.predict([text])[0]
        proba = model.predict_proba([text])[0]
        confidence = max(proba)
        is_crisis = bool(prediction == 'crisis')
        return is_crisis, confidence
    except Exception as e:
        logger.error(f"❌ Error during classification: {e}")
        raise


def upload_article(content: str, bucket_name: str, destination_path: str) -> str:
    """Upload article to GCS.

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
        logger.error(f"❌ Error uploading to {destination_path}: {e}")
        return "error"


def process_and_classify_articles(source_bucket: str, crisis_bucket: str,
                                  model, date_str: str,
                                  prefix_path: str = "dvb_cleaned") -> Dict[str, int]:
    """
    Fetch, classify, and save crisis articles to pending_review/.
    Admin must confirm/reject from the admin portal before articles move to crisis_articles/.
    """
    logger.info("")
    logger.info("=" * 60)
    logger.info("CLASSIFYING ARTICLES")
    logger.info("=" * 60)
    logger.info(f"📥 Source root:  gs://{source_bucket}/{prefix_path}/")
    logger.info("")

    articles, source_hash = fetch_cleaned_articles(source_bucket, date_str, prefix_path)
    # Compute output folder hash from previous folder hash (source_hash) + this job's CONTENT_HASH
    classifier_content_hash = os.environ.get("CONTENT_HASH", "").strip()
    output_hash = compute_folder_hash(source_hash, classifier_content_hash)

    if source_hash:
        logger.info(f"🔎 Source hash: {source_hash}")
    else:
        logger.info("🔎 Source hash: legacy/non-hash path")

    logger.info(f"🧬 Output hash: {output_hash}")
    logger.info(f"⏳ Pending: gs://{crisis_bucket}/pending_review/{output_hash}/{date_str}/")

    if not articles:
        return {"total": 0, "crisis": 0, "skipped_existing": 0, "errors": 0}

    stats = {"total": len(articles), "crisis": 0, "skipped_existing": 0, "errors": 0}

    logger.info(f"Processing {stats['total']} articles...")
    logger.info("")

    for i, article in enumerate(articles, 1):
        filename = article['filename']
        logger.info(f"[{i}/{stats['total']}] {filename}")

        content = read_article_from_gcs(source_bucket, article['blob_name'])

        if content is None:
            stats['errors'] += 1
            logger.error("  ❌ Failed to read")
            continue

        try:
            is_crisis, confidence = classify_text(model, content)

            if is_crisis:
                destination_path = f"pending_review/{output_hash}/{date_str}/{filename}"
                upload_status = upload_article(content, crisis_bucket, destination_path)

                if upload_status == "uploaded":
                    stats['crisis'] += 1
                    logger.info(f"  CRISIS (confidence: {confidence:.2%}) - Saved to pending_review")
                    try:
                        storage.Client().bucket(source_bucket).blob(article['blob_name']).delete()
                        logger.info(f"  🗑️  Deleted source: {article['blob_name']}")
                    except Exception as del_err:
                        logger.warning(f"  ⚠️  Could not delete source: {del_err}")
                elif upload_status == "exists":
                    stats['skipped_existing'] += 1
                    logger.info(f"  ⏭️  CRISIS (confidence: {confidence:.2%}) - Output already exists, skipped")
                    try:
                        storage.Client().bucket(source_bucket).blob(article['blob_name']).delete()
                        logger.info(f"  🗑️  Deleted source: {article['blob_name']}")
                    except Exception as del_err:
                        logger.warning(f"  ⚠️  Could not delete source: {del_err}")
                else:
                    stats['errors'] += 1
                    logger.error("  CRISIS but upload failed")
            else:
                logger.info(f"  Non-crisis (confidence: {confidence:.2%}) - Removing from cleaned")
                try:
                    storage.Client().bucket(source_bucket).blob(article['blob_name']).delete()
                    logger.info(f"  🗑️  Deleted non-crisis source: {article['blob_name']}")
                except Exception as del_err:
                    logger.warning(f"  ⚠️  Could not delete source: {del_err}")

        except Exception as e:
            stats['errors'] += 1
            logger.error(f"  ❌ Classification error: {e}")

    # Save the output folder hash to Neo4j ONLY if articles were actually written.
    # Include DERIVED_FROM so the admin and annotator can traverse from dvb_cleaned/ → pending_review/.
    if stats['crisis'] > 0:
        if write_folder_hash_to_neo4j_env(
            folder_path="pending_review/",
            hash_value=output_hash,
            bucket_name=crisis_bucket,
            producer_component_key="job:crisis-classifier-job",
            source_folder_path="dvb_cleaned/",
            source_folder_hash=source_hash,
        ):
            logger.info(f"✅ Output folder hash saved to Neo4j: pending_review/ → {output_hash}")
            
            # Create DEPENDS_ON_DATA_FROM relationships between consecutive pipeline stages
            success, message = create_main_pipeline_linkage_env()
            if success:
                logger.info(f"✅ Pipeline linkages created: {message}")
            else:
                logger.warning(f"⚠️  Pipeline linkage creation incomplete: {message}")
        else:
            logger.warning("⚠️  Neo4j write skipped (not configured or failed)")
    else:
        logger.info(f"⏭️  No crisis articles classified - skipping Neo4j hash update")

    return stats


def parse_date_string(date_str: str) -> Optional[datetime]:
    """Parse date string in DD-MM-YYYY or YYYY-MM-DD format."""
    if not date_str:
        return None
    
    # Try DD-MM-YYYY format (workflow format)
    try:
        return datetime.strptime(date_str, '%d-%m-%Y')
    except ValueError:
        pass
    
    # Try YYYY-MM-DD format
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return None


def get_date_range() -> List[str]:
    """Return the list of dates to process."""
    date_start = os.environ.get('DATE_START') or os.environ.get('START_DATE')
    date_end = os.environ.get('DATE_END') or os.environ.get('END_DATE')
    process_date = os.environ.get('PROCESS_DATE')
    
    # If we have a date range, use it
    if date_start and date_end:
        start = parse_date_string(date_start)
        end = parse_date_string(date_end)
        
        if start and end:
            if start > end:
                start, end = end, start
            
            dates = []
            current = start
            while current <= end:
                dates.append(current.strftime('%Y-%m-%d'))
                current += timedelta(days=1)
            return dates
    
    # If we have a single process date, use it
    if process_date:
        parsed = parse_date_string(process_date)
        if parsed:
            return [parsed.strftime('%Y-%m-%d')]
        return [process_date]  # Fallback to raw string
    
    # Default to yesterday
    yesterday = datetime.now() - timedelta(days=1)
    return [yesterday.strftime('%Y-%m-%d')]


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 Crisis Classifier Job Starting...")
    logger.info("=" * 60)

    dates_to_process = get_date_range()
    source_bucket = os.environ.get('GCS_BUCKET')
    crisis_bucket = os.environ.get('CRISIS_BUCKET')

    if not source_bucket or not crisis_bucket:
        logger.error("❌ Missing required env vars: GCS_BUCKET, CRISIS_BUCKET")
        sys.exit(1)

    logger.info(f"📅 Processing {len(dates_to_process)} date(s): {dates_to_process}")
    logger.info(f"📦 Source bucket:   {source_bucket}")
    logger.info(f"📦 Crisis bucket:   {crisis_bucket}")

    # Load model once
    model = load_crisis_model(MODEL_PATH)
    
    # Track aggregate stats across all dates
    aggregate_stats = {"total": 0, "crisis": 0, "skipped_existing": 0, "errors": 0}
    storage_client = storage.Client()
    crisis_bkt = storage_client.bucket(crisis_bucket)

    # Process each date in the range
    for date_str in dates_to_process:
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"Processing date: {date_str}")
        logger.info("=" * 60)
        
        # Check if already classified
        already_classified = (
            any(True for _ in crisis_bkt.list_blobs(prefix="pending_review/")
                if re.match(rf"^pending_review/[^/]+/{re.escape(date_str)}/", _.name)) or
            any(True for _ in crisis_bkt.list_blobs(prefix="crisis_articles/")
                if re.match(rf"^crisis_articles/[^/]+/{re.escape(date_str)}/", _.name)) or
            any(True for _ in crisis_bkt.list_blobs(prefix=f"pending_review/{date_str}/", max_results=1)) or
            any(True for _ in crisis_bkt.list_blobs(prefix=f"crisis_articles/{date_str}/", max_results=1))
        )
        
        if already_classified:
            logger.info(f"⏭️  Already classified for {date_str}, skipping.")
            continue
        
        # Classify articles for this date
        stats = process_and_classify_articles(source_bucket, crisis_bucket, model, date_str)
        
        # Aggregate stats
        aggregate_stats["total"] += stats["total"]
        aggregate_stats["crisis"] += stats["crisis"]
        aggregate_stats["skipped_existing"] += stats["skipped_existing"]
        aggregate_stats["errors"] += stats["errors"]
        
        logger.info(f"📊 Date {date_str}: Total: {stats['total']}  |  Crisis: {stats['crisis']}  |  Skipped existing: {stats['skipped_existing']}  |  Errors: {stats['errors']}")
        if stats['total'] > 0:
            crisis_rate = stats['crisis'] / stats['total'] * 100
            logger.info(f"   Crisis rate: {stats['crisis']}/{stats['total']} ({crisis_rate:.1f}%)")

    logger.info("")
    logger.info("=" * 60)
    logger.info("CLASSIFICATION COMPLETE!")
    logger.info("=" * 60)
    logger.info(f"📊 Aggregate Stats: Total: {aggregate_stats['total']}  |  Crisis: {aggregate_stats['crisis']}  |  Skipped existing: {aggregate_stats['skipped_existing']}  |  Errors: {aggregate_stats['errors']}")
    if aggregate_stats['total'] > 0:
        crisis_rate = aggregate_stats['crisis'] / aggregate_stats['total'] * 100
        logger.info(f"   Crisis rate: {aggregate_stats['crisis']}/{aggregate_stats['total']} ({crisis_rate:.1f}%)")
    logger.info(f"   Processed {len(dates_to_process)} date(s)")
