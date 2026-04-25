import os
import logging
import sys
import re
from html import escape
from collections import defaultdict
from datetime import datetime
from flask import Flask, request, jsonify, redirect
from google.cloud import storage
import google.auth
from google.auth.transport.requests import AuthorizedSession
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


def trigger_cloud_run_job(job_name: str) -> None:
    """Trigger a Cloud Run job asynchronously from admin actions."""
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "")
    region = os.environ.get("GCP_REGION", "asia-southeast1")
    if not project_id:
        logger.warning("⚠️  GOOGLE_CLOUD_PROJECT(_ID) not set; skipping job trigger for %s", job_name)
        return

    try:
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        authed_session = AuthorizedSession(credentials)
        url = (
            f"https://{region}-run.googleapis.com/apis/run.googleapis.com/v1/"
            f"namespaces/{project_id}/jobs/{job_name}:run"
        )
        response = authed_session.post(url, json={})
        if 200 <= response.status_code < 300:
            logger.info("🚀 Triggered Cloud Run job: %s", job_name)
        else:
            logger.error("❌ Failed to trigger job %s: %s %s", job_name, response.status_code, response.text)
    except Exception as exc:
        logger.error("❌ Error triggering job %s: %s", job_name, exc)


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


def list_stage_articles(crisis_bucket: str, stage_prefix: str, latest_hash_key: str) -> List[Dict]:
    """List stage articles from latest hash folder (with legacy fallback)."""
    client = storage.Client()
    bucket = client.bucket(crisis_bucket)
    latest_hash = (
        os.environ.get("SOURCE_CONTENT_HASH", "").strip()
        or query_latest_hash_from_neo4j_env(latest_hash_key)
        or resolve_latest_hash(bucket, stage_prefix)
    )
    if latest_hash:
        blobs = list(bucket.list_blobs(prefix=f"{stage_prefix}/{latest_hash}/"))
    else:
        blobs = list(bucket.list_blobs(prefix=f"{stage_prefix}/"))

    articles = []
    for blob in blobs:
        if blob.name.endswith('.txt'):
            # hashed: {stage_prefix}/{hash}/{date}/{filename}
            # legacy: {stage_prefix}/{date}/{filename}
            hash_match = re.match(rf"^{re.escape(stage_prefix)}/([^/]+)/([0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}})/(.+\.txt)$", blob.name)
            legacy_match = re.match(rf"^{re.escape(stage_prefix)}/([0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}})/(.+\.txt)$", blob.name)

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


def list_pending_articles(crisis_bucket: str) -> List[Dict]:
    return list_stage_articles(crisis_bucket, "pending_review", "job:crisis-classifier-job")


def list_pending_annotation_articles(crisis_bucket: str) -> List[Dict]:
    return list_stage_articles(crisis_bucket, "pending_review_annotation", "job:dvb-annotator-job")


def render_stage_tables(
    articles: List[Dict],
    section_title: str,
    confirm_action: str,
    reject_action: str,
    empty_text: str,
) -> str:
    by_date = defaultdict(list)
    for article in articles:
        by_date[article['date']].append(article)

    sorted_dates = sorted(by_date.keys())
    if not sorted_dates:
        return f"<h2 class='stage-header'>{escape(section_title)}</h2><p class='empty'>{escape(empty_text)}</p>"

    sections = f"<h2 class='stage-header'>{escape(section_title)}</h2>"
    for date in sorted_dates:
        date_articles = by_date[date]
        rows = ""
        for article in date_articles:
            rows += f"""
        <tr>
            <td>{escape(article['filename'])}</td>
            <td>{escape(article['hash'])}</td>
            <td>{article['size']} bytes</td>
            <td>
                <form method="POST" action="{escape(confirm_action)}" style="display:inline">
                    <input type="hidden" name="blob_name" value="{escape(article['blob_name'])}">
                    <button type="submit" class="btn confirm">Confirm</button>
                </form>
                <form method="POST" action="{escape(reject_action)}" style="display:inline">
                    <input type="hidden" name="blob_name" value="{escape(article['blob_name'])}">
                    <button type="submit" class="btn reject">Reject</button>
                </form>
                <a href="/admin/view?blob={escape(article['blob_name'])}" target="_blank" class="btn view">View</a>
            </td>
        </tr>"""

        sections += f"""
    <h3 class="date-header">{escape(date)} <span class="date-count">({len(date_articles)} articles)</span></h3>
    <table>
        <thead><tr><th>Filename</th><th>Hash</th><th>Size</th><th>Action</th></tr></thead>
        <tbody>{rows}</tbody>
    </table>"""

    return sections


