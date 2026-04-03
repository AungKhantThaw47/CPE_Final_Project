import os
import re
import logging
import hashlib
import requests
from flask import Flask, request, jsonify
from google.cloud import storage

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

EXTRACTION_PROMPT = '''You are an information extraction system. Your task is to read an article that contains one or more <event> ... </event> blocks and extract structured information only from the text inside those blocks.

Follow the instructions below exactly. Generate the extracted information in English only, and do not produce any output based on text outside the <event> tags.

If the article contains:
	•	One <event> ... </event> block → output one JSON object (wrapped in a JSON array).
	•	Two or three <event> ... </event> blocks → output two or three JSON objects in one JSON array.

You must output exactly one JSON object per <event> block.

IMPORTANT OUTPUT RULES:
	•	Return ONLY the JSON array.
	•	Do NOT include explanations, reasoning, or any additional text.
	•	Do NOT use markdown code blocks (no ```json).
	•	Start your response directly with [ and end with ].
	•	No text before [ or after ].
	•	civilian_fatalities and armed_personnel_fatalities must be integers only when provided (not strings).
	•	number_of_people_displaced must be an integer if provided; otherwise "NA".

SCOPE AND SPECIAL RULES (VERY IMPORTANT)
	1.	The article contains text both inside and outside <event> ... </event> tags.
	2.	You must completely ignore any text outside <event> ... </event> tags.
		•	Treat outside text as if it does not exist.
		•	Do NOT use it to fill missing fields, refine locations, or guess dates.
	3.	Each <event> ... </event> block represents exactly one distinct event.
		•	Output one and only one JSON object for each <event> block.
		•	Do NOT split one <event> block into multiple events.
		•	Do NOT merge multiple <event> blocks into one event.
	4.	If there are multiple <event> blocks, your response must be a single JSON array:
[ {...}, {...}, ... ]

⸻
CRISIS TYPE DEFINITIONS
Use the following rules to decide crisis_type:
	•	Armed Conflict – Fighting between two or more armed organizations (military, militias, armed groups) in combat over territory, resistance, or control.
	•	Attack – Unilateral violence by armed actors directly targeting civilians.
	•	Airstrike – Explosive or projectile attacks carried out from the air by planes, helicopters, or drones.
	•	Bombing – Ground-based planted or manually delivered explosives.
	•	Fire – Armed organizations deliberately use arson to burn homes, buildings, villages, or vehicles.
	•	Natural disaster – Crises caused by natural forces such as floods, earthquakes, or landslides (not human actors).

⸻
FIELD GUIDELINES
	•	crisis_type – Must be exactly one of the six categories above.
	•	location – Comma-separated address including only the parts that are known, in this order: Township (if known), Region OR State (if known), Country.
Do NOT include districts, villages, street names, or specific landmarks.
Do NOT use "NA" as a placeholder for unknown parts — simply omit them.
If only the country is known, use just the country (e.g., Myanmar).
If only the state is known, use State, Country (e.g., Rakhine State, Myanmar).
Only use "NA" if the location is completely unknown.
Example: Mawlamyine Township, Mon State, Myanmar
	•	date – Use DD/MM/YYYY format (example: 13/03/2023). Do not rely only on explicitly written calendar dates. If the event text uses relative time expressions such as "yesterday", "today", or "last night", convert them into an exact DD/MM/YYYY date by using the article's publication date (the source date) as the reference. If not mentioned anywhere, use "NA".
	•	affected_civilian – "TRUE" if civilians are mentioned as affected (killed, injured, captured), "FALSE" if explicitly stated as not affected, "NA" if not mentioned.
	•	affected_women – "TRUE" if women are mentioned as affected, "FALSE" if explicitly stated as not affected, "NA" if not mentioned.
	•	affected_children – "TRUE" if children are mentioned as affected, "FALSE" if explicitly stated as not affected, "NA" if not mentioned.
	•	civilian_properties_damage – "TRUE" only if civilian-owned properties are damaged (do not count military/armed group facilities). "FALSE" if civilian properties are explicitly not damaged. "NA" if not mentioned.
	•	civilian_forced_displacement – "TRUE" if civilians are explicitly described as fleeing, being evacuated, or forcibly displaced. "FALSE" if explicitly stated that no displacement occurred. "NA" if not mentioned.
	•	civilian_fatalities – Integer count of civilian deaths (e.g., 3). If not clearly stated or not given, use "NA".
	•	armed_personnel_fatalities – Integer count of armed personnel deaths (military, PDF, armed groups). If not clearly stated or not given, use "NA".
	•	number_of_people_displaced – Integer count if explicitly provided; otherwise "NA".
	•	involved_parties –

	INVOLVED PARTIES (CRITICAL RULES):
	This list must include ONLY the organized groups (military, militias, or rebel groups) that are active combatants or primary perpetrators of the event.
	In Armed Conflict: Include all organizations actively fighting each other.
	In Airstrike, Bombing, or Fire: Include only the organization(s) that carried out the action. Don't include other organizations that are victims. Just consider main organization that caused the event.
	Format: A list of strings, e.g., ["Military", "People's Defense Force (PDF)"]. Return [] if none.
	Natural Disaster Rule: If crisis_type is Natural disaster, the involved_parties key must be omitted entirely from the JSON object.

Article:
'''


