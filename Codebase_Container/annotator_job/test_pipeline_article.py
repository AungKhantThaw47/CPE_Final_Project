"""
Diagnostic script: downloads a real crisis_articles/ file from GCS and runs it
through the annotation prompt locally so you can compare against pipeline output.

Usage:
    CRISIS_BUCKET=your-project-pipeline-data GEMINI_API_KEY=xxx python test_pipeline_article.py
"""

import os
import sys
from google.cloud import storage
from google import genai

CRISIS_BUCKET = os.environ.get("CRISIS_BUCKET", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyAlJAlqCx7VuAc2ViZnExUrzbeoKQkuXyQ")

if not CRISIS_BUCKET:
    print("❌ Set CRISIS_BUCKET env var to your pipeline data bucket name")
    print("   e.g.  CRISIS_BUCKET=my-project-pipeline-data python test_pipeline_article.py")
    sys.exit(1)

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

# --- 1. List crisis_articles/ files ---
print(f"📦 Bucket: {CRISIS_BUCKET}")
storage_client = storage.Client()
bucket = storage_client.bucket(CRISIS_BUCKET)

blobs = [
    b for b in bucket.list_blobs(prefix="crisis_articles/")
    if not b.name.endswith("/") and b.name.endswith(".txt")
]

if not blobs:
    print("❌ No .txt files found under crisis_articles/")
    sys.exit(1)

print(f"✅ Found {len(blobs)} article(s) in crisis_articles/")
for i, b in enumerate(blobs[:10]):
    print(f"  [{i}] {b.name}")

# Pick the first one (or change the index below)
target = blobs[0]
print(f"\n📄 Testing with: {target.name}")

# --- 2. Download ---
article_text = target.download_as_text(encoding="utf-8")
print(f"✅ Downloaded ({len(article_text)} chars)")
print("\n--- ORIGINAL ARTICLE ---")
print(article_text)

# --- 3. Annotate locally ---
print("\n🤖 Annotating with Gemini...")
client = genai.Client(api_key=GEMINI_API_KEY)
full_prompt = ANNOTATION_PROMPT + "\n\nArticle:\n" + article_text
response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents=full_prompt
)

annotated = response.text
print("\n--- ANNOTATED OUTPUT ---")
print(annotated)

# --- 4. Check result ---
has_tags = "<event>" in annotated
print("\n" + "=" * 60)
if has_tags:
    print("✅ Tags found — prompt is working correctly for this article")
else:
    print("❌ No <event> tags in output — prompt did not annotate this article")
    print("   Possible causes:")
    print("   1. Article has no 'today'/'yesterday' time reference (Rule 8)")
    print("   2. Article content does not match disaster categories")
    print("   3. Encoding or formatting issue in the article")

# Save both for comparison
with open("pipeline_article_original.txt", "w", encoding="utf-8") as f:
    f.write(article_text)
with open("pipeline_article_annotated.txt", "w", encoding="utf-8") as f:
    f.write(annotated)
print("\n💾 Saved: pipeline_article_original.txt and pipeline_article_annotated.txt")
