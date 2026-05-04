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

router = APIRouter(prefix="/api", tags=["courses"])


def _course_to_response(course: Course) -> CourseResponse:
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
        prerequisites=[p.code for p in course.prerequisites],
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


@router.get("/departments", response_model=List[DepartmentResponse])
def list_departments(db: Session = Depends(get_db)):
    return db.query(Department).all()


@router.get("/instructors", response_model=List[InstructorResponse])
def list_instructors(db: Session = Depends(get_db)):
    return db.query(Instructor).all()


@router.get("/rooms", response_model=List[RoomResponse])
def list_rooms(db: Session = Depends(get_db)):
    return db.query(Room).all()


@router.get("/days", response_model=List[DayResponse])
def list_days(db: Session = Depends(get_db)):
    return db.query(Day).order_by(Day.id).all()


@router.get("/timeslots", response_model=List[TimeSlotResponse])
def list_timeslots(db: Session = Depends(get_db)):
    return db.query(TimeSlot).order_by(TimeSlot.slot_order).all()


@router.get("/courses", response_model=List[CourseResponse])
def list_courses(
    department_id: int = None,
    level: int = None,
    include_archived: bool = False,
    db: Session = Depends(get_db),
):
    q = db.query(Course).options(joinedload(Course.department), joinedload(Course.sections), joinedload(Course.prerequisites))
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
    if current_user.role not in (UserRole.INSTRUCTOR, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Only instructors can create courses")
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
    if current_user.role not in (UserRole.INSTRUCTOR, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Only instructors can update courses")
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

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
    if current_user.role not in (UserRole.INSTRUCTOR, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Only instructors can delete courses")
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    db.delete(course)
    db.commit()
    return {"message": "Course deleted"}


@router.post("/sections", response_model=SectionResponse)
def create_section(
    data: SectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    q = db.query(Section).filter(Section.is_archived == False)
    if course_id:
        q = q.filter(Section.course_id == course_id)
    if gender:
        q = q.filter(Section.gender == gender)
    sections = q.all()
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
