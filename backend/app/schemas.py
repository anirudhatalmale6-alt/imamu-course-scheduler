"""
schemas.py - Pydantic Request/Response Schemas (Data Transfer Objects)

This file defines Pydantic models that validate and serialize data flowing
in and out of the API. They serve three purposes:

  1. **Request validation** - Pydantic automatically checks that incoming JSON
     payloads have the right fields and types. If validation fails, FastAPI
     returns a 422 error with details.
  2. **Response serialization** - Pydantic converts SQLAlchemy model instances
     into JSON-safe dictionaries, controlling exactly which fields are exposed.
  3. **Documentation** - FastAPI uses these schemas to generate interactive
     Swagger/OpenAPI docs at /docs.

Naming convention:
  - *Create  : Used for POST requests (creating a new resource).
  - *Update  : Used for PUT/PATCH requests (partial updates).
  - *Response: Used for API responses (what the client receives).
  - *Request : Used for complex POST bodies that aren't simple CRUD.
"""

from pydantic import BaseModel
from typing import Optional, List


# ===========================================================================
# User Schemas
# ===========================================================================

class UserCreate(BaseModel):
    """
    Schema for registering a new user account.
    The password is sent in plain text over HTTPS and hashed server-side.
    """
    username: str
    email: str
    password: str               # Plain-text password (will be hashed before storage)
    full_name: str
    role: str = "student"       # Default role; can also be "instructor" or "admin"
    gender: str = "Male"
    department: str = ""
    level: int = 1              # Academic year / level


class UserLogin(BaseModel):
    """Schema for the login endpoint. Only username and password are needed."""
    username: str
    password: str


class UserResponse(BaseModel):
    """
    Schema returned when the API sends user information back to the client.
    Note: the hashed_password is intentionally excluded for security.
    """
    id: int
    username: str
    email: str
    full_name: str
    role: str
    gender: str
    department: str
    level: int

    class Config:
        from_attributes = True  # Allow creating this schema from a SQLAlchemy model instance


class TokenResponse(BaseModel):
    """
    Schema returned after a successful login. Contains the JWT access token
    and the authenticated user's profile.
    """
    access_token: str
    token_type: str = "bearer"  # OAuth2 convention
    user: UserResponse          # Nested user profile so the frontend can store it


# ===========================================================================
# Course Schemas
# ===========================================================================

class CourseCreate(BaseModel):
    """Schema for creating a new course. Prerequisite courses are specified by code."""
    code: str                                   # Unique course code, e.g. "CS101"
    name: str                                   # Course title
    level: int = 1                              # Target academic level
    credits: int = 3                            # Credit hours
    is_lab: bool = False                        # Whether this is a laboratory course
    department_id: int                          # FK: which department offers this course
    prerequisite_codes: List[str] = []          # List of course codes that are prerequisites


class CourseUpdate(BaseModel):
    """
    Schema for updating an existing course. All fields are optional -
    only the provided fields will be updated (partial update pattern).
    """
    name: Optional[str] = None
    level: Optional[int] = None
    credits: Optional[int] = None
    is_lab: Optional[bool] = None
    is_archived: Optional[bool] = None
    prerequisite_codes: Optional[List[str]] = None


class CourseResponse(BaseModel):
    """
    Schema for returning course data to the client. Includes computed fields
    like department_name, prerequisite codes, and nested section info.
    """
    id: int
    code: str
    name: str
    level: int
    credits: int
    is_lab: bool
    is_archived: bool
    department_id: int
    department_name: str = ""           # Resolved from the related Department record
    prerequisites: List[str] = []       # List of prerequisite course codes
    sections: List[dict] = []           # List of section summaries (dicts)

    class Config:
        from_attributes = True


# ===========================================================================
# Section Schemas
# ===========================================================================

class SectionCreate(BaseModel):
    """Schema for creating a new section of a course."""
    section_id: str             # Unique section identifier, e.g. "CS101-M1"
    gender: str = "Male"        # Gender restriction for this section
    capacity: int = 40          # Maximum number of students
    course_id: int              # FK: the course this section belongs to


