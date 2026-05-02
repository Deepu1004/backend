import base64
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    from firebase_admin import storage as firebase_storage
except ImportError:
    firebase_admin = None
    credentials = None
    firestore = None
    firebase_storage = None

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "submissions_db.json"
LOCK = threading.Lock()
FIRESTORE_COLLECTION = os.getenv("FIRESTORE_COLLECTION", "submissions")

_FIREBASE_APP = None
_FIRESTORE_CLIENT = None
_FIREBASE_MIGRATED = False
UPLOADS_DIR = BASE_DIR / "uploads"


def _get_service_account_info() -> Optional[Dict[str, Any]]:
    raw_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if raw_json:
        return json.loads(raw_json)

    raw_b64 = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON_B64")
    if raw_b64:
        decoded = base64.b64decode(raw_b64).decode("utf-8")
        return json.loads(decoded)

    credentials_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if credentials_path:
        with open(credentials_path, "r", encoding="utf-8") as file_handle:
            return json.load(file_handle)

    return None


def _firebase_enabled() -> bool:
    return firebase_admin is not None and _get_service_account_info() is not None


def _initialize_firestore_client():
    global _FIREBASE_APP, _FIRESTORE_CLIENT

    if _FIRESTORE_CLIENT is not None:
        return _FIRESTORE_CLIENT

    if not _firebase_enabled():
        return None

    if not firebase_admin._apps:
        service_account_info = _get_service_account_info()
        app_options: Dict[str, Any] = {}

        project_id = os.getenv("FIREBASE_PROJECT_ID")
        if project_id:
            app_options["projectId"] = project_id

        storage_bucket = os.getenv("FIREBASE_STORAGE_BUCKET")
        if storage_bucket:
            app_options["storageBucket"] = storage_bucket

        cred = credentials.Certificate(service_account_info)
        if app_options:
            _FIREBASE_APP = firebase_admin.initialize_app(cred, app_options)
        else:
            _FIREBASE_APP = firebase_admin.initialize_app(cred)
    else:
        _FIREBASE_APP = firebase_admin.get_app()

    _FIRESTORE_CLIENT = firestore.client()
    _migrate_local_json_to_firestore(_FIRESTORE_CLIENT)
    return _FIRESTORE_CLIENT


def _initialize_storage_bucket():
    if not _firebase_enabled() or firebase_storage is None:
        return None

    _initialize_firestore_client()
    return firebase_storage.bucket()


def _is_firestore_mode() -> bool:
    return _initialize_firestore_client() is not None


def _normalize_submission(submission_data: Dict[str, Any], submission_id: Optional[str] = None) -> Dict[str, Any]:
    normalized = dict(submission_data)
    normalized["id"] = submission_id or normalized.get("id") or f"sub_{datetime.now().timestamp()}"
    normalized["timestamp"] = normalized.get("timestamp") or datetime.now().isoformat()
    return normalized


def _submission_docs_to_dicts() -> List[Dict[str, Any]]:
    client = _initialize_firestore_client()
    if client is None:
        return []

    submissions: List[Dict[str, Any]] = []
    for document in client.collection(FIRESTORE_COLLECTION).stream():
        record = document.to_dict() or {}
        record["id"] = record.get("id") or document.id
        submissions.append(record)

    return submissions


def _migrate_local_json_to_firestore(client) -> None:
    global _FIREBASE_MIGRATED

    if _FIREBASE_MIGRATED:
        return

    existing_doc = next(client.collection(FIRESTORE_COLLECTION).limit(1).stream(), None)
    if existing_doc is not None:
        _FIREBASE_MIGRATED = True
        return

    if not DB_FILE.exists():
        _FIREBASE_MIGRATED = True
        return

    try:
        with DB_FILE.open("r", encoding="utf-8") as file_handle:
            local_db = json.load(file_handle)
    except Exception:
        _FIREBASE_MIGRATED = True
        return

    for submission in local_db.get("submissions", []):
        normalized = _normalize_submission(submission)
        client.collection(FIRESTORE_COLLECTION).document(normalized["id"]).set(normalized)

    _FIREBASE_MIGRATED = True


def upload_file_to_firebase_storage(local_file_path: str, storage_path: str) -> Optional[str]:
    """Upload a file to Firebase Storage and return a long-lived download URL."""
    bucket = _initialize_storage_bucket()
    if bucket is None:
        return None

    blob = bucket.blob(storage_path)
    blob.upload_from_filename(local_file_path)

    try:
        return blob.generate_signed_url(
            version="v4",
            expiration=datetime.now(timezone.utc) + timedelta(days=3650),
            method="GET",
        )
    except Exception:
        return None


def _delete_firestore_collection() -> None:
    client = _initialize_firestore_client()
    if client is None:
        return

    for document in client.collection(FIRESTORE_COLLECTION).stream():
        document.reference.delete()


