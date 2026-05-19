"""
main.py - FastAPI Application Entry Point

This is the main file that bootstraps the IMAMU Course Scheduler web application.
It creates the FastAPI app instance, configures middleware, registers API route
modules, seeds the database on first run, and serves the React frontend as a
Single-Page Application (SPA).

Key responsibilities:
  1. Create and configure the FastAPI application.
  2. Enable CORS so the frontend (running on a different port during dev) can
     call the API.
  3. Register all API route groups (auth, courses, registration, schedule).
  4. On startup, create database tables and import seed data from an XML file
     if the database is empty.
  5. Serve the compiled React frontend for any non-API route (SPA fallback).
"""

import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.database import engine, SessionLocal, Base
from app.models.models import *  # Import all models so SQLAlchemy registers them
from app.routes import auth, courses, registration, schedule
from app.services.xml_import import import_university_xml
from app.config import settings

# ---------------------------------------------------------------------------
# 1. Create the FastAPI application instance
# ---------------------------------------------------------------------------
# `title` and `version` appear in the auto-generated Swagger/OpenAPI docs at /docs
app = FastAPI(title="IMAMU Course Scheduler", version="1.0.0")

# ---------------------------------------------------------------------------
# 2. Configure CORS (Cross-Origin Resource Sharing) middleware
# ---------------------------------------------------------------------------
# This allows the React frontend (which may run on a different origin during
# development, e.g. http://localhost:3000) to make HTTP requests to this API.
# In production you should restrict `allow_origins` to your actual domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Accept requests from any origin
    allow_credentials=True,       # Allow cookies / Authorization headers
    allow_methods=["*"],          # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],          # Allow all request headers
)

# ---------------------------------------------------------------------------
# 3. Register API route groups (routers)
# ---------------------------------------------------------------------------
# Each router is defined in its own file under app/routes/ and handles a
# specific area of the API (authentication, course CRUD, registration, scheduling).
app.include_router(auth.router)          # /api/auth/* endpoints (login, register)
app.include_router(courses.router)       # /api/courses/* endpoints (CRUD for courses, sections)
app.include_router(registration.router)  # /api/registration/* endpoints (enroll, drop)
app.include_router(schedule.router)      # /api/schedule/* endpoints (generate, save schedules)

# Path to the compiled React frontend build directory (one level up from app/)
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")


# ---------------------------------------------------------------------------
# 4. Startup event - run once when the server starts
# ---------------------------------------------------------------------------
@app.on_event("startup")
def startup():
    """
    Called automatically when the FastAPI server starts up.

    Steps:
      1. Create all database tables that don't exist yet (based on SQLAlchemy
         models). This is safe to call repeatedly - it won't drop existing data.
      2. Check if the database is empty (no Day records). If so, import seed
         data from the university.xml file that contains departments, courses,
         instructors, rooms, time slots, etc.
    """
    # Create tables from all registered SQLAlchemy models
    Base.metadata.create_all(bind=engine)

    # Open a database session to check for and import seed data
    db = SessionLocal()
    try:
        from app.models.models import Day as DayModel

        # Use the Day table as an indicator: if it's empty, the DB hasn't been seeded yet
        if db.query(DayModel).count() == 0:
            # Try to locate the XML file relative to the project root first
            xml_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), settings.UNIVERSITY_XML)

            # Fallback: look in the current working directory
            if not os.path.exists(xml_path):
                xml_path = os.path.join(os.getcwd(), settings.UNIVERSITY_XML)

            if os.path.exists(xml_path):
                print(f"Importing university data from {xml_path}...")
                import_university_xml(db, xml_path)  # Parse XML and insert rows
                db.commit()                           # Persist all inserted rows
            else:
                print(f"university.xml not found at {xml_path}")
    finally:
        db.close()  # Always close the session to release the DB connection


# ---------------------------------------------------------------------------
# 5. Health-check endpoint
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    """
    Simple health-check endpoint. Returns a JSON object confirming the API is
    running. Useful for monitoring tools and load balancers.
    """
    return {"status": "ok", "app": "IMAMU Course Scheduler"}


# ---------------------------------------------------------------------------
# 6. Serve the React SPA (Single-Page Application) frontend
# ---------------------------------------------------------------------------
# Only mount the frontend if the build directory exists (i.e. the React app
# has been compiled with `npm run build` and copied into backend/static/).
if os.path.exists(frontend_dir):
    # Serve JS/CSS/image assets from the React build's "static" sub-folder
    app.mount("/static", StaticFiles(directory=os.path.join(frontend_dir, "static")), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """
        SPA catch-all route. For any path that isn't matched by an API endpoint:
          - If a real file exists at that path (e.g. favicon.ico, manifest.json),
            serve it directly.
          - Otherwise, serve index.html so the React router can handle client-side
            navigation.
        """
        file_path = os.path.join(frontend_dir, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)            # Serve the actual file
        return FileResponse(os.path.join(frontend_dir, "index.html"))  # SPA fallback
