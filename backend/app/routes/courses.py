"""
Course Management API Routes
=============================
This file defines the REST API endpoints for managing courses, sections,
and related reference data (departments, instructors, rooms, days, timeslots).

Endpoints overview:
  - GET  /api/departments        - List all departments.
  - GET  /api/instructors        - List all instructors.
  - GET  /api/rooms              - List all rooms.
  - GET  /api/days               - List all working days (Sun-Thu, etc.).
  - GET  /api/timeslots          - List all daily time slots (periods).
  - GET  /api/courses            - List courses with optional filters.
  - GET  /api/courses/{id}       - Get a single course by ID.
  - POST /api/courses            - Create a new course (instructor/admin only).
  - PUT  /api/courses/{id}       - Update an existing course (instructor/admin only).
  - DELETE /api/courses/{id}     - Delete a course (instructor/admin only).
  - POST /api/sections           - Create a new section (instructor/admin only).
  - GET  /api/sections           - List sections with optional filters.

Role-based access: Only users with INSTRUCTOR or ADMIN roles can create,
update, or delete courses and sections. Read endpoints are open to all
authenticated users.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List
from app.database import get_db
from app.models.models import User, UserRole, Course, Section, Department
from app.schemas import (
    CourseCreate, CourseUpdate, CourseResponse, SectionCreate, SectionResponse,
    DepartmentResponse, InstructorResponse, RoomResponse, DayResponse, TimeSlotResponse,
)
from app.services.auth import get_current_user
from app.models.models import Instructor, Room, Day, TimeSlot

# All endpoints in this file are grouped under the "/api" prefix.
router = APIRouter(prefix="/api", tags=["courses"])


def _course_to_response(course: Course) -> CourseResponse:
    """
    Convert a SQLAlchemy Course object into a CourseResponse schema.

    This helper manually maps the ORM model to the Pydantic response model,
    including nested data like prerequisite course codes and section summaries.
    It is used by every endpoint that returns course data to ensure a
    consistent response format.
    """
    return CourseResponse(
        id=course.id,
        code=course.code,
        name=course.name,
        level=course.level,
        credits=course.credits,
        is_lab=course.is_lab,
        is_archived=course.is_archived,
        department_id=course.department_id,
        department_name=course.department.name if course.department else "",
        # Flatten prerequisites to a list of course codes (e.g., ["CS101", "CS201"])
        prerequisites=[p.code for p in course.prerequisites],
        # Build a summary dict for each section of this course
        sections=[
            {
                "id": s.id,
                "section_id": s.section_id,
                "gender": s.gender,
                "capacity": s.capacity,
                "enrolled": s.enrolled,
                "is_archived": s.is_archived,
            }
            for s in course.sections
        ],
    )


# ── Reference Data Endpoints ────────────────────────────────────────────

@router.get("/departments", response_model=List[DepartmentResponse])
def list_departments(db: Session = Depends(get_db)):
    """Return all academic departments (e.g., Computer Science, IT)."""
    return db.query(Department).all()


@router.get("/instructors", response_model=List[InstructorResponse])
def list_instructors(db: Session = Depends(get_db)):
    """Return all instructors/professors in the system."""
    return db.query(Instructor).all()


@router.get("/rooms", response_model=List[RoomResponse])
def list_rooms(db: Session = Depends(get_db)):
    """Return all available rooms and labs across campus buildings."""
    return db.query(Room).all()


@router.get("/days", response_model=List[DayResponse])
def list_days(db: Session = Depends(get_db)):
    """Return all working days, ordered by their ID (e.g., Sun=1, Mon=2, ...)."""
    return db.query(Day).order_by(Day.id).all()


@router.get("/timeslots", response_model=List[TimeSlotResponse])
def list_timeslots(db: Session = Depends(get_db)):
    """Return all daily time periods (e.g., 08:00-09:00), ordered chronologically."""
    return db.query(TimeSlot).order_by(TimeSlot.slot_order).all()


# ── Course CRUD Endpoints ───────────────────────────────────────────────

@router.get("/courses", response_model=List[CourseResponse])
def list_courses(
    department_id: int = None,
    level: int = None,
    include_archived: bool = False,
    db: Session = Depends(get_db),
):
    """
    List all courses with optional filtering.

    Query parameters:
      - department_id: Filter by department (e.g., CS department only).
      - level: Filter by academic level (1-8, representing semesters).
      - include_archived: If True, include courses that have been archived.

    Uses joinedload to eagerly fetch related department, sections, and
    prerequisites in a single query to avoid N+1 performance problems.
    """
    q = db.query(Course).options(joinedload(Course.department), joinedload(Course.sections), joinedload(Course.prerequisites))
    # By default, exclude archived courses unless explicitly requested
    if not include_archived:
        q = q.filter(Course.is_archived == False)
    if department_id:
        q = q.filter(Course.department_id == department_id)
    if level:
        q = q.filter(Course.level == level)
    courses = q.all()
    return [_course_to_response(c) for c in courses]


@router.get("/courses/{course_id}", response_model=CourseResponse)
def get_course(course_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a single course by its database ID.

    Eagerly loads the department, sections, and prerequisites relationships.
    Returns 404 if the course does not exist.
    """
    course = db.query(Course).options(
        joinedload(Course.department), joinedload(Course.sections), joinedload(Course.prerequisites)
    ).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return _course_to_response(course)