def build_pipeline_output_hash(source_hash: str, content_hash: str) -> str:
    """Build deterministic folder hash from upstream hash + current content hash."""
    content_hash = (content_hash or "unknown-hash").strip()
    source_hash = (source_hash or "").strip()

    if not source_hash:
        return content_hash

    return hashlib.sha256(f"{source_hash}:{content_hash}".encode("utf-8")).hexdigest()


def extract_events(article_text: str, api_key: str) -> str:
    """Extract crisis events from annotated article using Gemini REST API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={api_key}"

    payload = {
        "contents": [{"parts": [{"text": EXTRACTION_PROMPT + article_text}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }

    response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})

    if response.status_code == 200:
        result = response.json()
        return result["candidates"][0]["content"]["parts"][0]["text"]
    else:
        raise RuntimeError(f"Gemini API error: {response.status_code} - {response.text}")


@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "service": "dvb-extractor",
        "status": "ok",
        "usage": "Send Eventarc-compatible POST requests to / and GET requests to /health for health checks."
    }), 200


@app.route("/", methods=["POST"])
def handle_event():
    """Handle Eventarc GCS notification when a file lands in annotated_articles/."""
    try:
        event_data = request.get_json()

        logger.info("=" * 60)
        logger.info("RECEIVED EVENTARC WEBHOOK - EXTRACTOR")
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

        # Only process .txt files in annotated_articles/
        if not object_name.startswith('annotated_articles/') or not object_name.endswith('.txt'):
            logger.info(f"⏭️  Ignoring: {object_name}")
            return jsonify({"status": "ignored"}), 200

        # Parse source path
        # hashed: annotated_articles/{hash}/{date}/{filename}
        # legacy: annotated_articles/{date}/{filename}
        hash_match = re.match(r'annotated_articles/([^/]+)/(\d{4}-\d{2}-\d{2})/(.+\.txt)', object_name)
        legacy_match = re.match(r'annotated_articles/(\d{4}-\d{2}-\d{2})/(.+\.txt)', object_name)

        if hash_match:
            source_hash = hash_match.group(1)
            date_str = hash_match.group(2)
            filename = hash_match.group(3)
        elif legacy_match:
            source_hash = "legacy"
            date_str = legacy_match.group(1)
            filename = legacy_match.group(2)
        else:
            logger.warning(f"⚠️  Could not parse path: {object_name}")
            return jsonify({"status": "error", "reason": "invalid path"}), 400

        output_hash = build_pipeline_output_hash(
            source_hash,
            os.environ.get('CONTENT_HASH', 'unknown-hash').strip(),
        )
        logger.info(f"📅 Date: {date_str}")
        logger.info(f"🔎 Source hash: {source_hash}")
        logger.info(f"🧬 Output hash: {output_hash}")
        logger.info(f"📝 File: {filename}")

        crisis_bucket = os.environ.get('CRISIS_BUCKET')
        extraction_bucket = os.environ.get('EXTRACTION_BUCKET')
        gemini_api_key = os.environ.get('GEMINI_API_KEY')

        if not crisis_bucket or not extraction_bucket or not gemini_api_key:
            logger.error("❌ Missing env vars: CRISIS_BUCKET, EXTRACTION_BUCKET, GEMINI_API_KEY")
            return jsonify({"status": "error", "reason": "missing env vars"}), 500

        # Check if already extracted
        storage_client = storage.Client()
        source_bucket = storage_client.bucket(crisis_bucket)
        output_bucket = storage_client.bucket(extraction_bucket)
        output_filename = filename.replace('.txt', '.json')
        extracted_blob_name = f"extracted_events/{output_hash}/{date_str}/{output_filename}"
        extracted_blob = output_bucket.blob(extracted_blob_name)
        if extracted_blob.exists():
            logger.info(f"⏭️  Already extracted: {extracted_blob_name}")
            return jsonify({"status": "skipped", "reason": "already extracted"}), 200

        # Download annotated article from crisis bucket
        source_blob = source_bucket.blob(object_name)
        article_text = source_blob.download_as_text(encoding='utf-8')
        logger.info(f"✅ Downloaded annotated article ({len(article_text)} chars)")

        # Extract with Gemini
        logger.info("🤖 Extracting with Gemini...")
        result = extract_events(article_text, gemini_api_key)
        logger.info("✅ Extraction complete")

        # Save to extraction bucket
        extracted_blob.upload_from_string(result, content_type='application/json')
        logger.info(f"✅ Saved to gs://{extraction_bucket}/{extracted_blob_name}")

        return jsonify({
            "status": "success",
            "date": date_str,
            "filename": filename,
            "extracted_path": extracted_blob_name
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
