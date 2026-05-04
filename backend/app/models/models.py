from sqlalchemy import (
    Column, Integer, String, Boolean, Float, ForeignKey, Table, Text,
    UniqueConstraint, Enum as SAEnum
)
from sqlalchemy.orm import relationship
import enum
from app.database import Base


class UserRole(str, enum.Enum):
    STUDENT = "student"
    INSTRUCTOR = "instructor"
    ADMIN = "admin"


course_prerequisites = Table(
    "course_prerequisites",
    Base.metadata,
    Column("course_id", Integer, ForeignKey("courses.id"), primary_key=True),
    Column("prerequisite_id", Integer, ForeignKey("courses.id"), primary_key=True),
)

student_completed_courses = Table(
    "student_completed_courses",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("course_id", Integer, ForeignKey("courses.id"), primary_key=True),
)

student_registrations = Table(
    "student_registrations",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("section_id", Integer, ForeignKey("sections.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.STUDENT)
    gender = Column(String(10), default="Male")
    department = Column(String(100), default="")
    level = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)

    completed_courses = relationship("Course", secondary=student_completed_courses, backref="completed_by")
    registered_sections = relationship("Section", secondary=student_registrations, backref="registered_students")
    saved_schedules = relationship("SavedSchedule", back_populates="user")


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    code = Column(String(10), unique=True, nullable=False)

    courses = relationship("Course", back_populates="department")


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    level = Column(Integer, default=1)
    credits = Column(Integer, default=3)
    is_lab = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    department_id = Column(Integer, ForeignKey("departments.id"))

    department = relationship("Department", back_populates="courses")
    sections = relationship("Section", back_populates="course", cascade="all, delete-orphan")
    prerequisites = relationship(
        "Course",
        secondary=course_prerequisites,
        primaryjoin=id == course_prerequisites.c.course_id,
        secondaryjoin=id == course_prerequisites.c.prerequisite_id,
        backref="required_by",
    )


class Instructor(Base):
    __tablename__ = "instructors"

    id = Column(Integer, primary_key=True, index=True)
    instructor_id = Column(String(20), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    gender = Column(String(10), default="Male")
    department = Column(String(100), default="")
    rank = Column(String(50), default="")
    min_hours = Column(Integer, default=12)
    max_hours = Column(Integer, default=18)


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(String(20), unique=True, nullable=False)
    capacity = Column(Integer, default=40)
    gender = Column(String(10), default="")
    room_type = Column(String(50), default="Lecture Hall")
    floor = Column(Integer, default=1)
    building = Column(String(100), default="")
    equipment = Column(String(255), default="")


class TimeSlot(Base):
    __tablename__ = "time_slots"

    id = Column(Integer, primary_key=True, index=True)
    label = Column(String(20), unique=True, nullable=False)
    start_time = Column(String(10), nullable=False)
    end_time = Column(String(10), nullable=False)
    slot_type = Column(String(10), default="Class")
    slot_order = Column(Integer, default=0)


class Day(Base):
    __tablename__ = "days"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(5), unique=True, nullable=False)
    name = Column(String(20), default="")


class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, index=True)
    section_id = Column(String(20), unique=True, nullable=False)
    gender = Column(String(10), default="Male")
    capacity = Column(Integer, default=40)
    enrolled = Column(Integer, default=0)
    course_id = Column(Integer, ForeignKey("courses.id"))
    is_archived = Column(Boolean, default=False)

    course = relationship("Course", back_populates="sections")


class SavedSchedule(Base):
    __tablename__ = "saved_schedules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String(255), default="My Schedule")
    algorithm = Column(String(10), default="GA")
    objective = Column(String(20), default="student")
    fitness = Column(Float, default=0.0)
    conflicts = Column(Float, default=0.0)
    schedule_data = Column(Text, nullable=False)

    user = relationship("User", back_populates="saved_schedules")
