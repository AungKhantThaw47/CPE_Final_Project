from google.cloud import firestore

PROJECT_ID = "cpe-final-project"
COLLECTION = "events"


def main() -> None:
    client = firestore.Client(project=PROJECT_ID)
    docs = list(client.collection(COLLECTION).limit(2000).stream())

    print(f"project={PROJECT_ID}")
    print(f"collection={COLLECTION}")
    print(f"doc_count_sampled={len(docs)}")

    rows = []
    for doc in docs:
        data = doc.to_dict() or {}
        rows.append(
            {
                "id": doc.id,
                "updated_at": str(data.get("updated_at", "")),
                "source_filename": str(data.get("source_filename", "")),
                "event_date": str(data.get("event_date", "")),
                "used_folder_hash": str(data.get("used_folder_hash", "")),
            }
        )

    rows.sort(key=lambda r: r["updated_at"], reverse=True)
    print("latest_docs=")
    for row in rows[:5]:
        print(
            "  "
            f"updated_at={row['updated_at']} "
            f"id={row['id']} "
            f"file={row['source_filename']} "
            f"date={row['event_date']} "
            f"used_folder_hash={row['used_folder_hash']}"
        )


if __name__ == "__main__":
    main()