class SectionResponse(BaseModel):
    """Schema for returning section data, enriched with parent course info."""
    id: int
    section_id: str
    gender: str
    capacity: int
    enrolled: int               # Current number of registered students
    course_id: int
    course_code: str = ""       # Resolved from the parent Course record
    course_name: str = ""       # Resolved from the parent Course record
    is_archived: bool = False

    class Config:
        from_attributes = True


# ===========================================================================
# Schedule Generation Schemas
# ===========================================================================

class ScheduleGenerateRequest(BaseModel):
    """
    Schema for requesting the scheduling algorithm to generate timetables.

    Fields:
      - selected_course_ids : Which courses the student wants to take.
      - algorithm           : Scheduling algorithm to use ("GA" = Genetic Algorithm).
      - objective           : What to optimize for ("student" = minimize gaps, etc.).
      - preferred_gender    : Optional gender filter for section selection.
    """
    selected_course_ids: List[int] = []
    algorithm: str = "GA"
    objective: str = "student"
    preferred_gender: Optional[str] = None


class ScheduleSlot(BaseModel):
    """
    Represents one class session in a generated schedule (one cell in the
    timetable grid). Contains all the information needed to display the slot.
    """
    course_code: str            # e.g. "CS101"
    course_name: str            # e.g. "Intro to Programming"
    section_id: str             # e.g. "CS101-M1"
    department: str             # Department offering the course
    instructor_name: str        # Name of the assigned instructor
    room: str                   # Room number/code
    day: str                    # Day of the week (e.g. "SUN")
    time: str                   # Time slot label (e.g. "P1")
    credits: int                # Course credit hours
    level: int                  # Course level
    gender: str                 # Section gender


class ScheduleResult(BaseModel):
    """
    A complete generated schedule option returned by the algorithm.
    The algorithm typically returns multiple ranked options for the user
    to choose from.
    """
    rank: int                   # Ranking among generated options (1 = best)
    label: str                  # Display label (e.g. "Option A")
    description: str            # Brief description of this schedule's characteristics
    fitness: float              # Quality score from the algorithm (higher = better)
    conflicts: float            # Number or score of detected conflicts
    objective: str              # The optimization objective used
    slots: List[ScheduleSlot]   # All class sessions in this schedule


class SaveScheduleRequest(BaseModel):
    """Schema for saving a generated schedule to the user's account."""
    name: str = "My Schedule"       # User-chosen name for the schedule
    algorithm: str = "GA"           # Which algorithm produced it
    objective: str = "student"      # Which objective was optimized
    fitness: float = 0.0            # Fitness score to store
    conflicts: float = 0.0         # Conflict score to store
    schedule_data: str              # Full schedule as a JSON string


# ===========================================================================
# Reference Data Schemas (read-only lookups)
# ===========================================================================

class DepartmentResponse(BaseModel):
    """Schema for returning department data."""
    id: int
    name: str       # Full department name
    code: str       # Short department code

    class Config:
        from_attributes = True


class InstructorResponse(BaseModel):
    """Schema for returning instructor data."""
    id: int
    instructor_id: str      # University staff ID
    name: str
    gender: str
    department: str
    rank: str               # Academic rank
    min_hours: int          # Minimum weekly teaching hours
    max_hours: int          # Maximum weekly teaching hours

    class Config:
        from_attributes = True


class RoomResponse(BaseModel):
    """Schema for returning room/classroom data."""
    id: int
    room_id: str            # Room number/code
    capacity: int
    gender: str             # Gender restriction, if any
    room_type: str          # "Lecture Hall", "Lab", etc.
    floor: int
    building: str

    class Config:
        from_attributes = True


class DayResponse(BaseModel):
    """Schema for returning day-of-week data."""
    id: int
    code: str       # Short code (e.g. "SUN")
    name: str       # Full name (e.g. "Sunday")

    class Config:
        from_attributes = True


class TimeSlotResponse(BaseModel):
    """Schema for returning time slot data."""
    id: int
    label: str          # Display label (e.g. "P1")
    start_time: str     # e.g. "08:00"
    end_time: str       # e.g. "09:00"
    slot_type: str      # "Class" or "Break"
    slot_order: int     # Chronological sort order

    class Config:
        from_attributes = True
