================================================================================
                       AUTHORPRINT API - README
================================================================================

APPLICATION OVERVIEW:
AuthorPrint is a FastAPI-based backend application for detecting academic fraud 
and plagiarism through multi-layer risk scoring analysis. It analyzes document 
metadata, device fingerprints, writing styles, and content similarity to flag 
suspicious submissions.

================================================================================
                         TABLE OF CONTENTS
================================================================================

1. PREREQUISITES
2. LOCAL SETUP & RUNNING
3. DEPENDENCIES INSTALLATION
4. RUNNING LOCALLY
5. API ENDPOINTS
6. DEPLOYMENT ON RENDER.COM
7. ENVIRONMENT VARIABLES
8. TROUBLESHOOTING

================================================================================
                         1. PREREQUISITES
================================================================================

Before running this application, ensure you have:

- Python 3.9+ installed (https://www.python.org/downloads/)
- pip (Python package manager - comes with Python)
- Git (for version control)
- A code editor (VS Code, PyCharm, etc.)
- For Render.com deployment: A GitHub account with the repository

System Requirements:
- RAM: Minimum 2GB
- Disk Space: 500MB
- Internet Connection: Required for dependencies and deployment

================================================================================
                    2. LOCAL SETUP & RUNNING
================================================================================

STEP 1: Clone and Navigate to Project
================================================================================
1. Open Terminal/Command Prompt
2. Navigate to your project directory or create a new one
3. Clone the repository (if applicable):
   $ git clone <repository-url>
   $ cd backend

STEP 2: Create Virtual Environment
================================================================================
Virtual environments isolate project dependencies. This is HIGHLY RECOMMENDED.

Windows:
  $ python -m venv venv
  $ venv\Scripts\activate

macOS/Linux:
  $ python3 -m venv venv
  $ source venv/bin/activate

After activation, your terminal should show (venv) at the beginning.

STEP 3: Install Dependencies
================================================================================
With virtual environment activated:
  $ pip install -r requirements.txt

This installs all required packages:
- fastapi (web framework)
- uvicorn (ASGI server)
- PyMuPDF (PDF processing)
- python-docx (Word document processing)
- scikit-learn (ML utilities)
- redis (caching)
- python-dotenv (environment variables)
- And more...

STEP 4: Initialize Database
================================================================================
The application uses JSON file for database (submissions_db.json).
This will be automatically created on first RUN.

STEP 5: Run Locally
================================================================================
With virtual environment activated:
  $ uvicorn main:app --reload --host 0.0.0.0 --port 8000

Output should show:
  Uvicorn running on http://127.0.0.1:8000
  Application startup complete

The --reload flag enables hot-reload during development (auto-restart on code changes)

STEP 6: Verify Application
================================================================================
Open browser and visit:
  http://localhost:8000/api/health

Expected response:
  {"status": "ok", "timestamp": 1234567890.123}

Access API Documentation:
  http://localhost:8000/docs (Swagger UI)
  http://localhost:8000/redoc (ReDoc)

================================================================================
                       3. DEPENDENCIES INSTALLATION
================================================================================

The application requires these packages (in requirements.txt):

Core Framework:
- FastAPI (web framework)
- Uvicorn (server)
- python-multipart (form data handling)
- Pydantic (data validation)
- CORS (cross-origin requests)

Document Processing:
- PyMuPDF (PDF extraction)
- python-docx (Word documents)
- python-magic (file type detection)

Machine Learning & NLP:
- scikit-learn (machine learning)
- scipy (scientific computing)
- numpy (numerical computing)
- torch (deep learning, required by sentence-transformers)
- sentence-transformers (text embeddings)
- spacy (NLP)

Utilities:
- redis (caching/sessions - optional if not used)
- python-dotenv (environment configuration)
- Pillow (image processing)

Install all at once:
  $ pip install -r requirements.txt

Or install specific packages:
  $ pip install fastapi uvicorn PyMuPDF python-docx

================================================================================
                      4. APPLICATION API ENDPOINTS
================================================================================

1. HEALTH CHECK
  Method: GET
  URL: /api/health
  Purpose: Check if API is running
  Response: {"status": "ok", "timestamp": 1234567890.123}

2. UPLOAD SUBMISSION
  Method: POST
  URL: /api/upload
  Purpose: Upload and analyze a document for fraud
  Parameters:
    - file (File): PDF, DOCX, or TXT file
    - fingerprint (String): Device fingerprint ID
    - email (String): Submitter email
    - journal (String, optional): Journal name
    - author_name (String, optional): Author name
    - document_type (String, optional): Type of document
    - document_kind (String, optional): Kind of document
  
  Response: {
    "success": true,
    "submission_id": "sub_1234567890.123",
    "risk_score": 45,
    "risk_level": "medium",
    "similar_document": {...} or null
  }

3. LIST ALL SUBMISSIONS
  Method: GET
  URL: /api/submissions
  Purpose: Get all submissions for dashboard
  Response: {
    "submissions": [
      {
        "id": "sub_...",
        "title": "filename.pdf",
        "author_name": "John Doe",
        "email": "john@example.com",
        "score": 45,
        "workflow_status": "pending",
        ...
      }
    ]
  }

4. GET SUBMISSION DETAILS
  Method: GET
  URL: /api/submissions/{submission_id}
  Purpose: Get full details of a specific submission
  Response: {
    "submission": {
      "id": "sub_...",
      "title": "filename.pdf",
      "risk_score": 45,
      "risk_level": "medium",
      "signals": [...],
      "metadata": {...},
      ...
    }
  }

5. UPDATE REVIEW DECISION
  Method: POST
  URL: /api/submissions/{submission_id}/decision
  Purpose: Accept or reject a submission after review
  Parameters:
    - decision (String): "accept" or "reject"
    - reviewer_name (String, optional): Name of reviewer
  
  Response: {
    "success": true,
    "submission_id": "sub_...",
    "workflow_status": "accepted" or "rejected"
  }

6. GET DASHBOARD STATISTICS
  Method: GET
  URL: /api/stats
  Purpose: Get summary statistics
  Response: {
    "total_submissions": 50,
    "high_risk_submissions": 5,
    "critical_risk_submissions": 2,
    "average_risk_score": 35.8
  }

================================================================================
                   5. DEPLOYMENT ON RENDER.COM
================================================================================

STEP 1: Prepare GitHub Repository
================================================================================
1. Create a GitHub repository
2. Push your code (including requirements.txt)
3. Your project structure should be:
   backend/
     ├── main.py
     ├── database.py
     ├── metadata_extractor.py
     ├── risk_scoring.py
     ├── users.py
     ├── requirements.txt
     ├── submissions_db.json
     └── uploads/

STEP 2: Create Render Account
================================================================================
1. Go to https://render.com
2. Sign up with your GitHub account
3. Authorize Render to access your GitHub repositories

STEP 3: Create New Web Service
================================================================================
1. Log in to Render Dashboard
2. Click "New +"
3. Select "Web Service"
4. Connect your GitHub repository
5. Choose the repository and branch (main)

STEP 4: Configure Service Settings
================================================================================

Name: authorprint-api (or your preferred name)

Region: Choose closest to your users (e.g., us-east-1 for USA)

Branch: main

Root Directory: backend (if project is in subdirectory)
            or . (if project is at root)

Runtime: Python 3

Build Command:
  $ pip install -r requirements.txt

Start Command:
  $ uvicorn main:app --host 0.0.0.0 --port 8000

STEP 5: Set Environment Variables
================================================================================
In Render Dashboard under Environment:

Add the following variables:
  PYTHONUNBUFFERED=1
  PORT=8000

Example environment setup:
  - Click "Environment" tab
  - Add each variable as a new row
  - Save changes

STEP 6: Configure Advanced Settings (Optional)
================================================================================

Instance Type: Free (or Starter for production)
- Free: Spins down after 15 minutes of inactivity
- Starter: Better for production ($7/month)

Auto-Deploy: Enable to auto-deploy on GitHub push

Health Check Path: /api/health

Max Num Processes: 4

Request Timeout: 30 seconds

STEP 7: Deploy
================================================================================
1. Click "Create Web Service"
2. Render will start building and deploying
3. Watch build logs in the dashboard
4. Deployment typically takes 2-5 minutes

STEP 8: Verify Deployment
================================================================================
Once deployment is complete:

1. Your service URL will appear: https://authorprint-api-xxxx.onrender.com

2. Test health endpoint:
   https://authorprint-api-xxxx.onrender.com/api/health

3. Access API docs:
   https://authorprint-api-xxxx.onrender.com/docs

4. Test upload endpoint with any of your client applications

STEP 9: Set Up Database Persistence (Optional but Recommended)
================================================================================

By default, submissions_db.json will be lost when service redeploys.

For persistent storage:
1. Use Render PostgreSQL add-on (recommended for production)
2. Or use external file storage service
3. Or update database.py to use cloud storage

Quick Fix (temporary):
- Submissions persist as long as service doesn't redeploy
- On free tier, service may restart causing data loss

STEP 10: Monitoring & Maintenance
================================================================================
In Render Dashboard:
- View real-time logs
- Monitor performance metrics
- Check deployment history
- Set up alerts for failures

================================================================================
                  6. ENVIRONMENT VARIABLES
================================================================================

Create a .env file in project root (NOT committed to Git):

# Server Configuration
PORT=8000
HOST=0.0.0.0
PYTHONUNBUFFERED=1

# Optional - Add in production
DEBUG=False
ENVIRONMENT=production

Firebase note:
- Keep the Firebase service account on the backend only.
- Do not put the service account JSON in the frontend.
- If the frontend ever talks directly to Firebase, it should only receive the public web config, not secret credentials.

Example .env:
  PORT=8000
  DEBUG=False

Load in main.py using python-dotenv:
  from dotenv import load_dotenv
  load_dotenv()

================================================================================
                       7. TROUBLESHOOTING
================================================================================

ISSUE: "ModuleNotFoundError: No module named 'fastapi'"
SOLUTION:
  - Verify virtual environment is activated
  - Run: pip install -r requirements.txt
  - Check Python version: python --version

ISSUE: "Port 8000 already in use"
SOLUTION:
  - Kill process using port 8000
  - Or use different port: uvicorn main:app --port 8001
  
ISSUE: Render deployment fails
SOLUTION:
  - Check build logs in Render dashboard
  - Verify requirements.txt exists and is correct
  - Ensure main.py is at project root (or specify Root Directory)
  - Verify start command: uvicorn main:app --host 0.0.0.0 --port 8000

ISSUE: "FileNotFoundError: submissions_db.json"
SOLUTION:
  - Database auto-creates on first run
  - Ensure 'uploads' directory exists
  - Check file permissions

ISSUE: CORS errors when calling from frontend
SOLUTION:
  - CORS is already enabled in main.py
  - Verify frontend URL is correct
  - Check browser console for actual error

ISSUE: Deployed service keeps spinning down
SOLUTION:
  - You're using free tier (auto sleep after 15 min inactivity)
  - Upgrade to Starter tier ($7/month)
  - Or set up periodic ping to keep alive

================================================================================
                      8. DEVELOPMENT WORKFLOW
================================================================================

For local development:

1. Activate virtual environment:
   $ source venv/bin/activate  (macOS/Linux)
   $ venv\Scripts\activate     (Windows)

2. Install dev dependencies:
   $ pip install -r requirements.txt

3. Run with auto-reload:
   $ uvicorn main:app --reload --port 8000

4. Make code changes - server auto-restarts

5. Test at http://localhost:8000/docs

6. Commit and push changes:
   $ git add .
   $ git commit -m "Your message"
   $ git push

7. Render auto-deploys if auto-deploy is enabled

================================================================================
                      9. FILE DESCRIPTIONS
================================================================================

main.py
  - FastAPI application setup
  - API endpoint definitions
  - Request handling and responses
  - CORS middleware configuration
  - File upload processing

database.py
  - JSON file database operations
  - Submission storage and retrieval
  - Account linking functionality
  - Database synchronization

metadata_extractor.py
  - PDF, DOCX, TXT file processing
  - Metadata extraction
  - Content hashing
  - Document classification
  - Text analysis

risk_scoring.py
  - Multi-layer risk calculation
  - Device fingerprint analysis
  - Metadata forensics
  - Behavioral pattern detection
  - Content similarity checking
  - AI-generated content detection

users.py
  - Editor account management
  - Authentication credentials
  - Session management

requirements.txt
  - All Python dependencies
  - Version specifications

submissions_db.json
  - JSON database file
  - Stores all submissions
  - Account linking data

uploads/
  - Directory for uploaded files
  - Stores submitted documents

================================================================================
                         10. PRODUCTION CHECKLIST
================================================================================

Before going to production:

[ ] Update DEBUG to False in environment
[ ] Set up persistent database (PostgreSQL recommended)
[ ] Set up file upload storage (AWS S3 or similar)
[ ] Enable HTTPS (Render does this automatically)
[ ] Set up monitoring and alerts
[ ] Configure backup strategy
[ ] Review security settings
[ ] Test all API endpoints
[ ] Load test the application
[ ] Set up error logging
[ ] Document API for frontend developers
[ ] Create deployment runbook

================================================================================
                          11. QUICK REFERENCE
================================================================================

Local Commands:
  $ python3 -m venv venv              # Create virtual env
  $ source venv/bin/activate          # Activate (macOS/Linux)
  $ pip install -r requirements.txt   # Install dependencies
  $ uvicorn main:app --reload         # Run with auto-reload
  $ deactivate                        # Deactivate virtual env

File Locations:
  - API: http://localhost:8000
  - Docs: http://localhost:8000/docs
  - Database: submissions_db.json
  - Uploads: uploads/

Render Deployment:
  1. Push to GitHub
  2. Create service on Render
  3. Connect repository
  4. Configure start command
  5. Deploy

Testing:
  $ curl http://localhost:8000/api/health
  $ curl -X POST http://localhost:8000/api/upload -F "file=@test.pdf" ...

================================================================================
                       12. SUPPORT & RESOURCES
================================================================================

Official Documentation:
  - FastAPI: https://fastapi.tiangolo.com/
  - Uvicorn: https://www.uvicorn.org/
  - Render: https://render.com/docs
  - Python: https://docs.python.org/3/

Useful Links:
  - FastAPI Deployment: https://fastapi.tiangolo.com/deployment/
  - Render Python Guide: https://render.com/docs/deploy-python

================================================================================
                           END OF README
================================================================================

For questions or issues, refer to:
1. Official documentation links above
2. GitHub Issues in repository
3. Render support dashboard

Last Updated: 2026
================================================================================
