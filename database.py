import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import threading

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "submissions_db.json"
LOCK = threading.Lock()


def init_db():
    """Initialize database file if it doesn't exist"""
    if not DB_FILE.exists():
        with DB_FILE.open("w") as f:
            json.dump({"submissions": [], "accounts": {}}, f, indent=2)


def load_db() -> Dict[str, Any]:
    """Load database from JSON file"""
    with LOCK:
        if not DB_FILE.exists():
            init_db()
        with DB_FILE.open("r") as f:
            return json.load(f)


def save_db(data: Dict[str, Any]):
    """Save database to JSON file"""
    with LOCK:
        with DB_FILE.open("w") as f:
            json.dump(data, f, indent=2)


def add_submission(submission_data: Dict[str, Any]) -> str:
    """Add a new submission to database"""
    db = load_db()
    submission_id = f"sub_{datetime.now().timestamp()}"
    
    submission_data["id"] = submission_id
    submission_data["timestamp"] = datetime.now().isoformat()
    
    db["submissions"].append(submission_data)
    save_db(db)
    
    return submission_id


def update_submission(submission_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update a submission and return the updated record."""
    db = load_db()

    for index, submission in enumerate(db.get("submissions", [])):
        if submission.get("id") == submission_id:
            db["submissions"][index] = {**submission, **updates}
            save_db(db)
            return db["submissions"][index]

    return None


def get_all_submissions() -> List[Dict[str, Any]]:
    """Get all submissions from database"""
    db = load_db()
    return db.get("submissions", [])


def get_submission_by_id(submission_id: str) -> Dict[str, Any]:
    """Get a specific submission"""
    db = load_db()
    for sub in db.get("submissions", []):
        if sub.get("id") == submission_id:
            return sub
    return None


def get_submissions_by_fingerprint(fingerprint: str) -> List[Dict[str, Any]]:
    """Get all submissions with the same fingerprint"""
    db = load_db()
    return [
        sub for sub in db.get("submissions", [])
        if sub.get("fingerprint") == fingerprint
    ]


def get_submissions_by_content_hash(content_hash: str) -> List[Dict[str, Any]]:
    """Get all submissions with the same uploaded file hash"""
    db = load_db()
    return [
        sub for sub in db.get("submissions", [])
        if sub.get("metadata", {}).get("content_hash") == content_hash
    ]


def get_submissions_by_email(email: str) -> List[Dict[str, Any]]:
    """Get all submissions from a specific email"""
    db = load_db()
    return [
        sub for sub in db.get("submissions", [])
        if sub.get("email") == email
    ]


def get_recent_submissions(minutes: int = 10) -> List[Dict[str, Any]]:
    """Get submissions from the last N minutes"""
    from datetime import datetime, timedelta
    
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
    with LOCK:
        if DB_FILE.exists():
            DB_FILE.unlink()
        init_db()


def get_stats() -> Dict[str, Any]:
    """Get dashboard statistics"""
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
