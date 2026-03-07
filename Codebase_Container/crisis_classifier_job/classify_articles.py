#!/usr/bin/env python3
"""
Crisis News Classifier Service

This Flask web service:
1. Receives Eventarc webhooks when files are created in the cleaned bucket
2. Checks if the file is a _COMPLETE marker
3. If yes, loads the crisis classification model and processes all articles for that date
4. Classifies each article as crisis or non-crisis
5. Saves only crisis articles to the crisis bucket
"""

import os
import pickle
import re
import logging
import sys
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, redirect
from google.cloud import storage
from typing import List, Dict, Optional

# Heavy ML imports — only loaded if available (not needed for admin routes)
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
    pass  # ML deps not installed; model loading will fail gracefully

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Global model (loaded once at startup)
MODEL = None
MODEL_PATH = os.path.join(os.path.dirname(__file__), "crisis_model.pkl")


def load_crisis_model(model_path: str = "crisis_model.pkl"):
    """Load the pre-trained crisis classification model."""
    logger.info("=" * 60)
    logger.info("LOADING CRISIS CLASSIFICATION MODEL")
    logger.info("=" * 60)
    logger.info(f"📦 Model path: {model_path}")

    try:
        # Inject class into __main__ so pickle can find it
        # (model was pickled when GemmaEmbeddingVectorizer was defined in __main__)
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


def fetch_cleaned_articles(bucket_name: str, date_str: str,
                          prefix_path: str = "dvb_cleaned") -> List[Dict]:
    """Fetch cleaned articles from GCS bucket for a specific date."""
    logger.info("")
    logger.info("=" * 60)
    logger.info("FETCHING CLEANED ARTICLES FROM GCS")
    logger.info("=" * 60)
    logger.info(f"📦 Bucket: gs://{bucket_name}")
    logger.info(f"📅 Date: {date_str}")
    logger.info(f"📂 Prefix: {prefix_path}/{date_str}/")
    logger.info("")

    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)

        prefix = f"{prefix_path}/{date_str}/"
        blobs = list(bucket.list_blobs(prefix=prefix))

        # Filter for .txt files and exclude _COMPLETE marker
        txt_blobs = [b for b in blobs
                     if b.name.endswith('.txt') and not b.name.endswith('_COMPLETE')]

        logger.info(f"📊 Found {len(blobs)} total files")
        logger.info(f"   - Text articles: {len(txt_blobs)}")
        logger.info("")

        if not txt_blobs:
            logger.warning("⚠️  No cleaned articles found!")
            return []

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
        return articles

    except Exception as e:
        logger.error(f"❌ Error fetching articles: {e}")
        raise


def read_article_from_gcs(bucket_name: str, blob_name: str) -> Optional[str]:
    """Read a single article text from GCS."""
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        content = blob.download_as_text()
        return content

    except Exception as e:
        logger.error(f"❌ Error reading {blob_name}: {e}")
        return None


def classify_text(model, text: str) -> tuple:
    """
    Classify text as crisis or non-crisis.
    Returns (is_crisis: bool, confidence: float)
    """
    try:
        # Predict
        prediction = model.predict([text])[0]

        # Get probability/confidence
        proba = model.predict_proba([text])[0]
        confidence = max(proba)

        is_crisis = bool(prediction == 'crisis')  # Labels are 'crisis' or 'non_crisis'

        return is_crisis, confidence

    except Exception as e:
        logger.error(f"❌ Error during classification: {e}")
        raise


def upload_article(content: str, bucket_name: str, destination_path: str) -> bool:
    """Upload article to GCS."""
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(destination_path)

        blob.upload_from_string(content, content_type='text/plain')
        return True

    except Exception as e:
        logger.error(f"❌ Error uploading to {destination_path}: {e}")
        return False


