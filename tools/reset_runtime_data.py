"""Reset generated Sift runtime data.

This keeps source code, knowledge base files, deployment config, buckets, tables,
and Firestore databases intact. It deletes only app-created sessions, turns,
analytics events, uploads, and generated local runtime indexes.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]


def _project_id(explicit: str) -> str:
    return (
        explicit
        or os.environ.get("SIFT_GCP_PROJECT_ID")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GCP_PROJECT")
        or "sift-495116"
    ).strip()


def reset_local(data_dir: Path, *, dry_run: bool) -> None:
    targets = [
        data_dir / "sessions.db",
        data_dir / "session_uploads",
        data_dir / "exports",
        data_dir / "vc_firms",
    ]
    for target in targets:
        if not target.exists():
            continue
        print(f"{'Would delete' if dry_run else 'Deleting'} {target}")
        if dry_run:
            continue
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
    if not dry_run:
        (data_dir / "session_uploads").mkdir(parents=True, exist_ok=True)


def _firestore_collections(prefix: str) -> list[str]:
    return [f"{prefix}_sessions", f"{prefix}_analytics_events"]


def _delete_firestore_doc(doc_ref, *, dry_run: bool) -> int:
    deleted = 0
    for child_collection in doc_ref.collections():
        for child_doc in child_collection.list_documents():
            deleted += _delete_firestore_doc(child_doc, dry_run=dry_run)
    print(f"{'Would delete' if dry_run else 'Deleting'} Firestore document {doc_ref.path}")
    if not dry_run:
        doc_ref.delete()
    return deleted + 1


def reset_firestore(project: str, database: str, prefix: str, *, dry_run: bool) -> None:
    try:
        from google.cloud import firestore  # type: ignore
    except ImportError as exc:
        collections = ", ".join(_firestore_collections(prefix))
        if dry_run:
            print(f"Would delete Firestore collections in project {project}: {collections}")
            print("Install google-cloud-firestore to count/delete documents.")
            return
        raise RuntimeError("Install google-cloud-firestore before resetting Firestore data.") from exc

    client_kwargs = {"project": project}
    if database:
        client_kwargs["database"] = database
    client = firestore.Client(**client_kwargs)
    for collection_name in _firestore_collections(prefix):
        deleted = 0
        for doc_ref in client.collection(collection_name).list_documents():
            deleted += _delete_firestore_doc(doc_ref, dry_run=dry_run)
        print(f"{collection_name}: {'would delete' if dry_run else 'deleted'} {deleted} documents")


def reset_gcs(project: str, bucket_name: str, prefixes: Iterable[str], *, dry_run: bool) -> None:
    try:
        from google.cloud import storage  # type: ignore
    except ImportError as exc:
        prefix_list = ", ".join(prefixes)
        if dry_run:
            print(f"Would delete Cloud Storage objects in gs://{bucket_name}/ for prefixes: {prefix_list}")
            print("Install google-cloud-storage to count/delete objects.")
            return
        raise RuntimeError("Install google-cloud-storage before resetting Cloud Storage data.") from exc

    client = storage.Client(project=project)
    bucket = client.bucket(bucket_name)
    total = 0
    for prefix in prefixes:
        clean_prefix = prefix.strip().strip("/")
        if not clean_prefix:
            continue
        blobs = list(bucket.list_blobs(prefix=f"{clean_prefix}/"))
        total += len(blobs)
        for blob in blobs:
            print(f"{'Would delete' if dry_run else 'Deleting'} gs://{bucket_name}/{blob.name}")
            if not dry_run:
                blob.delete()
    print(f"Cloud Storage: {'would delete' if dry_run else 'deleted'} {total} objects")


def reset_bigquery(project: str, table: str, *, dry_run: bool) -> None:
    if "." not in table:
        table = f"{project}.sift_analytics.events"
    if dry_run:
        print(f"Would truncate BigQuery table {table}")
        return
    try:
        from google.cloud import bigquery  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Install google-cloud-bigquery before resetting BigQuery data.") from exc
    client = bigquery.Client(project=project)
    query = f"TRUNCATE TABLE `{table}`"
    client.query(query).result()
    print(f"Truncated BigQuery table {table}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset generated Sift runtime data.")
    parser.add_argument("--local", action="store_true", help="Reset local ./data runtime state.")
    parser.add_argument("--gcp", action="store_true", help="Reset Firestore, Cloud Storage uploads, and BigQuery analytics.")
    parser.add_argument("--project", default="", help="Google Cloud project id.")
    parser.add_argument("--firestore-database", default=os.environ.get("SIFT_FIRESTORE_DATABASE", ""))
    parser.add_argument("--collection-prefix", default=os.environ.get("SIFT_FIRESTORE_COLLECTION_PREFIX", "sift"))
    parser.add_argument("--bucket", default=os.environ.get("SIFT_UPLOAD_BUCKET", "sift-495116-sift-uploads"))
    parser.add_argument("--upload-prefix", default=os.environ.get("SIFT_UPLOAD_PREFIX", "session_uploads"))
    parser.add_argument("--bigquery-table", default=os.environ.get("SIFT_BIGQUERY_TABLE", "sift-495116.sift_analytics.events"))
    parser.add_argument("--data-dir", default=os.environ.get("SIFT_DATA_DIR", str(ROOT / "data")))
    parser.add_argument("--yes", action="store_true", help="Actually delete data. Without this, the command is a dry run.")
    args = parser.parse_args()

    dry_run = not args.yes
    if not args.local and not args.gcp:
        args.local = True

    if dry_run:
        print("Dry run only. Re-run with --yes to delete.")

    if args.local:
        reset_local(Path(args.data_dir), dry_run=dry_run)

    if args.gcp:
        project = _project_id(args.project)
        reset_firestore(project, args.firestore_database, args.collection_prefix, dry_run=dry_run)
        reset_gcs(project, args.bucket, [args.upload_prefix, "tmp", "deck_artifacts"], dry_run=dry_run)
        reset_bigquery(project, args.bigquery_table, dry_run=dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
