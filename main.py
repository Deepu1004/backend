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
    get_all_submissions,
    get_submission_by_id,
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
    journal: Annotated[str, Form(default="Unknown Journal")],
    author_name: Annotated[str, Form(default="Anonymous")],
    document_type: Annotated[str, Form(default="Paper")],
    document_kind: Annotated[str, Form(default="Science")],
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
            "file_url": f"{BACKEND_URL}/uploads/{saved_filename}",
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
    reviewer_name: Annotated[str, Form(default="Editor")],
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
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats", responses={500: {"description": "Failed to load statistics"}})
async def get_dashboard_stats():
    """Get statistics for the editor dashboard"""
    try:
        return get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
