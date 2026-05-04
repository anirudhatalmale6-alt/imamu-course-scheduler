import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.database import engine, SessionLocal, Base
from app.models.models import *
from app.routes import auth, courses, registration, schedule
from app.services.xml_import import import_university_xml
from app.config import settings

app = FastAPI(title="IMAMU Course Scheduler", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(registration.router)
app.include_router(schedule.router)

frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        from app.models.models import Day as DayModel
        if db.query(DayModel).count() == 0:
            xml_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), settings.UNIVERSITY_XML)
            if not os.path.exists(xml_path):
                xml_path = os.path.join(os.getcwd(), settings.UNIVERSITY_XML)
            if os.path.exists(xml_path):
                print(f"Importing university data from {xml_path}...")
                import_university_xml(db, xml_path)
                db.commit()
            else:
                print(f"university.xml not found at {xml_path}")
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "IMAMU Course Scheduler"}


if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=os.path.join(frontend_dir, "static")), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        file_path = os.path.join(frontend_dir, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dir, "index.html"))