def process_and_classify_articles(source_bucket: str, crisis_bucket: str,
                                  model, date_str: str,
                                  prefix_path: str = "dvb_cleaned") -> Dict[str, int]:
    """
    Process all articles: fetch, classify, and save crisis articles to pending_review bucket.
    Admin must confirm/reject from /admin page before articles move to crisis_articles/.
    Returns statistics about the classification job.
    """
    logger.info("")
    logger.info("=" * 60)
    logger.info("CLASSIFYING ARTICLES")
    logger.info("=" * 60)
    logger.info(f"📥 Source:     gs://{source_bucket}/{prefix_path}/{date_str}/")
    logger.info(f"⏳ Pending:    gs://{crisis_bucket}/pending_review/{date_str}/")
    logger.info("")

    articles = fetch_cleaned_articles(source_bucket, date_str, prefix_path)

    if not articles:
        return {"total": 0, "crisis": 0, "errors": 0}

    stats = {"total": len(articles), "crisis": 0, "errors": 0}

    logger.info(f"Processing {stats['total']} articles...")
    logger.info("")

    for i, article in enumerate(articles, 1):
        filename = article['filename']
        logger.info(f"[{i}/{stats['total']}] {filename}")

        content = read_article_from_gcs(source_bucket, article['blob_name'])

        if content is None:
            stats['errors'] += 1
            logger.error(f"  ❌ Failed to read")
            continue

        try:
            is_crisis, confidence = classify_text(model, content)

            if is_crisis:
                destination_path = f"pending_review/{date_str}/{filename}"
                success = upload_article(content, crisis_bucket, destination_path)

                if success:
                    stats['crisis'] += 1
                    logger.info(f"  CRISIS (confidence: {confidence:.2%}) - Saved to pending_review")
                else:
                    stats['errors'] += 1
                    logger.error(f"  CRISIS but upload failed")
            else:
                logger.info(f"  Non-crisis (confidence: {confidence:.2%}) - Skipped")

        except Exception as e:
            stats['errors'] += 1
            logger.error(f"  ❌ Classification error: {e}")

    return stats


