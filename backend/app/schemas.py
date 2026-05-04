from pydantic import BaseModel
from typing import Optional, List


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: str
    role: str = "student"
    gender: str = "Male"
    department: str = ""
    level: int = 1


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role: str
    gender: str
    department: str
    level: int

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class CourseCreate(BaseModel):
    code: str
    name: str
    level: int = 1
    credits: int = 3
    is_lab: bool = False
    department_id: int
    prerequisite_codes: List[str] = []


class CourseUpdate(BaseModel):
    name: Optional[str] = None
    level: Optional[int] = None
    credits: Optional[int] = None
    is_lab: Optional[bool] = None
    is_archived: Optional[bool] = None
    prerequisite_codes: Optional[List[str]] = None


class CourseResponse(BaseModel):
    id: int
    code: str
    name: str
    level: int
    credits: int
    is_lab: bool
    is_archived: bool
    department_id: int
    department_name: str = ""
    prerequisites: List[str] = []
    sections: List[dict] = []

    class Config:
        from_attributes = True


class SectionCreate(BaseModel):
    section_id: str
    gender: str = "Male"
    capacity: int = 40
    course_id: int


class SectionResponse(BaseModel):
    id: int
    section_id: str
    gender: str
    capacity: int
    enrolled: int
    course_id: int
    course_code: str = ""
    course_name: str = ""
    is_archived: bool = False

    class Config:
        from_attributes = True


class ScheduleGenerateRequest(BaseModel):
    selected_course_ids: List[int] = []
    algorithm: str = "GA"
    objective: str = "student"
    preferred_gender: Optional[str] = None


class ScheduleSlot(BaseModel):
    course_code: str
    course_name: str
    section_id: str
    department: str
    instructor_name: str
    room: str
    day: str
    time: str
    credits: int
    level: int
    gender: str


class ScheduleResult(BaseModel):
    rank: int
    label: str
    description: str
    fitness: float
    conflicts: float
    objective: str
    slots: List[ScheduleSlot]


class SaveScheduleRequest(BaseModel):
    name: str = "My Schedule"
    algorithm: str = "GA"
    objective: str = "student"
    fitness: float = 0.0
    conflicts: float = 0.0
    schedule_data: str


class DepartmentResponse(BaseModel):
    id: int
    name: str
    code: str

    class Config:
        from_attributes = True


class InstructorResponse(BaseModel):
    id: int
    instructor_id: str
    name: str
    gender: str
    department: str
    rank: str
    min_hours: int
    max_hours: int

    class Config:
        from_attributes = True


class RoomResponse(BaseModel):
    id: int
    room_id: str
    capacity: int
    gender: str
    room_type: str
    floor: int
    building: str

    class Config:
        from_attributes = True


class DayResponse(BaseModel):
    id: int
    code: str
    name: str

    class Config:
        from_attributes = True


class TimeSlotResponse(BaseModel):
    id: int
    label: str
    start_time: str
    end_time: str
    slot_type: str
    slot_order: int

    class Config:
        from_attributes = True