def _delete_storage_object(storage_path: Optional[str]) -> None:
    if not storage_path:
        return

    bucket = _initialize_storage_bucket()
    if bucket is not None:
        blob = bucket.blob(storage_path)
        try:
            blob.delete()
        except Exception:
            pass

    local_file = UPLOADS_DIR / Path(storage_path).name
    if local_file.exists():
        try:
            local_file.unlink()
        except Exception:
            pass


def _resolve_storage_path(submission: Dict[str, Any]) -> Optional[str]:
    saved_file = submission.get("saved_file")
    if saved_file:
        return f"uploads/{saved_file}"

    file_url = submission.get("file_url", "")
    if "/uploads/" in file_url:
        return f"uploads/{file_url.rsplit('/uploads/', 1)[-1]}"

    return None


def delete_submission_files(submission: Dict[str, Any]) -> None:
    _delete_storage_object(_resolve_storage_path(submission))


def delete_submission(submission_id: str) -> Optional[Dict[str, Any]]:
    deleted_submission = get_submission_by_id(submission_id)
    if not deleted_submission:
        return None

    delete_submission_files(deleted_submission)

    if _is_firestore_mode():
        client = _initialize_firestore_client()
        if client is None:
            return None
        client.collection(FIRESTORE_COLLECTION).document(submission_id).delete()
        return deleted_submission

    with LOCK:
        if not DB_FILE.exists():
            return None

        with DB_FILE.open("r", encoding="utf-8") as file_handle:
            data = json.load(file_handle)

        submissions = data.get("submissions", [])
        remaining_submissions = [
            submission for submission in submissions
            if submission.get("id") != submission_id
        ]

        if len(remaining_submissions) == len(submissions):
            return None

        data["submissions"] = remaining_submissions
        with DB_FILE.open("w", encoding="utf-8") as file_handle:
            json.dump(data, file_handle, indent=2)

    return deleted_submission


def init_db():
    """Initialize database file if it doesn't exist"""
    if _is_firestore_mode():
        return

    if not DB_FILE.exists():
        with DB_FILE.open("w") as f:
            json.dump({"submissions": [], "accounts": {}}, f, indent=2)


def load_db() -> Dict[str, Any]:
    """Load database from JSON file"""
    if _is_firestore_mode():
        return {"submissions": _submission_docs_to_dicts(), "accounts": {}}

    with LOCK:
        if not DB_FILE.exists():
            init_db()
        with DB_FILE.open("r") as f:
            return json.load(f)


def save_db(data: Dict[str, Any]):
    """Save database to JSON file"""
    if _is_firestore_mode():
        client = _initialize_firestore_client()
        if client is None:
            return

        _delete_firestore_collection()
        for submission in data.get("submissions", []):
            normalized = _normalize_submission(submission)
            client.collection(FIRESTORE_COLLECTION).document(normalized["id"]).set(normalized)
        return

    with LOCK:
        with DB_FILE.open("w") as f:
            json.dump(data, f, indent=2)


def add_submission(submission_data: Dict[str, Any]) -> str:
    """Add a new submission to database"""
    normalized = _normalize_submission(submission_data)
    submission_id = normalized["id"]

    if _is_firestore_mode():
        client = _initialize_firestore_client()
        if client is not None:
            client.collection(FIRESTORE_COLLECTION).document(submission_id).set(normalized)
            return submission_id

    db = load_db()
    db.setdefault("submissions", []).append(normalized)
    save_db(db)

    return submission_id


