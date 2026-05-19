"""
Course Registration API Routes
===============================
This file defines the REST API endpoints that let students register for
course sections, unregister, and manage their completed-courses list.

Endpoints overview:
  - POST   /api/registration/register/{section_id}   - Register for a section.
  - DELETE /api/registration/unregister/{section_id}  - Drop a section.
  - GET    /api/registration/my-registrations         - View current registrations.
  - GET    /api/registration/completed                - View completed courses.
  - POST   /api/registration/complete/{course_id}     - Mark a course as completed.
  - DELETE /api/registration/uncomplete/{course_id}   - Remove a course from completed list.

Key business rule: A student cannot register for a course unless all of
its prerequisite courses have been marked as completed first.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.models import User, UserRole, Course, Section, student_registrations
from app.schemas import SectionResponse
from app.services.auth import get_current_user

# All registration endpoints live under the "/api/registration" prefix.
router = APIRouter(prefix="/api/registration", tags=["registration"])


@router.post("/register/{section_id}")
def register_for_section(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Register the current user for a specific course section.

    Validation steps:
      1. Verify the section exists.
      2. Verify the parent course exists.
      3. Check prerequisites: if the course has prerequisites and the user
         is a student, ensure all prerequisite courses are in their
         completed-courses list. (Instructors/admins skip this check.)
      4. Prevent duplicate registration for the same section.
      5. Prevent registering for two different sections of the same course.
      6. Add the registration and update the section's enrollment count.
    """
    # Step 1: Look up the section by its database ID
    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    # Step 2: Look up the course that this section belongs to
    course = db.query(Course).filter(Course.id == section.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Step 3: Prerequisite enforcement (only for students)
    if course.prerequisites and current_user.role == UserRole.STUDENT:
        # Build a set of course codes the student has already completed
        completed_codes = {c.code for c in current_user.completed_courses}
        # Find any prerequisites that are NOT in the completed set
        missing = [p.code for p in course.prerequisites if p.code not in completed_codes]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Prerequisites not met. You must complete: {', '.join(missing)}"
            )

    # Step 4: Check if the student is already registered for this exact section
    if section in current_user.registered_sections:
        raise HTTPException(status_code=400, detail="Already registered for this section")

    # Step 5: Check if the student is registered for a DIFFERENT section of the same course
    already_registered_course_ids = [s.course_id for s in current_user.registered_sections]
    if section.course_id in already_registered_course_ids:
        raise HTTPException(status_code=400, detail="Already registered for another section of this course")

    # Step 6: Add the registration and update enrollment count
    current_user.registered_sections.append(section)
    section.enrolled = len(section.registered_students)
    db.commit()
    return {"message": "Registered successfully", "section_id": section.section_id}


@router.delete("/unregister/{section_id}")
def unregister_from_section(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Remove the current user's registration from a section (drop the course).

    Steps:
      1. Verify the section exists.
      2. Verify the user is actually registered for it.
      3. Remove the registration and update the enrollment count.
    """
    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    # Ensure the student is actually registered before trying to remove
    if section not in current_user.registered_sections:
        raise HTTPException(status_code=400, detail="Not registered for this section")

    # Remove the many-to-many link and recalculate enrollment
    current_user.registered_sections.remove(section)
    section.enrolled = len(section.registered_students)
    db.commit()
    return {"message": "Unregistered successfully"}


@router.get("/my-registrations")
def get_my_registrations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return all sections the current user is registered for.

    Each result includes section details along with the parent course's
    code and name for display purposes.
    """
    sections = current_user.registered_sections
    result = []
    for s in sections:
        # Fetch parent course to get its code and name
        course = db.query(Course).filter(Course.id == s.course_id).first()
        result.append({
            "id": s.id,
            "section_id": s.section_id,
            "gender": s.gender,
            "capacity": s.capacity,
            "enrolled": s.enrolled,
            "course_id": s.course_id,
            "course_code": course.code if course else "",
            "course_name": course.name if course else "",
        })
    return result


@router.get("/completed")
def get_completed_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return all courses the current user has marked as completed.

    This list is used by the prerequisite check: when a student tries to
    register for a course, the system verifies that all prerequisites
    appear in their completed-courses list.
    """
    return [
        {"id": c.id, "code": c.code, "name": c.name, "level": c.level, "credits": c.credits}
        for c in current_user.completed_courses
    ]


@router.post("/complete/{course_id}")
def mark_course_completed(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark a course as completed for the current user.

    This is typically used by students to indicate they have already passed
    a course in a previous semester, which then satisfies prerequisite
    requirements for advanced courses.
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Prevent marking the same course as completed twice
    if course in current_user.completed_courses:
        raise HTTPException(status_code=400, detail="Course already marked as completed")

    current_user.completed_courses.append(course)
    db.commit()
    return {"message": f"Marked {course.code} as completed"}


@router.delete("/uncomplete/{course_id}")
def unmark_course_completed(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Remove a course from the current user's completed list.

    This reverses a previous mark_course_completed call. Note that if the
    user is currently registered for courses that require this as a
    prerequisite, those registrations are NOT automatically removed.
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if course not in current_user.completed_courses:
        raise HTTPException(status_code=400, detail="Course not marked as completed")

    current_user.completed_courses.remove(course)
    db.commit()
    return {"message": f"Removed {course.code} from completed"}
