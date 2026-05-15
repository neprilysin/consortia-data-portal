import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL:
    raise RuntimeError("Missing SUPABASE_URL environment variable")

if not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_SERVICE_ROLE_KEY environment variable")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def upload_file_to_bucket(
    bucket_name: str,
    local_path: Path,
    storage_path: str,
):
    with open(local_path, "rb") as f:
        supabase.storage.from_(bucket_name).upload(
            path=storage_path,
            file=f,
            file_options={"upsert": "true"},
        )

    return storage_path


def save_consortia_record(
    user_name,
    lab,
    project,
    molecule,
    experiment,
    phase,
    file_url=None,
    status="Uploaded",
    certificate_url=None,
    dataset_hash=None,
):
    record = {
        "user_name": user_name,
        "lab": lab,
        "project": project,
        "molecule": molecule,
        "experiment": experiment,
        "phase": phase,
        "file_url": file_url,
        "status": status,
        "certificate_url": certificate_url,
        "dataset_hash": dataset_hash,
    }

    response = (
        supabase
        .table("consortia_records")
        .insert(record)
        .execute()
    )

    return response.data
