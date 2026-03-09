import os
import logging
import sys
from collections import defaultdict
from flask import Flask, request, jsonify, redirect
from google.cloud import storage
from typing import List, Dict, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


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
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
