from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.models import User, UserRole, Course, Section, student_registrations
from app.schemas import SectionResponse
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/registration", tags=["registration"])


@router.post("/register/{section_id}")
def register_for_section(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    course = db.query(Course).filter(Course.id == section.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if course.prerequisites and current_user.role == UserRole.STUDENT:
        completed_codes = {c.code for c in current_user.completed_courses}
        missing = [p.code for p in course.prerequisites if p.code not in completed_codes]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Prerequisites not met. You must complete: {', '.join(missing)}"
            )

    if section in current_user.registered_sections:
        raise HTTPException(status_code=400, detail="Already registered for this section")

    already_registered_course_ids = [s.course_id for s in current_user.registered_sections]
    if section.course_id in already_registered_course_ids:
        raise HTTPException(status_code=400, detail="Already registered for another section of this course")

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
    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    if section not in current_user.registered_sections:
        raise HTTPException(status_code=400, detail="Not registered for this section")

    current_user.registered_sections.remove(section)
    section.enrolled = len(section.registered_students)
    db.commit()
    return {"message": "Unregistered successfully"}


@router.get("/my-registrations")
def get_my_registrations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sections = current_user.registered_sections
    result = []
    for s in sections:
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
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

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
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if course not in current_user.completed_courses:
        raise HTTPException(status_code=400, detail="Course not marked as completed")

    current_user.completed_courses.remove(course)
    db.commit()
    return {"message": f"Removed {course.code} from completed"}