def update_submission(submission_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update a submission and return the updated record."""
    if _is_firestore_mode():
        client = _initialize_firestore_client()
        if client is None:
            return None

        document_ref = client.collection(FIRESTORE_COLLECTION).document(submission_id)
        snapshot = document_ref.get()
        if not snapshot.exists:
            return None

        document_ref.update(updates)
        updated_submission = snapshot.to_dict() or {}
        updated_submission.update(updates)
        updated_submission["id"] = updated_submission.get("id") or submission_id
        return updated_submission

    db = load_db()

    for index, submission in enumerate(db.get("submissions", [])):
        if submission.get("id") == submission_id:
            db["submissions"][index] = {**submission, **updates}
            save_db(db)
            return db["submissions"][index]

    return None


def get_all_submissions() -> List[Dict[str, Any]]:
    """Get all submissions from database"""
    if _is_firestore_mode():
        return _submission_docs_to_dicts()

    db = load_db()
    return db.get("submissions", [])


def get_submission_by_id(submission_id: str) -> Dict[str, Any]:
    """Get a specific submission"""
    if _is_firestore_mode():
        client = _initialize_firestore_client()
        if client is None:
            return None

        snapshot = client.collection(FIRESTORE_COLLECTION).document(submission_id).get()
        if not snapshot.exists:
            return None

        submission = snapshot.to_dict() or {}
        submission["id"] = submission.get("id") or submission_id
        return submission

    db = load_db()
    for sub in db.get("submissions", []):
        if sub.get("id") == submission_id:
            return sub
    return None


def get_submissions_by_fingerprint(fingerprint: str) -> List[Dict[str, Any]]:
    """Get all submissions with the same fingerprint"""
    if _is_firestore_mode():
        return [
            sub for sub in get_all_submissions()
            if sub.get("fingerprint") == fingerprint
        ]

    db = load_db()
    return [
        sub for sub in db.get("submissions", [])
        if sub.get("fingerprint") == fingerprint
    ]


def get_submissions_by_content_hash(content_hash: str) -> List[Dict[str, Any]]:
    """Get all submissions with the same uploaded file hash"""
    if _is_firestore_mode():
        return [
            sub for sub in get_all_submissions()
            if sub.get("metadata", {}).get("content_hash") == content_hash
        ]

    db = load_db()
    return [
        sub for sub in db.get("submissions", [])
        if sub.get("metadata", {}).get("content_hash") == content_hash
    ]


def get_submissions_by_email(email: str) -> List[Dict[str, Any]]:
    """Get all submissions from a specific email"""
    if _is_firestore_mode():
        return [
            sub for sub in get_all_submissions()
            if sub.get("email") == email
        ]

    db = load_db()
    return [
        sub for sub in db.get("submissions", [])
        if sub.get("email") == email
    ]


def get_recent_submissions(minutes: int = 10) -> List[Dict[str, Any]]:
    """Get submissions from the last N minutes"""
    from datetime import datetime, timedelta
    
    if _is_firestore_mode():
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        recent = []
        for sub in get_all_submissions():
            try:
                sub_time = datetime.fromisoformat(sub.get("timestamp", ""))
                if sub_time > cutoff_time:
                    recent.append(sub)
            except Exception:
                pass
        return recent

    db = load_db()
    cutoff_time = datetime.now() - timedelta(minutes=minutes)
    
    recent = []
    for sub in db.get("submissions", []):
        try:
            sub_time = datetime.fromisoformat(sub.get("timestamp", ""))
            if sub_time > cutoff_time:
                recent.append(sub)
        except Exception:
            pass
    
    return recent


def link_accounts(fingerprint: str, emails: List[str]) -> Dict[str, Any]:
    """Get all accounts linked by a fingerprint"""
    if _is_firestore_mode():
        linked = list(dict.fromkeys(emails or []))

        for sub in get_submissions_by_fingerprint(fingerprint):
            email = sub.get("email")
            if email not in linked:
                linked.append(email)

        return {
            "fingerprint": fingerprint,
            "linked_accounts": linked,
            "account_count": len(linked)
        }

    db = load_db()
    linked = list(dict.fromkeys(emails or []))
    
    for sub in db.get("submissions", []):
        if sub.get("fingerprint") == fingerprint:
            email = sub.get("email")
            if email not in linked:
                linked.append(email)
    
    return {
        "fingerprint": fingerprint,
        "linked_accounts": linked,
        "account_count": len(linked)
    }


def get_author_metadata_matches(author: str, creator: str) -> List[Dict[str, Any]]:
    """Find all submissions with matching author metadata"""
    if _is_firestore_mode():
        matches = []
        for sub in get_all_submissions():
            metadata = sub.get("metadata", {})
            if (metadata.get("author") == author or 
                metadata.get("creator") == creator):
                matches.append(sub)
        return matches

    db = load_db()
    matches = []
    
    for sub in db.get("submissions", []):
        metadata = sub.get("metadata", {})
        if (metadata.get("author") == author or 
            metadata.get("creator") == creator):
            matches.append(sub)
    
    return matches


def clear_db():
    """Clear all data (for testing)"""
    if _is_firestore_mode():
        _delete_firestore_collection()
        return

    with LOCK:
        if DB_FILE.exists():
            DB_FILE.unlink()
        init_db()


def get_stats() -> Dict[str, Any]:
    """Get dashboard statistics"""
    if _is_firestore_mode():
        submissions = get_all_submissions()
        total = len(submissions)
        high_risk = 0
        critical_risk = 0
        total_score = 0

        for sub in submissions:
            score = sub.get("risk_score", 0)
            total_score += score
            if score >= 80:
                critical_risk += 1
            elif score >= 60:
                high_risk += 1

        avg_score = round(total_score / total, 1) if total > 0 else 0

        return {
            "total_submissions": total,
            "high_risk_submissions": high_risk,
            "critical_risk_submissions": critical_risk,
            "average_risk_score": avg_score
        }

    db = load_db()
    submissions = db.get("submissions", [])
    
    total = len(submissions)
    high_risk = 0
    critical_risk = 0
    total_score = 0
    
    for sub in submissions:
        score = sub.get("risk_score", 0)
        total_score += score
        if score >= 80:
            critical_risk += 1
        elif score >= 60:
            high_risk += 1
            
    avg_score = round(total_score / total, 1) if total > 0 else 0
    
    return {
        "total_submissions": total,
        "high_risk_submissions": high_risk,
        "critical_risk_submissions": critical_risk,
        "average_risk_score": avg_score
    }
