================================================================================
                    RENDER DEPLOYMENT GUIDE - STEP BY STEP
================================================================================

Your Frontend: https://tnf-risk-analyzer.vercel.app/
Backend Repo: Deepu1004/backend (on GitHub)

================================================================================
                       STEP 1: PREPARE YOUR CODE
================================================================================

The code has been updated to support production URLs. 

Local .env file (already created):
File: .env.example
Contents show what variables are needed for both local and production.

For LOCAL TESTING, create .env in your backend root directory:

  BACKEND_URL=http://localhost:8000
  FRONTEND_URL=http://localhost:3000
  PORT=8000
  HOST=0.0.0.0
  DEBUG=False

================================================================================
                   STEP 2: PUSH CODE TO GITHUB
================================================================================

Open Terminal in your project directory:

  $ cd /Users/satyanagasai.deepakvaranasi/Documents/Vibe\ Coding\ Challenge/backend

Make sure Git is initialized:
  $ git status

If not initialized:
  $ git init
  $ git remote add origin https://github.com/Deepu1004/backend.git

Add and commit your changes:
  $ git add .
  $ git commit -m "Update backend for production deployment with environment variables"

Push to GitHub:
  $ git push -u origin main

Verify on GitHub: https://github.com/Deepu1004/backend
(You should see readme.txt and backend_code.txt there)

================================================================================
                   STEP 3: CREATE RENDER SERVICE
================================================================================

1. Go to https://render.com
2. Log in with your GitHub account (or create account)
3. Click "New +"
4. Select "Web Service"
5. Click "Connect" next to your "backend" repository
6. Wait for it to connect and show the list

================================================================================
                   STEP 4: CONFIGURE RENDER SERVICE
================================================================================

Fill in these settings:

NAME:
  authorprint-backend

REGION:
  Choose closest to your users (e.g., us-east-1 or us-west-1)

BRANCH:
  main

RUNTIME:
  Python 3

ROOT DIRECTORY:
  Leave empty (or put . if your files are at project root)

BUILD COMMAND:
  $ pip install -r requirements.txt

START COMMAND:
  $ uvicorn main:app --host 0.0.0.0 --port 8000

INSTANCE TYPE:
  Free (for testing) or Starter+ (production recommended)

AUTO-DEPLOY:
  Enable (so it deploys automatically when you push to GitHub)

================================================================================
                STEP 5: SET ENVIRONMENT VARIABLES
================================================================================

After clicking "Create Web Service", before deployment:

1. Scroll down to "Environment" section
2. Add these variables:

┌─────────────────────────────────────────────────────────────┐
│ NAME              │ VALUE                                   │
├─────────────────────────────────────────────────────────────┤
│ BACKEND_URL       │ (You'll get this after first deploy)   │
│ FRONTEND_URL      │ https://tnf-risk-analyzer.vercel.app   │
│ PORT              │ 8000                                    │
│ HOST              │ 0.0.0.0                                │
│ DEBUG             │ False                                  │
│ PYTHONUNBUFFERED  │ 1                                      │
└─────────────────────────────────────────────────────────────┘

NEXT STEPS:
- Leave BACKEND_URL empty for now (or put a placeholder)
- Click "Save Changes"

================================================================================
                  STEP 6: INITIAL DEPLOYMENT
================================================================================

Click "Create Web Service"

Render will now:
1. Start building (takes 2-5 minutes)
2. Show build logs in real-time
3. Deploy the application
4. Show your service URL

Watch the logs - you should see:
  "Application startup complete"
  "Uvicorn running on http://0.0.0.0:8000"

Once deployment is complete, you'll see your URL:
  https://authorprint-backend-xxxx.onrender.com
  (The xxxx part will be random)

COPY THIS URL - you'll need it next!

================================================================================
            STEP 7: ADD BACKEND_URL ENVIRONMENT VARIABLE
================================================================================

Now that you have your Render URL, update the environment variable:

1. Go back to your service Dashboard on Render
2. Click "Environment" tab
3. Find and edit BACKEND_URL
4. Change it to: https://authorprint-backend-xxxx.onrender.com
   (Use YOUR actual URL)
5. Click "Save"

The service will automatically redeploy with the new environment variable.

================================================================================
                  STEP 8: VERIFY BACKEND IS WORKING
================================================================================

Test your backend health endpoint:

Open browser and visit:
  https://authorprint-backend-xxxx.onrender.com/api/health

You should see:
  {"status": "ok", "timestamp": 1234567890.123}

Test API documentation:
  https://authorprint-backend-xxxx.onrender.com/docs

This shows interactive Swagger UI with all endpoints!

================================================================================
             STEP 9: UPDATE FRONTEND TO USE NEW BACKEND URL
================================================================================

Your frontend needs to know your backend URL.

In your frontend code (Vercel), update the API calls:

CHANGE FROM:
  http://localhost:8000/api/...

CHANGE TO:
  https://authorprint-backend-xxxx.onrender.com/api/...

Common places to update:
1. API configuration file
2. Environment variables in Vercel
3. Any hardcoded API URLs

VERCEL ENVIRONMENT VARIABLES:
1. Go to https://vercel.com/dashboard
2. Select your project (tnf-risk-analyzer)
3. Go to "Settings" → "Environment Variables"
4. Add:
   Name: REACT_APP_API_URL
   Value: https://authorprint-backend-xxxx.onrender.com
5. Save and redeploy

Your frontend will now make requests to the deployed backend!

================================================================================
                   STEP 10: TEST END-TO-END
================================================================================

1. Open your frontend: https://tnf-risk-analyzer.vercel.app/

2. Try uploading a file

3. Verify it works:
   - File gets uploaded
   - Risk score appears
   - No CORS errors in browser console

4. Check Render logs:
   Go to Render Dashboard → Your Service → "Logs"
   Should show POST /api/upload requests

================================================================================
                    STEP 11: TROUBLESHOOTING
================================================================================

ISSUE: "503 Service Unavailable" or "Build failed"
SOLUTION:
  1. Check Render logs for errors
  2. Verify requirements.txt is correct
  3. Ensure main.py is at project root
  4. Check if python-magic library causing issues (common on Render)

ISSUE: CORS errors in browser console
SOLUTION:
  1. Verify FRONTEND_URL is set correctly in Render Environment
  2. Check URL includes https:// protocol
  3. No trailing slashes in URLs

ISSUE: "Module not found" errors
SOLUTION:
  1. Re-run: pip install -r requirements.txt
  2. Verify all dependencies are listed in requirements.txt

ISSUE: Files not persisting after redeploy
SOLUTION:
  This is normal on Render Free tier - use Postgres for persistent storage
  (Out of scope for this guide, but documented in readme.txt)

ISSUE: Service keeps spinning down (Free tier)
SOLUTION:
  Free tier auto-sleeps after 15 minutes of inactivity
  Set up a ping or upgrade to Starter tier ($7/month)

================================================================================
                      STEP 12: MONITORING
================================================================================

View logs anytime:
  1. Render Dashboard → Your Service
  2. Click "Logs" tab
  3. Real-time updates as requests come in

View errors:
  1. Same Logs tab
  2. Red lines = errors
  3. Copy error and google it

Performance:
  1. Render Dashboard → "Metrics" tab
  2. Monitor CPU, Memory, Network

================================================================================
            UPDATE: COMMAND TO FIND YOUR RENDER URL
================================================================================

After first deployment completes, your URL will be shown as:

  authorprint-backend-[random-string].onrender.com

You can also find it:
1. Render Dashboard
2. Select your service
3. Top of page shows: "authorprint-backend — [URL]"

Take note of this URL - you'll need it multiple times!

================================================================================
                       QUICK REFERENCE
================================================================================

Frontend: https://tnf-risk-analyzer.vercel.app/
Backend URL Format: https://authorprint-backend-xxxx.onrender.com

Required Environment Variables on Render:
  ✓ BACKEND_URL=https://authorprint-backend-xxxx.onrender.com
  ✓ FRONTEND_URL=https://tnf-risk-analyzer.vercel.app
  ✓ PORT=8000
  ✓ HOST=0.0.0.0
  ✓ DEBUG=False
  ✓ PYTHONUNBUFFERED=1

API Endpoints:
  GET  /api/health                          - Health check
  POST /api/upload                          - Upload document
  GET  /api/submissions                     - List submissions
  GET  /api/submissions/{id}                - Get submission details
  POST /api/submissions/{id}/decision       - Review submission
  GET  /api/stats                           - Dashboard stats

Test after deployment:
  https://authorprint-backend-xxxx.onrender.com/docs  - API documentation
  https://authorprint-backend-xxxx.onrender.com/api/health - Health check

================================================================================
                     FINAL CHECKLIST BEFORE GOING LIVE
================================================================================

Code Preparation:
  [ ] Pushed code to GitHub (Deepu1004/backend)
  [ ] .env.example created with required variables
  [ ] main.py uses BACKEND_URL and FRONTEND_URL from environment
  [ ] requirements.txt includes all dependencies

Render Setup:
  [ ] Service created on Render
  [ ] Build command: pip install -r requirements.txt
  [ ] Start command: uvicorn main:app --host 0.0.0.0 --port 8000
  [ ] Environment variables set correctly
  [ ] Auto-deploy enabled

Testing:
  [ ] Backend health endpoint works
  [ ] API docs accessible at /docs
  [ ] Frontend can reach backend (no CORS errors)
  [ ] File upload works end-to-end
  [ ] Risk scores calculate correctly

Frontend Integration:
  [ ] Frontend knows the Render backend URL
  [ ] API calls point to Render URL (not localhost)
  [ ] Vercel environment variables updated
  [ ] Frontend redeployed after URL changes

Monitoring:
  [ ] Can view Render logs
  [ ] Monitoring metrics visible
  [ ] Error handling in place

================================================================================
                       DEPLOYMENT COMPLETE!
================================================================================

Your application is now live with:
  Frontend: https://tnf-risk-analyzer.vercel.app/
  Backend: https://authorprint-backend-xxxx.onrender.com

Both are connected and communicating!

For any issues or questions, refer to:
  - readme.txt for general documentation
  - This file for Render-specific deployment
  - Render Dashboard Logs for error diagnostics

================================================================================
                      Last Updated: April 30, 2026
================================================================================
