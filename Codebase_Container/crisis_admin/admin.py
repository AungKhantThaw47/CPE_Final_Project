import os
import logging
import sys
import re
from collections import defaultdict
from datetime import datetime
from flask import Flask, request, jsonify, redirect
from google.cloud import storage
from typing import List, Dict, Optional


if "/workspace" not in sys.path:
    sys.path.append("/workspace")

from utils.neo4j_utils import query_latest_hash_from_neo4j_env

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/", methods=["GET"])
def root():
    return redirect("/admin")


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


def resolve_latest_hash(bucket, prefix: str) -> Optional[str]:
    """Resolve latest hash folder under prefix/ by blob update time."""
    pattern = re.compile(rf"^{re.escape(prefix)}/([^/]+)/")
    latest_by_hash = {}

    for blob in bucket.list_blobs(prefix=f"{prefix}/"):
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


def list_pending_articles(crisis_bucket: str) -> List[Dict]:
    """List pending articles from latest hash folder (with legacy fallback)."""
    client = storage.Client()
    bucket = client.bucket(crisis_bucket)
    latest_hash = (
        os.environ.get("SOURCE_CONTENT_HASH", "").strip()
        or query_latest_hash_from_neo4j_env("job:crisis-classifier-job")
        or resolve_latest_hash(bucket, "pending_review")
    )
    if latest_hash:
        blobs = list(bucket.list_blobs(prefix=f"pending_review/{latest_hash}/"))
    else:
        blobs = list(bucket.list_blobs(prefix="pending_review/"))

    articles = []
    for blob in blobs:
        if blob.name.endswith('.txt'):
            # hashed: pending_review/{hash}/{date}/{filename}
            # legacy: pending_review/{date}/{filename}
            hash_match = re.match(r"^pending_review/([^/]+)/([0-9]{4}-[0-9]{2}-[0-9]{2})/(.+\.txt)$", blob.name)
            legacy_match = re.match(r"^pending_review/([0-9]{4}-[0-9]{2}-[0-9]{2})/(.+\.txt)$", blob.name)

            if hash_match:
                hash_value = hash_match.group(1)
                date = hash_match.group(2)
                filename = hash_match.group(3)
            elif legacy_match:
                hash_value = "legacy"
                date = legacy_match.group(1)
                filename = legacy_match.group(2)
            else:
                continue

            articles.append({
                'blob_name': blob.name,
                'filename': filename,
                'date': date,
                'hash': hash_value,
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
            <td>{a['hash']}</td>
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
        <thead><tr><th>Filename</th><th>Hash</th><th>Size</th><th>Action</th></tr></thead>
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
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