@router.post("/courses", response_model=CourseResponse)
def create_course(
    data: CourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new course. Restricted to INSTRUCTOR and ADMIN roles.

    Steps:
      1. Verify the user has permission (instructor or admin).
      2. Ensure the course code is unique (no duplicates).
      3. Create the Course record and optionally link prerequisite courses.
      4. Persist to the database and return the new course.
    """
    # Authorization check: only instructors and admins can create courses
    if current_user.role not in (UserRole.INSTRUCTOR, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Only instructors can create courses")
    # Prevent duplicate course codes (e.g., two "CS101" entries)
    if db.query(Course).filter(Course.code == data.code).first():
        raise HTTPException(status_code=400, detail="Course code already exists")

    course = Course(
        code=data.code,
        name=data.name,
        level=data.level,
        credits=data.credits,
        is_lab=data.is_lab,
        department_id=data.department_id,
    )
    # If prerequisite course codes were provided, look them up and link them
    if data.prerequisite_codes:
        prereqs = db.query(Course).filter(Course.code.in_(data.prerequisite_codes)).all()
        course.prerequisites = prereqs
    db.add(course)
    db.commit()
    db.refresh(course)
    return _course_to_response(course)


@router.put("/courses/{course_id}", response_model=CourseResponse)
def update_course(
    course_id: int,
    data: CourseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update an existing course. Restricted to INSTRUCTOR and ADMIN roles.

    Only fields that are provided (not None) will be updated, allowing
    partial updates. For example, you can update just the name without
    changing the level or credits.
    """
    if current_user.role not in (UserRole.INSTRUCTOR, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Only instructors can update courses")
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Apply only the fields that were explicitly provided in the request
    if data.name is not None:
        course.name = data.name
    if data.level is not None:
        course.level = data.level
    if data.credits is not None:
        course.credits = data.credits
    if data.is_lab is not None:
        course.is_lab = data.is_lab
    if data.is_archived is not None:
        course.is_archived = data.is_archived
    # If prerequisites are being updated, replace the entire list
    if data.prerequisite_codes is not None:
        prereqs = db.query(Course).filter(Course.code.in_(data.prerequisite_codes)).all()
        course.prerequisites = prereqs

    db.commit()
    db.refresh(course)
    return _course_to_response(course)


@router.delete("/courses/{course_id}")
def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Permanently delete a course. Restricted to INSTRUCTOR and ADMIN roles.

    Returns 404 if the course does not exist.
    Note: This is a hard delete. For soft deletion, use the archive feature
    via the PUT endpoint (set is_archived=True).
    """
    if current_user.role not in (UserRole.INSTRUCTOR, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Only instructors can delete courses")
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    db.delete(course)
    db.commit()
    return {"message": "Course deleted"}


# ── Section Endpoints ───────────────────────────────────────────────────

@router.post("/sections", response_model=SectionResponse)
def create_section(
    data: SectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new section for a course. Restricted to INSTRUCTOR and ADMIN roles.

    A section represents one class group within a course (e.g., Section A
    for male students, Section B for female students), each with its own
    capacity and enrollment count.
    """
    if current_user.role not in (UserRole.INSTRUCTOR, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Only instructors can create sections")
    section = Section(
        section_id=data.section_id,
        gender=data.gender,
        capacity=data.capacity,
        course_id=data.course_id,
    )
    db.add(section)
    db.commit()
    db.refresh(section)
    # Fetch the parent course to include its code and name in the response
    course = db.query(Course).filter(Course.id == section.course_id).first()
    return SectionResponse(
        id=section.id,
        section_id=section.section_id,
        gender=section.gender,
        capacity=section.capacity,
        enrolled=section.enrolled,
        course_id=section.course_id,
        course_code=course.code if course else "",
        course_name=course.name if course else "",
    )


@router.get("/sections", response_model=List[SectionResponse])
def list_sections(course_id: int = None, gender: str = None, db: Session = Depends(get_db)):
    """
    List all active (non-archived) sections with optional filters.

    Query parameters:
      - course_id: Only return sections belonging to this course.
      - gender: Filter by gender designation (e.g., "Male" or "Female").
    """
    q = db.query(Section).filter(Section.is_archived == False)
    if course_id:
        q = q.filter(Section.course_id == course_id)
    if gender:
        q = q.filter(Section.gender == gender)
    sections = q.all()
    # Build the response list, fetching each section's parent course for its code/name
    result = []
    for s in sections:
        course = db.query(Course).filter(Course.id == s.course_id).first()
        result.append(SectionResponse(
            id=s.id,
            section_id=s.section_id,
            gender=s.gender,
            capacity=s.capacity,
            enrolled=s.enrolled,
            course_id=s.course_id,
            course_code=course.code if course else "",
            course_name=course.name if course else "",
        ))
    return result
