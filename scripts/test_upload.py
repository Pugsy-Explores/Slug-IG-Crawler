#!/usr/bin/env python3

import os
from google.cloud import storage
from google.api_core.exceptions import GoogleAPIError

# Configurable via environment variables
BUCKET_NAME = os.getenv("BUCKET_NAME", "pugsy_ai_crawled_data")
LOCAL_FILE  = os.getenv("LOCAL_FILE", "/Users/shang/my_work/pugsy_ai/tests_ai/data/audit_comment_dataset.jsonl")
REMOTE_BLOB = os.getenv("REMOTE_BLOB", "uploads/audit_comment_dataset.jsonl")

def upload():
    try:
        client = storage.Client()  # uses your local gcloud credentials
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(REMOTE_BLOB)

        print(f"Uploading {LOCAL_FILE} → gs://{BUCKET_NAME}/{REMOTE_BLOB}")
        blob.upload_from_filename(LOCAL_FILE)

        print("Upload successful.")
    except GoogleAPIError as e:
        print(f"GCS error: {e}")
    except FileNotFoundError:
        print(f"Local file not found: {LOCAL_FILE}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    upload()
