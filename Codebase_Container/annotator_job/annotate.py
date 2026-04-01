import os
import re
import logging
import time
from flask import Flask, request, jsonify
from google.cloud import storage
from google import genai

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

ANNOTATION_PROMPT = """
1. Wrap each disaster event in the article with `<event>` and `</event>` tags.

2. Only add a tag when the text describes a real disaster event.

   The scope of disasters includes: **Fire, Airstrike, Armed Conflict, Natural Disaster, Attack, and Bombing**.

3. Consider multiple sentences as the **same event** and use a single tag if all of the following are true:

   * They refer to the same date,

   * They occur in the same location,

   * They describe the same disaster incident.

   The tag should cover all related information about that event on that day, such as damages, casualties, and response actions.

4. Create a new `<event>` tag when any of these change:

   * The date is different,

   * The location is different,(ignore the township level)

   * The incident is separate and unrelated to the previous one.

5. Do not create one tag per sentence. One disaster event should have only one continuous tag that spans all directly related text.


6. Do not tag only the disaster word (e.g., "fire" or "earthquake"). Tag the full span of text that describes the event and its immediate effects.


7. Do not tag events that happened in the past if they are mentioned only as background or historical context.


8. Only tag events that are reported as happening in the current report time, specifically when the article indicates timing such as **"today" or "yesterday."**

   If there is no clear current-day reference, do not tag the event. But tag if the event yesterday or today is connected to the same event.


9. If multiple descriptions refer to connected parts of the same ongoing disaster on the same day (for example, flooding affecting nearby areas as part of the same incident), group them under one `<event>` tag.


10. Use time expressions carefully to decide whether the text refers to:

* the same ongoing event (use one tag), or

* a different event in time or place (use a new tag).

* a same event connected in different location (use a new tag).

11. When annotating, it is **not necessary to include or mention displacement information** (e.g., people being evacuated or moved or soldiers being relocated or fleeing away) as part of deciding or defining the disaster event. But if it is happening in the same sentence together and connected with the event cosinder that sentence as the event together.

12. Also tag supporting details for that same event if it is disaster related.

13. Do not cut off from the middle of the sentence and always take from the begining of the event sentence.
"""


def annotate_article(article_text: str, gemini_client) -> str:
    """Annotate a single article using Gemini."""
    full_prompt = ANNOTATION_PROMPT + "\n\nArticle:\n" + article_text
    response = gemini_client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=full_prompt
    )
    return response.text


@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "service": "dvb-annotator",
        "status": "ok",
        "usage": "Send Eventarc-compatible POST requests to / and GET requests to /health for health checks."
    }), 200


@app.route("/", methods=["POST"])
def handle_event():
    """Handle Eventarc GCS notification when a file lands in crisis_articles/."""
    try:
        event_data = request.get_json()

        logger.info("=" * 60)
        logger.info("RECEIVED EVENTARC WEBHOOK - ANNOTATOR")
        logger.info("=" * 60)

        # Extract object name from event
        if 'data' in event_data:
            object_name = event_data['data'].get('name', '')
            bucket_name = event_data['data'].get('bucket', '')
        else:
            object_name = event_data.get('name', '')
            bucket_name = event_data.get('bucket', '')

        logger.info(f"📄 Object: {object_name}")
        logger.info(f"📦 Bucket: {bucket_name}")

        # Only process .txt files in crisis_articles/
        if not object_name.startswith('crisis_articles/') or not object_name.endswith('.txt'):
            logger.info(f"⏭️  Ignoring: {object_name}")
            return jsonify({"status": "ignored"}), 200

        # Extract date and filename: crisis_articles/{date}/{filename}
        match = re.match(r'crisis_articles/(\d{4}-\d{2}-\d{2})/(.+\.txt)', object_name)
        if not match:
            logger.warning(f"⚠️  Could not parse path: {object_name}")
            return jsonify({"status": "error", "reason": "invalid path"}), 400

        date_str = match.group(1)
        filename = match.group(2)
        logger.info(f"📅 Date: {date_str}")
        logger.info(f"📝 File: {filename}")

        crisis_bucket = os.environ.get('CRISIS_BUCKET')
        gemini_api_key = os.environ.get('GEMINI_API_KEY')

        if not crisis_bucket or not gemini_api_key:
            logger.error("❌ Missing env vars: CRISIS_BUCKET, GEMINI_API_KEY")
            return jsonify({"status": "error", "reason": "missing env vars"}), 500

        # Check if already annotated
        storage_client = storage.Client()
        bucket = storage_client.bucket(crisis_bucket)
        annotated_blob_name = f"annotated_articles/{date_str}/{filename}"
        annotated_blob = bucket.blob(annotated_blob_name)
        if annotated_blob.exists():
            logger.info(f"⏭️  Already annotated: {annotated_blob_name}")
            return jsonify({"status": "skipped", "reason": "already annotated"}), 200

        # Download article
        source_blob = bucket.blob(object_name)
        article_text = source_blob.download_as_text(encoding='utf-8')
        logger.info(f"✅ Downloaded article ({len(article_text)} chars)")

        # Annotate with Gemini
        gemini_client = genai.Client(api_key=gemini_api_key)
        logger.info("🤖 Annotating with Gemini...")
        annotated_text = annotate_article(article_text, gemini_client)
        logger.info("✅ Annotation complete")

        # Save annotated output
        annotated_blob.upload_from_string(annotated_text, content_type='text/plain; charset=utf-8')
        logger.info(f"✅ Saved to gs://{crisis_bucket}/{annotated_blob_name}")

        return jsonify({
            "status": "success",
            "date": date_str,
            "filename": filename,
            "annotated_path": annotated_blob_name
        }), 200

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
