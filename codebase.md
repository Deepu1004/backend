# Backend Codebase — Complete Source Code

**Project:** TNF Vibe Coding Challenge — Scholar Risk Detector  
**Backend:** Python + FastAPI + Optional Firebase/Firestore  
**Purpose:** Fraud detection, metadata extraction, risk scoring, and manuscript submission management

---

## Table of Contents

1. [main.py](#mainpy) — FastAPI application and HTTP endpoints
2. [database.py](#databasepy) — JSON/Firestore database layer
3. [metadata_extractor.py](#metadata_extractorpy) — PDF/DOCX metadata extraction
4. [risk_scoring.py](#risk_scoringpy) — Multi-layer fraud detection scoring
5. [users.py](#userspy) — Simple editor authentication
6. [requirements.txt](#requirementstxt) — Python dependencies
7. [runtime.txt](#runtimetxt) — Python version specification

---

## main.py

FastAPI REST API for manuscript upload, analysis, and editorial review.

```python
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import shutil
import time
import os
from datetime import datetime
from typing import Annotated
from dotenv import load_dotenv

from metadata_extractor import extract_file_metadata
from risk_scoring import RiskScorer
from users import build_editor_session, is_editor_credentials
from database import (
    add_submission,
    delete_submission,
    get_all_submissions,
    get_submission_by_id,
    upload_file_to_firebase_storage,
    update_submission,
    get_stats
)

load_dotenv()

app = FastAPI(title="AuthorPrint API")

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Configure CORS with frontend URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000", "http://localhost:8000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure upload directory exists
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Mount static files for serving uploaded PDFs
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

risk_scorer = RiskScorer()


@app.get("/", responses={200: {"description": "Service is running"}})
async def root():
    return {
        "message": "AuthorPrint API is running",
        "health": "/api/health",
        "docs": "/docs",
    }

@app.get("/api/health", responses={200: {"description": "Health check response"}})
async def health_check():
    return {"status": "ok", "timestamp": time.time()}


@app.post(
    "/api/auth/editor",
    responses={
        200: {"description": "Editor authenticated successfully"},
        401: {"description": "Invalid editor credentials"},
    },
)
async def auth_editor(request: Request):
    content_type = request.headers.get("content-type", "")
    email = ""
    password = ""

    if "application/json" in content_type:
        payload = await request.json()
        email = str(payload.get("email", ""))
        password = str(payload.get("password", ""))
    else:
        form = await request.form()
        email = str(form.get("email", ""))
        password = str(form.get("password", ""))

    if not is_editor_credentials(email, password):
        raise HTTPException(status_code=401, detail="Invalid editor credentials")

    return {
        "success": True,
        "message": "Editor authenticated successfully",
        "user": build_editor_session(),
    }

@app.post("/api/upload", responses={500: {"description": "Upload or analysis failed"}})
async def upload_submission(
    file: Annotated[UploadFile, File(...)],
    fingerprint: Annotated[str, Form(...)],
    email: Annotated[str, Form(...)],
    journal: Annotated[str, Form()] = "Unknown Journal",
    author_name: Annotated[str, Form()] = "Anonymous",
    document_type: Annotated[str, Form()] = "Paper",
    document_kind: Annotated[str, Form()] = "Science",
):
    """
    Upload a paper and perform fraud detection
    """
    try:
        # Save uploaded file
        timestamp = int(time.time() * 1000)
        saved_filename = f"{timestamp}_{file.filename}"
        file_path = UPLOAD_DIR / saved_filename
        
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Extract metadata
        metadata = extract_file_metadata(str(file_path))
        metadata["document_type"] = document_type
        metadata["document_kind"] = document_kind

        firebase_file_url = upload_file_to_firebase_storage(
            str(file_path),
            f"uploads/{saved_filename}",
        )
        file_url = firebase_file_url or f"{BACKEND_URL}/uploads/{saved_filename}"
        
        # Calculate risk score
        risk_result = risk_scorer.calculate_risk_score(
            fingerprint=fingerprint,
            email=email,
            metadata=metadata,
            file_name=file.filename
        )
        
        # Prepare submission data
        submission_data = {
            "email": email,
            "fingerprint": fingerprint,
            "journal": journal,
            "author_name": author_name,
            "file_name": file.filename,
            "saved_file": saved_filename,
            "file_url": file_url,
            "file_size": file.size,
            "metadata": metadata,
            "risk_score": risk_result["risk_score"],
            "risk_level": risk_result["risk_level"],
            "signals": risk_result["signals"],
            "risk_factors": risk_result["risk_factors"],
            "linked_accounts": risk_result["linked_accounts"],
            "workflow_status": "pending",
            "analysis_status": "queued",
            "review_status": "pending",
            "review_decision": None,
            "reviewer_name": None,
            "reviewed_at": None,
            "scan_started_at": None,
            "scan_completed_at": None,
        }
        
        # Check for similar document
        all_subs = get_all_submissions()
        similar_doc = None
        if document_type and document_kind:
            for sub in all_subs:
                sub_meta = sub.get("metadata", {})
                if sub_meta.get("document_type") == document_type and sub_meta.get("document_kind") == document_kind:
                    similar_doc = {
                        "file_name": sub.get("file_name"),
                        "type": document_type,
                        "kind": document_kind,
                        "content_preview": sub_meta.get("content_sample", "Content preview not available.")
                    }
                    break
                    
        # Add to database
        submission_id = add_submission(submission_data)
        
        return {
            "success": True,
            "submission_id": submission_id,
            "risk_score": risk_result["risk_score"],
            "risk_level": risk_result["risk_level"],
            "similar_document": similar_doc
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/submissions", responses={500: {"description": "Failed to list submissions"}})
async def list_submissions():
    """Get all submissions for the editor dashboard"""
    try:
        submissions = get_all_submissions()
        
        # Format for frontend
        formatted_subs = []
        for sub in submissions:
            formatted_subs.append({
                "id": sub.get("id"),
                "fingerprint": sub.get("fingerprint"),
                "title": sub.get("file_name"),
                "author_name": sub.get("author_name"),
                "email": sub.get("email"),
                "journal": sub.get("journal"),
                "timestamp": sub.get("timestamp"),
                "score": sub.get("risk_score", 0),
                "workflow_status": sub.get("workflow_status", "pending"),
                "account_count": len(sub.get("linked_accounts", [])),
                "signals": sub.get("signals", []),
                "file_url": sub.get("file_url"),
                "file_name": sub.get("file_name")
            })
            
        # Sort by timestamp (newest first)
        formatted_subs.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return {"submissions": formatted_subs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get(
    "/api/submissions/{submission_id}",
    responses={
        400: {"description": "Invalid request"},
        404: {"description": "Submission not found"},
    },
)
async def get_submission_details(submission_id: str):
    """Get full details for a specific submission"""
    try:
        submission = get_submission_by_id(submission_id)
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")
            
        return {
            "submission": {
                "id": submission.get("id"),
                "fingerprint": submission.get("fingerprint"),
                "title": submission.get("file_name"),
                "author_name": submission.get("author_name"),
                "email": submission.get("email"),
                "journal": submission.get("journal"),
                "timestamp": submission.get("timestamp"),
                "score": submission.get("risk_score", 0),
                "workflow_status": submission.get("workflow_status", "pending"),
                "file_url": submission.get("file_url"),
                "metadata": submission.get("metadata", {}),
                "risk_level": submission.get("risk_level", "low"),
                "signals": submission.get("signals", []),
                "risk_factors": submission.get("risk_factors", {}),
                "linked_accounts": submission.get("linked_accounts", []),
                "account_count": len(submission.get("linked_accounts", [])),
                "recommendation": submission.get("recommendation"),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post(
    "/api/submissions/{submission_id}/decision",
    responses={
        400: {"description": "Decision must be accept or reject"},
        404: {"description": "Submission not found"},
        500: {"description": "Failed to update review decision"},
    },
)
async def update_review_decision(
    submission_id: str,
    decision: Annotated[str, Form(...)],
    reviewer_name: Annotated[str, Form()] = "Editor",
):
    """Accept or reject a submission after scanning."""
    try:
        submission = get_submission_by_id(submission_id)
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")

        normalized_decision = decision.lower().strip()
        if normalized_decision not in {"accept", "reject"}:
            raise HTTPException(status_code=400, detail="Decision must be accept or reject")

        review_status = "accepted" if normalized_decision == "accept" else "rejected"
        update_submission(
            submission_id,
            {
                "workflow_status": review_status,
                "review_status": review_status,
                "review_decision": normalized_decision,
                "reviewer_name": reviewer_name,
                "reviewed_at": time.time(),
            },
        )

        return {
            "success": True,
            "submission_id": submission_id,
            "workflow_status": review_status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/submissions/{submission_id}", responses={500: {"description": "Delete failed"}})
async def delete_submission_endpoint(submission_id: str):
    """Delete a submission and its associated files"""
    try:
        deleted = delete_submission(submission_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Submission not found")
        return {"success": True, "deleted_id": submission_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats", responses={500: {"description": "Failed to fetch stats"}})
async def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        return get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## database.py

Database abstraction layer supporting JSON file storage and Firebase Firestore.

```python
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
```

---

## metadata_extractor.py

Extract and analyze metadata from PDF, DOCX, and TXT files.

```python
import hashlib
import os
from typing import Dict, Any, Optional
import mimetypes

try:
    import fitz  # PyMuPDF for PDFs
except ImportError:
    fitz = None

try:
    from docx import Document  # python-docx for Word files
except ImportError:
    Document = None


def _hash_file(file_path: str) -> str:
    """Generate a stable SHA-256 hash for the full file content."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def extract_pdf_metadata(file_path: str) -> Dict[str, Any]:
    """Extract metadata from PDF file"""
    if not fitz:
        return {"error": "PyMuPDF not installed"}
    
    try:
        doc = fitz.open(file_path)
        metadata = doc.metadata or {}
        
        # Extract standard PDF metadata
        result = {
            "author": metadata.get("author", ""),
            "title": metadata.get("title", ""),
            "subject": metadata.get("subject", ""),
            "creator": metadata.get("creator", ""),
            "producer": metadata.get("producer", ""),
            "creation_date": str(metadata.get("creationDate", "")),
            "mod_date": str(metadata.get("modDate", "")),
            "pages": len(doc),
            "file_size": os.path.getsize(file_path),
            "content_hash": _hash_file(file_path),
        }
        
        # Extract text from first 2 pages for style analysis
        text_sample = ""
        for page_num in range(min(2, len(doc))):
            text_sample += doc[page_num].get_text() + "\n"
        
        result["text_sample"] = text_sample[:2000]  # First 2000 chars
        result["total_words"] = len(text_sample.split())
        
        # Add classification
        classification = classify_document(text_sample)
        result.update(classification)
        
        doc.close()
        return result
    except Exception as e:
        return {"error": f"Failed to extract PDF metadata: {str(e)}"}


def extract_docx_metadata(file_path: str) -> Dict[str, Any]:
    """Extract metadata from DOCX file"""
    if not Document:
        return {"error": "python-docx not installed"}
    
    try:
        doc = Document(file_path)
        props = doc.core_properties
        
        result = {
            "author": props.author or "",
            "title": props.title or "",
            "subject": props.subject or "",
            "creator": "Microsoft Word",
            "created": str(props.created) if props.created else "",
            "modified": str(props.modified) if props.modified else "",
            "file_size": os.path.getsize(file_path),
            "paragraphs": len(doc.paragraphs),
            "tables": len(doc.tables),
            "content_hash": _hash_file(file_path),
        }
        
        # Extract text sample
        text_sample = ""
        for para in doc.paragraphs[:20]:  # First 20 paragraphs
            text_sample += para.text + "\n"
        
        result["text_sample"] = text_sample[:2000]
        result["total_words"] = len(text_sample.split())
        
        # Add classification
        classification = classify_document(text_sample)
        result.update(classification)
        
        return result
    except Exception as e:
        return {"error": f"Failed to extract DOCX metadata: {str(e)}"}


def extract_txt_metadata(file_path: str) -> Dict[str, Any]:
    """Extract metadata from TXT file"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        result = {
            "author": "",
            "file_size": os.path.getsize(file_path),
            "text_sample": content[:2000],
            "total_words": len(content.split()),
            "total_lines": len(content.split('\n')),
            "content_hash": _hash_file(file_path),
        }
        
        # Add classification
        classification = classify_document(content[:2000])
        result.update(classification)
        
        return result
    except Exception as e:
        return {"error": f"Failed to extract TXT metadata: {str(e)}"}


def extract_file_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract metadata from uploaded file based on file type
    """
    if not os.path.exists(file_path):
        return {"error": "File not found"}
    
    # Get file extension
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    
    # Route to appropriate extractor
    if ext == ".pdf":
        return extract_pdf_metadata(file_path)
    elif ext == ".docx":
        return extract_docx_metadata(file_path)
    elif ext == ".txt":
        return extract_txt_metadata(file_path)
    else:
        return {
            "error": f"Unsupported file type: {ext}",
            "file_size": os.path.getsize(file_path),
            "file_type": ext,
            "content_hash": _hash_file(file_path),
        }

def classify_document(text: str) -> Dict[str, str]:
    text_lower = text.lower()
    
    doc_type = "paper"
    if "chapter" in text_lower or "book" in text_lower:
        doc_type = "book"
    elif "journal" in text_lower or "volume" in text_lower or "issue" in text_lower:
        doc_type = "journal"
        
    doc_kind = "science"
    if any(k in text_lower for k in ["engineering", "architecture", "design", "mechanic"]):
        doc_kind = "engineering"
    elif any(k in text_lower for k in ["medical", "health", "clinical", "patient", "disease"]):
        doc_kind = "medical"
        
    return {
        "document_type": doc_type,
        "document_kind": doc_kind
    }



def analyze_document_similarity(
    metadata1: Dict[str, Any],
    metadata2: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Analyze similarity between two documents
    """
    similarity_score = 0
    matching_fields = []
    
    # Author match
    if (metadata1.get("author") and metadata2.get("author") and
        metadata1.get("author") == metadata2.get("author")):
        similarity_score += 25
        matching_fields.append("author")
    
    # Creator/Software match
    if (metadata1.get("creator") and metadata2.get("creator") and
        metadata1.get("creator") == metadata2.get("creator")):
        similarity_score += 15
        matching_fields.append("creator")
    
    # Title similarity
    if (metadata1.get("title") and metadata2.get("title") and
        metadata1.get("title").lower() == metadata2.get("title").lower()):
        similarity_score += 20
        matching_fields.append("title")
    
    # Text similarity (basic word overlap)
    text1 = metadata1.get("text_sample", "").lower()
    text2 = metadata2.get("text_sample", "").lower()
    
    if text1 and text2:
        words1 = set(text1.split())
        words2 = set(text2.split())
        if len(words1) > 0 and len(words2) > 0:
            overlap = len(words1 & words2) / len(words1 | words2)
            text_similarity = int(overlap * 100)
            similarity_score += text_similarity // 4  # Weight it less
            if overlap > 0.3:
                matching_fields.append("text_content")
    
    return {
        "similarity_score": min(similarity_score, 100),
        "matching_fields": matching_fields
    }
```

---

## risk_scoring.py

Multi-layer fraud detection and risk scoring algorithm (5 layers).

```python
from typing import Dict, List, Any
from datetime import datetime, timedelta
import time
import database


class RiskScorer:
    """Calculate fraud risk score based on multiple signals"""
    
    def __init__(self):
        self.max_score = 100
        self.risk_levels = {
            "low": (0, 30),
            "medium": (30, 60),
            "high": (60, 85),
            "critical": (85, 101)
        }
    
    def calculate_risk_score(
        self,
        fingerprint: str,
        email: str,
        metadata: Dict[str, Any],
        file_name: str
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive risk score based on 5 layers
        """
        score = 0
        signals = []
        risk_factors = {}
        
        # Layer 1: Device Fingerprint Analysis
        fp_score, fp_signals, fp_factors = self._analyze_fingerprint(fingerprint)
        score += fp_score
        signals.extend(fp_signals)
        risk_factors.update({f"fingerprint_{k}": v for k, v in fp_factors.items()})
        
        # Layer 2: Document Metadata Forensics
        meta_score, meta_signals, meta_factors = self._analyze_metadata(metadata, fingerprint)
        score += meta_score
        signals.extend(meta_signals)
        risk_factors.update({f"metadata_{k}": v for k, v in meta_factors.items()})
        
        # Layer 3: Behavioral Patterns
        behav_score, behav_signals, behav_factors = self._analyze_behavior(
            fingerprint, email, file_name
        )
        score += behav_score
        signals.extend(behav_signals)
        risk_factors.update({f"behavior_{k}": v for k, v in behav_factors.items()})
        
        # Layer 4: Writing Style (if text available)
        style_score, style_signals, style_factors = self._analyze_writing_style(metadata)
        score += style_score
        signals.extend(style_signals)
        risk_factors.update({f"style_{k}": v for k, v in style_factors.items()})
        
        # Layer 5: Content Similarity
        content_score, content_signals, content_factors = self._analyze_content(
            metadata, fingerprint
        )
        score += content_score
        signals.extend(content_signals)
        risk_factors.update({f"content_{k}": v for k, v in content_factors.items()})
        
        # Cap the score at 100
        final_score = min(int(score), 100)
        
        # Determine risk level
        risk_level = self._get_risk_level(final_score)
        
        # Get linked accounts
        linked_info = database.link_accounts(fingerprint, [email])
        
        return {
            "risk_score": final_score,
            "risk_level": risk_level,
            "signals": signals,
            "risk_factors": risk_factors,
            "linked_accounts": linked_info.get("linked_accounts", []),
            "account_count": linked_info.get("account_count", 1),
            "recommendation": self._get_recommendation(final_score, signals)
        }
    
    def _analyze_fingerprint(self, fingerprint: str) -> tuple:
        """Layer 1: Device Fingerprint Analysis"""
        score = 0
        signals = []
        factors = {}
        
        # Check if this fingerprint has been seen before
        matching_subs = database.get_submissions_by_fingerprint(fingerprint)
        
        if len(matching_subs) == 0:
            signals.append("✓ New device fingerprint")
            factors["first_submission"] = True
            score += 0
        elif len(matching_subs) == 1:
            signals.append("• Device seen before (1 prior account)")
            factors["prior_accounts"] = 1
            score += 5
        elif len(matching_subs) <= 3:
            signals.append(f"⚠ Device fingerprint matches {len(matching_subs)} prior accounts")
            factors["prior_accounts"] = len(matching_subs)
            score += 30
        else:
            signals.append(f"🔴 Device fingerprint matches {len(matching_subs)} prior accounts")
            factors["prior_accounts"] = len(matching_subs)
            score += 40
        
        factors["fingerprint_matches"] = len(matching_subs)
        
        return score, signals, factors
    
    def _analyze_metadata(self, metadata: Dict[str, Any], fingerprint: str) -> tuple:
        """Layer 2: Document Metadata Forensics"""
        score = 0
        signals = []
        factors = {}
        
        if metadata.get("error"):
            return 0, [], {}
        
        author = metadata.get("author", "")
        creator = metadata.get("creator", "")
        
        # Check for author/creator metadata
        if author:
            similar_docs = database.get_author_metadata_matches(author, creator)
            if len(similar_docs) > 1:
                score += 20
                signals.append(f"⚠ Document author '{author}' found in {len(similar_docs)} submissions")
                factors["author_matches"] = len(similar_docs)
        
        # Check for creator/software match
        if creator:
            creator_matches = [
                s for s in database.get_submissions_by_fingerprint(fingerprint)
                if s.get("metadata", {}).get("creator") == creator
            ]
            if len(creator_matches) > 1:
                score += 15
                signals.append(f"• Same document editor: {creator}")
                factors["creator_matches"] = len(creator_matches)
        
        # Check file size consistency (might indicate templates)
        file_size = metadata.get("file_size", 0)
        if file_size > 0:
            similar_sizes = [
                s for s in database.get_submissions_by_fingerprint(fingerprint)
                if abs(s.get("metadata", {}).get("file_size", 0) - file_size) < file_size * 0.1
            ]
            if len(similar_sizes) > 2:
                score += 10
                signals.append("• Similar file sizes (possible template reuse)")
                factors["size_pattern"] = len(similar_sizes)
        
        # Check for suspiciously old creation dates
        creation_date = metadata.get("creation_date", "")
        if creation_date and ("1970" in creation_date or "1980" in creation_date):
            score += 5
            signals.append("• Suspicious creation date (possible metadata manipulation)")
            factors["date_manipulation"] = True
        
        factors["metadata_score"] = score
        return score, signals, factors
    
    def _analyze_behavior(
        self, fingerprint: str, email: str, file_name: str
    ) -> tuple:
        """Layer 3: Behavioral Patterns"""
        score = 0
        signals = []
        factors = {}
        
        # Check upload velocity
        recent_subs = database.get_recent_submissions(minutes=10)
        fingerprint_velocity = len(
            [s for s in recent_subs if s.get("fingerprint") == fingerprint]
        )
        
        if fingerprint_velocity >= 5:
            score += 35
            signals.append(f"🔴 BULK UPLOAD: {fingerprint_velocity} files in 10 minutes")
            factors["bulk_upload"] = fingerprint_velocity
        elif fingerprint_velocity >= 3:
            score += 25
            signals.append(f"⚠ Multiple uploads: {fingerprint_velocity} files in 10 minutes")
            factors["rapid_upload"] = fingerprint_velocity
        elif fingerprint_velocity >= 2:
            score += 10
            signals.append(f"• {fingerprint_velocity} uploads in short timeframe")
            factors["multiple_uploads"] = fingerprint_velocity

        email_submissions = database.get_submissions_by_email(email)
        if len(email_submissions) > 1:
            score += 5
            signals.append(f"• Email seen in {len(email_submissions)} submissions")
            factors["email_reuse"] = len(email_submissions)
        
        # Check file naming patterns
        similar_names = [
            s for s in database.get_submissions_by_fingerprint(fingerprint)
            if self._check_file_name_pattern(s.get("file_name", ""), file_name)
        ]
        if len(similar_names) > 1:
            score += 15
            signals.append(f"⚠ File naming pattern detected ({len(similar_names)} similar names)")
            factors["naming_pattern"] = len(similar_names)
        
        # Check submission timing patterns (e.g., always at night)
        all_by_fp = database.get_submissions_by_fingerprint(fingerprint)
        if len(all_by_fp) >= 2:
            hours = []
            for sub in all_by_fp:
                try:
                    dt = datetime.fromisoformat(sub.get("timestamp", ""))
                    hours.append(dt.hour)
                except Exception:
                    pass
            
            # Check for unusual timing (e.g., all between 2-4 AM)
            if hours and all(h >= 2 and h <= 4 for h in hours) and len(hours) >= 2:
                score += 20
                signals.append("• Suspicious timing pattern (automated submissions?)")
                factors["timing_pattern"] = True
        
        factors["velocity"] = fingerprint_velocity
        return score, signals, factors
    
    def _analyze_writing_style(self, metadata: Dict[str, Any]) -> tuple:
        """Layer 4: Writing Style Fingerprint"""
        score = 0
        signals = []
        factors = {}
        
        text_sample = metadata.get("text_sample", "")
        if not text_sample or len(text_sample) < 100:
            return 0, [], {}
        
        # Basic style analysis
        words = text_sample.split()
        sentences = text_sample.split('.')
        
        if len(sentences) > 0 and len(words) > 0:
            avg_sentence_length = len(words) / len(sentences)
            
            # Unusual sentence length patterns
            if avg_sentence_length < 5 or avg_sentence_length > 50:
                score += 5
                signals.append(f"• Unusual sentence structure (avg: {avg_sentence_length:.1f} words)")
                factors["unusual_style"] = True
        
        # Check for vocabulary richness
        unique_words = len({w.lower() for w in words if len(w) > 3})
        vocabulary_ratio = unique_words / len(words) if len(words) > 0 else 0
        
        if vocabulary_ratio < 0.3:  # Low vocabulary diversity
            score += 5
            signals.append("• Low vocabulary diversity (possible AI-generated?)")
            factors["low_vocabulary"] = vocabulary_ratio
        
        factors["writing_style_score"] = score
        return score, signals, factors
    
    def _analyze_content(self, metadata: Dict[str, Any], fingerprint: str) -> tuple:
        """Layer 5: Content Similarity"""
        score = 0
        signals = []
        factors = {}

        exact_score, exact_signals, exact_factors = self._score_exact_duplicates(metadata)
        score += exact_score
        signals.extend(exact_signals)
        factors.update(exact_factors)

        text_sample = metadata.get("text_sample", "")
        if text_sample:
            similarity_score, similarity_signals, similarity_factors = self._score_text_similarity(
                text_sample,
                fingerprint,
            )
            score += similarity_score
            signals.extend(similarity_signals)
            factors.update(similarity_factors)

            ai_score, ai_signals, ai_factors = self._score_ai_markers(text_sample)
            score += ai_score
            signals.extend(ai_signals)
            factors.update(ai_factors)

        factors["content_score"] = score
        return score, signals, factors

    def _score_exact_duplicates(self, metadata: Dict[str, Any]) -> tuple:
        """Score exact file duplicates across the entire corpus."""
        content_hash = metadata.get("content_hash", "")
        text_sample = metadata.get("text_sample", "")

        exact_duplicates = []
        if content_hash:
            exact_duplicates = database.get_submissions_by_content_hash(content_hash)

        if not exact_duplicates and text_sample:
            exact_duplicates = [
                sub
                for sub in database.get_all_submissions()
                if sub.get("metadata", {}).get("text_sample", "") == text_sample
            ]

        if not exact_duplicates:
            return 0, [], {}

        score = 35
        signals = [
            f"🔴 Exact file duplicate detected in {len(exact_duplicates)} prior submission(s)"
        ]
        factors = {"exact_file_duplicates": len(exact_duplicates)}
        return score, signals, factors

    def _score_text_similarity(self, text_sample: str, fingerprint: str) -> tuple:
        """Score similarity between the current text and prior submissions."""
        score = 0
        signals = []
        factors = {}

        current_words = set(text_sample.lower().split())
        if len(current_words) <= 10:
            return 0, [], {}

        for prev_sub in database.get_submissions_by_fingerprint(fingerprint):
            prev_text = prev_sub.get("metadata", {}).get("text_sample", "")
            if not prev_text or prev_text == text_sample:
                continue

            prev_words = set(prev_text.lower().split())
            if len(prev_words) <= 10:
                continue

            overlap = len(current_words & prev_words) / len(current_words | prev_words)
            if overlap > 0.7:
                score += 20
                signals.append("🔴 Content 70%+ similar to previous submission")
                factors["high_similarity"] = overlap
                break
            if overlap > 0.5:
                score += 10
                signals.append("⚠ Content 50%+ similar to previous submission")
                factors["medium_similarity"] = overlap
                break

        return score, signals, factors

    def _score_ai_markers(self, text_sample: str) -> tuple:
        """Score obvious AI-style marker usage."""
        ai_markers = ["however", "furthermore", "in conclusion", "in summary", "notably"]
        marker_count = sum(1 for marker in ai_markers if marker in text_sample.lower())

        if marker_count < 3:
            return 0, [], {}

        score = 5
        signals = ["• Possible AI-generated content (academic markers detected)"]
        factors = {"ai_markers": marker_count}
        return score, signals, factors
    
    def _check_file_name_pattern(self, name1: str, name2: str) -> bool:
        """Check if two filenames follow a pattern"""
        # Strip extensions
        n1 = name1.rsplit(".", 1)[0].lower()
        n2 = name2.rsplit(".", 1)[0].lower()
        
        # Check for version patterns like Paper_v1, Paper_v2
        import re
        pattern1 = re.sub(r'_v\d+|_\d+|v\d+', '', n1)
        pattern2 = re.sub(r'_v\d+|_\d+|v\d+', '', n2)
        
        if pattern1 == pattern2 and pattern1:
            return True
        
        # Check for common prefixes
        if len(n1) >= 5 and len(n2) >= 5 and n1[:5] == n2[:5]:
            return True
        
        return False
    
    def _get_risk_level(self, score: int) -> str:
        """Determine risk level based on score"""
        for level, (low, high) in self.risk_levels.items():
            if low <= score < high:
                return level
        return "critical"
    
    def _get_recommendation(self, score: int, signals: List[str]) -> str:
        """Generate recommendation based on score and signals"""
        if score < 30:
            return "✓ APPROVED: Submission appears legitimate"
        elif score < 60:
            return "⚠ REVIEW: Manual review recommended"
        elif score < 85:
            return "🔴 FLAG: High risk - likely spam/duplicate accounts"
        else:
            return "🚫 REJECT: Critical risk - suspected multi-account abuse"
```

---

## users.py

Simple editor authentication module.

```python
"""Shared user definitions for the single editor account."""

from typing import Dict

EDITOR_ACCOUNT = {
	"name": "Editor",
	"email": "editor@tnf.com",
	"password": "editor@123",
}


def get_editor_account() -> Dict[str, str]:
	"""Return the configured editor identity."""
	return dict(EDITOR_ACCOUNT)


def is_editor_credentials(email: str, password: str) -> bool:
	"""Check whether the supplied credentials match the editor account."""
	return email.strip().lower() == EDITOR_ACCOUNT["email"] and password == EDITOR_ACCOUNT["password"]


def build_editor_session() -> Dict[str, str]:
	"""Build the session payload used by the frontend after editor login."""
	return {
		"name": EDITOR_ACCOUNT["name"],
		"email": EDITOR_ACCOUNT["email"],
		"role": "editor",
		"authenticated": True,
	}
```

---

## requirements.txt

Python dependencies.

```
fastapi==0.104.1
uvicorn==0.24.0
python-multipart==0.0.6
firebase-admin==6.5.0
PyMuPDF==1.23.8
python-docx==0.8.11
redis==5.0.1
numpy==1.24.3
scikit-learn==1.3.2
scipy==1.11.4
spacy==3.7.2
sentence-transformers==2.2.2
torch==2.1.1
python-magic==0.4.27
Pillow==10.1.0
python-dotenv==1.0.0
cors==1.0.1
pydantic==2.5.0
```

---

## runtime.txt

Python runtime version (for Heroku/deployment).

```
python-3.11.7
```

---

## Environment Variables (.env)

Create a `.env` file in the backend directory with:

```
BACKEND_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000
FIREBASE_PROJECT_ID=tnf-vibe-coding-challenge
FIREBASE_STORAGE_BUCKET=tnf-vibe-coding-challenge.firebasestorage.app
FIREBASE_CREDENTIALS_PATH=./credentials.json
# OR:
# FIREBASE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
# FIREBASE_SERVICE_ACCOUNT_JSON_B64=eyJ0eXBlIjoic2VydmljZV9hY2NvdW50IiwuLi59
```

---

## Running the Backend

```bash
python backend/main.py
```

Or with Uvicorn:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Visit `http://localhost:8000/docs` for interactive API documentation.
