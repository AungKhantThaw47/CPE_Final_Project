import json
import requests
from google.cloud import storage

GEMINI_API_KEY = "AIzaSyAlJAlqCx7VuAc2ViZnExUrzbeoKQkuXyQ"
CRISIS_BUCKET = "cpe-final-project-crisis-crawler-data"
EXTRACTION_BUCKET = "llm-extraction"

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


def extract_events(article_text: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": EXTRACTION_PROMPT + article_text}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
    if response.status_code != 200:
        raise RuntimeError(f"Gemini API error: {response.status_code} - {response.text}")
    return response.json()["candidates"][0]["content"]["parts"][0]["text"]


def main():
    storage_client = storage.Client()
    source_bucket = storage_client.bucket(CRISIS_BUCKET)
    output_bucket = storage_client.bucket(EXTRACTION_BUCKET)

    # List annotated articles from crisis bucket
    blobs = list(source_bucket.list_blobs(prefix="annotated_articles/"))
    txt_blobs = [b for b in blobs if b.name.endswith(".txt")]

    if not txt_blobs:
        print("No annotated articles found in annotated_articles/")
        return

    print(f"Found {len(txt_blobs)} annotated article(s):")
    for i, b in enumerate(txt_blobs):
        print(f"  [{i}] {b.name}")

    # Process all articles
    for blob in txt_blobs:
        object_name = blob.name  # e.g. annotated_articles/2026-03-05/article.txt
        parts = object_name.split("/")
        if len(parts) < 3:
            continue
        date_str = parts[1]
        filename = parts[2]
        output_filename = filename.replace(".txt", ".json")
        extracted_blob_name = f"extracted_events/{date_str}/{output_filename}"

        # Skip if already extracted
        extracted_blob = output_bucket.blob(extracted_blob_name)
        if extracted_blob.exists():
            print(f"⏭️  Already extracted: {extracted_blob_name}")
            continue

        print(f"\n📄 Processing: {object_name}")
        article_text = blob.download_as_text(encoding="utf-8")
        print(f"   Downloaded ({len(article_text)} chars)")

        print("   🤖 Extracting with Gemini...")
        result = extract_events(article_text)
        print(f"   ✅ Result: {result[:200]}...")

        # Save to extraction bucket
        extracted_blob.upload_from_string(result, content_type="application/json")
        print(f"   ✅ Saved to gs://{EXTRACTION_BUCKET}/{extracted_blob_name}")

        # Also save locally for inspection
        local_file = f"extracted_{filename.replace('.txt', '.json')}"
        with open(local_file, "w", encoding="utf-8") as f:
            parsed = json.loads(result)
            json.dump(parsed, f, indent=2, ensure_ascii=False)
        print(f"   💾 Also saved locally: {local_file}")


if __name__ == "__main__":
    main()