@app.route("/", methods=["POST"])
def handle_eventarc():
    """
    Handle Eventarc webhook for Cloud Storage events.
    Triggered when files are created in the cleaned bucket.
    """
    if MODEL is None:
        return jsonify({"status": "error", "reason": "Model not loaded"}), 503

    try:
        # Parse the Eventarc CloudEvent
        event_data = request.get_json()

        logger.info("=" * 60)
        logger.info("RECEIVED EVENTARC WEBHOOK")
        logger.info("=" * 60)
        logger.info(f"Event data: {event_data}")
        logger.info("")

        # Extract object name from event
        # CloudEvent format: event_data contains 'data' with GCS object info
        if 'data' in event_data:
            object_name = event_data['data'].get('name', '')
            bucket_name = event_data['data'].get('bucket', '')
        else:
            # Fallback: direct GCS notification format
            object_name = event_data.get('name', '')
            bucket_name = event_data.get('bucket', '')

        logger.info(f"📄 Object: {object_name}")
        logger.info(f"📦 Bucket: {bucket_name}")
        logger.info("")

        # Check if this is a _COMPLETE marker file
        if not object_name.endswith('_COMPLETE'):
            logger.info(f"⏭️  Ignoring non-marker file: {object_name}")
            return jsonify({"status": "ignored", "reason": "not a completion marker"}), 200

        # Extract date from path: dvb_cleaned/{date}/_COMPLETE
        match = re.search(r'dvb_cleaned/(\d{4}-\d{2}-\d{2})/_COMPLETE', object_name)
        if not match:
            logger.warning(f"⚠️  Could not extract date from path: {object_name}")
            return jsonify({"status": "error", "reason": "invalid marker path"}), 400

        date_str = match.group(1)
        logger.info(f"📅 Extracted date: {date_str}")
        logger.info("")

        # Get configuration
        source_bucket = os.environ.get('GCS_BUCKET')
        crisis_bucket = os.environ.get('CRISIS_BUCKET')

        if not source_bucket or not crisis_bucket:
            logger.error("❌ Missing required env vars: GCS_BUCKET, CRISIS_BUCKET")
            return jsonify({"status": "error", "reason": "missing env vars"}), 500

        # Check if this date has already been classified (articles exist in pending_review or crisis_articles)
        storage_client = storage.Client()
        crisis_bkt = storage_client.bucket(crisis_bucket)
        already_classified = (
            any(True for _ in crisis_bkt.list_blobs(prefix=f"pending_review/{date_str}/", max_results=1)) or
            any(True for _ in crisis_bkt.list_blobs(prefix=f"crisis_articles/{date_str}/", max_results=1))
        )
        if already_classified:
            logger.info(f"⏭️  Already classified for {date_str}, skipping to avoid duplicate processing.")
            return jsonify({"status": "skipped", "reason": "already classified"}), 200

        logger.info("=" * 60)
        logger.info("CRISIS NEWS CLASSIFIER - EVENT TRIGGERED")
        logger.info("=" * 60)
        logger.info(f"  Source bucket:     {source_bucket}")
        logger.info(f"  Crisis bucket:     {crisis_bucket}")
        logger.info(f"  Process date:      {date_str}")
        logger.info("")

        # Process and classify articles
        stats = process_and_classify_articles(
            source_bucket,
            crisis_bucket,
            MODEL,
            date_str,
            "dvb_cleaned"
        )

        logger.info("")
        logger.info("=" * 60)
        logger.info("CLASSIFICATION COMPLETE!")
        logger.info("=" * 60)
        logger.info(f"📊 Statistics:")
        logger.info(f"   Total articles processed: {stats['total']}")
        logger.info(f"   🚨 Crisis articles: {stats['crisis']}")
        logger.info(f"   ❌ Errors: {stats['errors']}")
        logger.info("")

        if stats['total'] > 0:
            crisis_rate = stats['crisis'] / stats['total'] * 100
            logger.info(f"   Crisis rate: {stats['crisis']}/{stats['total']} ({crisis_rate:.1f}%)")
            logger.info(f"   Pending review: gs://{crisis_bucket}/pending_review/{date_str}/")

        return jsonify({
            "status": "success",
            "date": date_str,
            "statistics": stats
        }), 200

    except Exception as e:
        logger.error(f"❌ Error handling webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


def list_pending_articles(crisis_bucket: str) -> List[Dict]:
    """List all articles in pending_review/ across all dates."""
    client = storage.Client()
    bucket = client.bucket(crisis_bucket)
    blobs = list(bucket.list_blobs(prefix="pending_review/"))
    articles = []
    for blob in blobs:
        if blob.name.endswith('.txt'):
            parts = blob.name.split('/')  # pending_review/{date}/{filename}
            date = parts[1] if len(parts) >= 3 else 'unknown'
            articles.append({
                'blob_name': blob.name,
                'filename': os.path.basename(blob.name),
                'date': date,
                'size': blob.size,
            })
    return articles


@app.route("/admin", methods=["GET"])
def admin_page():
    """Admin HTML page for reviewing pending crisis articles."""
    crisis_bucket = os.environ.get('CRISIS_BUCKET', '')
    try:
        articles = list_pending_articles(crisis_bucket) if crisis_bucket else []
    except Exception as e:
        articles = []
        logger.error(f"Error listing pending articles: {e}")

    # Group articles by date, sorted oldest first (process chronologically)
    from collections import defaultdict
    by_date = defaultdict(list)
    for a in articles:
        by_date[a['date']].append(a)
    sorted_dates = sorted(by_date.keys())

    sections = ""
    for date in sorted_dates:
        date_articles = by_date[date]
        rows = ""
        for a in date_articles:
            rows += f"""
        <tr>
            <td>{a['filename']}</td>
            <td>{a['size']} bytes</td>
            <td>
                <form method="POST" action="/admin/confirm" style="display:inline">
                    <input type="hidden" name="blob_name" value="{a['blob_name']}">
                    <button type="submit" class="btn confirm">Confirm</button>
                </form>
                <form method="POST" action="/admin/reject" style="display:inline">
                    <input type="hidden" name="blob_name" value="{a['blob_name']}">
                    <button type="submit" class="btn reject">Reject</button>
                </form>
                <a href="/admin/view?blob={a['blob_name']}" target="_blank" class="btn view">View</a>
            </td>
        </tr>"""
        sections += f"""
    <h2 class="date-header">{date} <span class="date-count">({len(date_articles)} articles)</span></h2>
    <table>
        <thead><tr><th>Filename</th><th>Size</th><th>Action</th></tr></thead>
        <tbody>{rows}</tbody>
    </table>"""

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Crisis Article Review</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        h1 {{ color: #c0392b; }}
        h2.date-header {{ color: #2c3e50; margin-top: 32px; margin-bottom: 8px; font-size: 18px; }}
        .date-count {{ color: #888; font-size: 14px; font-weight: normal; }}
        table {{ border-collapse: collapse; width: 100%; background: white; box-shadow: 0 1px 4px rgba(0,0,0,0.1); margin-bottom: 24px; }}
        th, td {{ padding: 12px 16px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #2c3e50; color: white; }}
        tr:hover {{ background: #fafafa; }}
        .btn {{ padding: 6px 14px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; text-decoration: none; display: inline-block; }}
        .confirm {{ background: #27ae60; color: white; }}
        .reject {{ background: #e74c3c; color: white; margin-left: 6px; }}
        .view {{ background: #2980b9; color: white; margin-left: 6px; }}
        .empty {{ color: #888; padding: 20px; text-align: center; }}
        .count {{ color: #555; margin-bottom: 16px; }}
    </style>
</head>
<body>
    <h1>Crisis Article Review</h1>
    <p class="count">Pending articles: <strong>{len(articles)}</strong></p>
    {sections if articles else '<p class="empty">No pending articles.</p>'}
</body>
</html>"""
    return html


@app.route("/admin/view", methods=["GET"])
def admin_view_article():
    """View raw content of a pending article."""
    blob_name = request.args.get('blob', '')
    crisis_bucket = os.environ.get('CRISIS_BUCKET', '')
    if not blob_name or not crisis_bucket:
        return "Missing parameters", 400
    try:
        content = read_article_from_gcs(crisis_bucket, blob_name)
        if content is None:
            return "Article not found", 404
        return f"<pre style='font-family:monospace;padding:20px;white-space:pre-wrap'>{content}</pre>"
    except Exception as e:
        return f"Error: {e}", 500


@app.route("/admin/confirm", methods=["POST"])
def admin_confirm():
    """Move a pending article to crisis_articles/."""
    blob_name = request.form.get('blob_name', '')
    crisis_bucket = os.environ.get('CRISIS_BUCKET', '')
    if not blob_name or not crisis_bucket:
        return "Missing parameters", 400

    try:
        client = storage.Client()
        bucket = client.bucket(crisis_bucket)
        source_blob = bucket.blob(blob_name)

        # pending_review/{date}/{filename} -> crisis_articles/{date}/{filename}
        destination_name = blob_name.replace('pending_review/', 'crisis_articles/', 1)
        bucket.copy_blob(source_blob, bucket, destination_name)
        source_blob.delete()

        logger.info(f"✅ Confirmed: {blob_name} -> {destination_name}")
    except Exception as e:
        logger.error(f"❌ Confirm failed: {e}")
        return f"Error: {e}", 500

    return redirect('/admin')


@app.route("/admin/reject", methods=["POST"])
def admin_reject():
    """Delete a pending article (reject it)."""
    blob_name = request.form.get('blob_name', '')
    crisis_bucket = os.environ.get('CRISIS_BUCKET', '')
    if not blob_name or not crisis_bucket:
        return "Missing parameters", 400

    try:
        client = storage.Client()
        bucket = client.bucket(crisis_bucket)
        bucket.blob(blob_name).delete()
        logger.info(f"🗑️  Rejected: {blob_name}")
    except Exception as e:
        logger.error(f"❌ Reject failed: {e}")
        return f"Error: {e}", 500

    return redirect('/admin')


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "model_loaded": MODEL is not None}), 200


# Load model at module import time (when gunicorn starts)
logger.info("=" * 60)
logger.info("🚀 Starting Crisis Classifier Service...")
logger.info(f"📦 Loading model from: {MODEL_PATH}")
try:
    import sklearn
    logger.info(f"🔬 sklearn version: {sklearn.__version__}")
except ImportError:
    logger.warning("⚠️  sklearn not installed")
logger.info("=" * 60)
try:
    MODEL = load_crisis_model(MODEL_PATH)
    logger.info("=" * 60)
    logger.info("✅ Model loaded successfully, ready to classify!")
    logger.info("=" * 60)
except Exception as e:
    MODEL = None
    logger.warning("=" * 60)
    logger.warning(f"⚠️  Model not loaded: {e}")
    logger.warning("⚠️  Classification disabled. Admin routes still available.")
    logger.warning("=" * 60)


if __name__ == "__main__":
    # Run Flask app directly (for local testing)
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)