@app.route("/admin", methods=["GET"])
def admin_page():
    """Admin HTML page for reviewing pending and annotated crisis queues."""
    crisis_bucket = os.environ.get('CRISIS_BUCKET', '')
    try:
        pending_articles = list_pending_articles(crisis_bucket) if crisis_bucket else []
        pending_annotation_articles = list_pending_annotation_articles(crisis_bucket) if crisis_bucket else []
    except Exception as e:
        pending_articles = []
        pending_annotation_articles = []
        logger.error(f"Error listing pending articles: {e}")

    pending_section = render_stage_tables(
        pending_articles,
        "Pending Classification Review",
        "/admin/confirm",
        "/admin/reject",
        "No pending classification articles."
    )
    annotation_section = render_stage_tables(
        pending_annotation_articles,
        "Pending Annotation Review",
        "/admin/confirm_annotation",
        "/admin/reject_annotation",
        "No pending annotation articles."
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Crisis Article Review</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        h1 {{ color: #c0392b; }}
        h2.stage-header {{ color: #2c3e50; margin-top: 32px; margin-bottom: 8px; font-size: 20px; }}
        h3.date-header {{ color: #2c3e50; margin-top: 24px; margin-bottom: 8px; font-size: 16px; }}
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
    <p class="count">Pending classification: <strong>{len(pending_articles)}</strong></p>
    <p class="count">Pending annotation review: <strong>{len(pending_annotation_articles)}</strong></p>
    {pending_section}
    {annotation_section}
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
    """Move a pending article to crisis_articles/ and trigger annotation job."""
    blob_name = request.form.get('blob_name', '')
    crisis_bucket = os.environ.get('CRISIS_BUCKET', '')
    if not blob_name or not crisis_bucket:
        return "Missing parameters", 400

    try:
        client = storage.Client()
        bucket = client.bucket(crisis_bucket)
        source_blob = bucket.blob(blob_name)

        # pending_review/{hash}/{date}/{filename} -> crisis_articles/{hash}/{date}/{filename}
        destination_name = blob_name.replace('pending_review/', 'crisis_articles/', 1)
        bucket.copy_blob(source_blob, bucket, destination_name)
        source_blob.delete()
        trigger_cloud_run_job("dvb-annotator-job")

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


@app.route("/admin/confirm_annotation", methods=["POST"])
def admin_confirm_annotation():
    """Move a pending annotated article to annotated_articles/ and trigger extractor job."""
    blob_name = request.form.get('blob_name', '')
    crisis_bucket = os.environ.get('CRISIS_BUCKET', '')
    if not blob_name or not crisis_bucket:
        return "Missing parameters", 400

    try:
        client = storage.Client()
        bucket = client.bucket(crisis_bucket)
        source_blob = bucket.blob(blob_name)

        # pending_review_annotation/{hash}/{date}/{filename} -> annotated_articles/{hash}/{date}/{filename}
        destination_name = blob_name.replace('pending_review_annotation/', 'annotated_articles/', 1)
        bucket.copy_blob(source_blob, bucket, destination_name)
        source_blob.delete()
        trigger_cloud_run_job("dvb-extractor-job")

        logger.info(f"✅ Confirmed annotation: {blob_name} -> {destination_name}")
    except Exception as e:
        logger.error(f"❌ Annotation confirm failed: {e}")
        return f"Error: {e}", 500

    return redirect('/admin')


@app.route("/admin/reject_annotation", methods=["POST"])
def admin_reject_annotation():
    """Delete a pending annotated article (reject it)."""
    blob_name = request.form.get('blob_name', '')
    crisis_bucket = os.environ.get('CRISIS_BUCKET', '')
    if not blob_name or not crisis_bucket:
        return "Missing parameters", 400

    try:
        client = storage.Client()
        bucket = client.bucket(crisis_bucket)
        bucket.blob(blob_name).delete()
        logger.info(f"🗑️  Rejected annotation: {blob_name}")
    except Exception as e:
        logger.error(f"❌ Annotation reject failed: {e}")
        return f"Error: {e}", 500

    return redirect('/admin')


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
