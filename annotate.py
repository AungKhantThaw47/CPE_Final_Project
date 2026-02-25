import os
from google.cloud import storage
from google import genai

# ===============================
# PUT YOUR VALUES HERE
# ===============================
PROJECT_ID = "cpe-final-project"
BUCKET_NAME = "cpe-final-project-crawler-data"
PREFIX = "dvb/2026-02-08/"


# ===============================
# Configure Gemini (API Key Mode)
# ===============================
client_genai = genai.Client(
    api_key="AIzaSyAlJAlqCx7VuAc2ViZnExUrzbeoKQkuXyQ"
)
# ===============================
# Create Storage Client
# (Uses gcloud auth automatically)
# ===============================
storage_client = storage.Client(project=PROJECT_ID)

# ===============================
# Annotation Prompt
# ===============================
ANNOTATION_PROMPT = """
1. Wrap each disaster event in the article with `<event1>` and `</event1>` tags.

2. Only add a tag when the text describes a real disaster event.

   The scope of disasters includes: **Fire, Armed Conflict, Natural Disaster, Attack, and Bombing**.

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


6. Do not tag only the disaster word (e.g., “fire” or “earthquake”). Tag the full span of text that describes the event and its immediate effects.


7. Do not tag events that happened in the past if they are mentioned only as background or historical context.


8. Only tag events that are reported as happening in the current report time, specifically when the article indicates timing such as **“today” or “yesterday.”**

   If there is no clear current-day reference, do not tag the event. But tag if the event yesterday or today is connected to the same event. 


9. If multiple descriptions refer to connected parts of the same ongoing disaster on the same day (for example, flooding affecting nearby areas as part of the same incident), group them under one `<event>` tag.


10. Use time expressions carefully to decide whether the text refers to:

* the same ongoing event (use one tag), or

* a different event in time or place (use a new tag).

* a same event connected in different location (use a new tag).  

11. When annotating, it is **not necessary to include or mention displacement information** (e.g., people being evacuated or moved) as part of deciding or defining the disaster event.

12. Also tag supporting details for that same event if it is disaster related.
"""

# ===============================
# Main Process
# ===============================
os.makedirs("downloaded_txt", exist_ok=True)
os.makedirs("annotated_output", exist_ok=True)

blobs = storage_client.list_blobs(BUCKET_NAME, prefix=PREFIX)

for blob in blobs:

    if blob.name.endswith(".txt"):

        filename = blob.name.split("/")[-1]
        local_path = os.path.join("downloaded_txt", filename)

        print("Downloading:", filename)
        blob.download_to_filename(local_path)

        with open(local_path, "r", encoding="utf-8") as f:
            article_text = f.read()

        full_prompt = ANNOTATION_PROMPT + "\n\nArticle:\n" + article_text

        print("Annotating:", filename)

        response = client_genai.models.generate_content(
            model="gemini-3",
            contents=full_prompt

        )
        
        import time

        response = client_genai.models.generate_content(
        model="gemini-3",
        contents=full_prompt
)

        time.sleep(30)

        output_path = os.path.join(
            "annotated_output",
            filename.replace(".txt", "_annotated.txt")
        )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(response.text)

        print("Saved:", output_path)

print("DONE.")