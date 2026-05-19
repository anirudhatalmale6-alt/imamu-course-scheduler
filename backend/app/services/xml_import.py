"""
XML Data Import Service
=======================
This module imports university data from an XML file into the database.
It is typically run once during initial setup to populate the system with
the university's academic structure.

The XML file contains:
  - TimeSlots: Working days (e.g., Sunday-Thursday) and daily periods
    (e.g., 08:00-09:00, 09:00-10:00).
  - Campus: Buildings and their rooms/labs with capacity and gender info.
  - Faculty: Instructor profiles grouped by department, including rank
    and teaching-hour limits.
  - AcademicProgram: Departments, courses with prerequisites, and sections
    with gender designation and capacity.

The import is idempotent: if a record already exists (checked by its
unique identifier like room_id or course code), it is skipped rather
than duplicated.
"""

import xml.etree.ElementTree as ET
import os
from sqlalchemy.orm import Session
from app.models.models import (
    Department, Course, Section, Instructor, Room, Day, TimeSlot,
)


def import_university_xml(db: Session, xml_path: str):
    """
    Main entry point: parse the XML file and import all data into the database.

    Calls sub-functions in the correct order to respect foreign-key
    dependencies (e.g., departments must exist before courses that
    reference them).

    Args:
        db: SQLAlchemy database session.
        xml_path: Absolute path to the university XML data file.
    """
    if not os.path.exists(xml_path):
        print(f"XML file not found: {xml_path}")
        return

    # Parse the XML file into an ElementTree and get the root element
    root = ET.parse(xml_path).getroot()

    # Import in dependency order: reference data first, then courses/sections
    _import_days_and_timeslots(db, root)
    _import_rooms(db, root)
    _import_instructors(db, root)
    dept_map = _import_courses_and_sections(db, root)

    db.commit()  # Final commit to persist all changes
    print("XML import complete.")


def _import_days_and_timeslots(db: Session, root):
    """
    Import working days and daily time periods from the <TimeSlots> element.

    Working days example: Sunday, Monday, Tuesday, Wednesday, Thursday.
    Daily periods example: 08:00-09:00 (Class), 12:00-13:00 (Break).

    Each day gets a short code (e.g., "SUN") and each period gets an
    ordering number (slot_order) so they display in chronological order.
    Only "Class" type periods increment the slot_order counter; break
    periods do not.
    """
    ts = root.find("TimeSlots")
    if ts is None:
        return

    # Import each working day (e.g., Sunday -> code "SUN")
    for d_el in ts.find("WorkingDays").findall("Day"):
        code = d_el.get("code", d_el.text.strip()[:3].upper())  # Use XML attribute or first 3 chars
        name = d_el.text.strip() if d_el.text else code
        # Skip if this day code already exists in the database
        if not db.query(Day).filter(Day.code == code).first():
            db.add(Day(code=code, name=name))
    db.flush()  # Flush to assign IDs without committing the transaction

    # Import each daily period (time slot)
    slot_order = 0  # Counter for ordering class periods chronologically
    for p_el in ts.find("DailyPeriods").findall("Period"):
        start = p_el.find("StartTime").text.strip()
        end = p_el.find("EndTime").text.strip()
        label = f"{start}-{end}"  # e.g., "08:00-09:00"
        slot_type = p_el.get("type", "Class")  # "Class" or "Break"

        # Skip if this time slot label already exists
        if not db.query(TimeSlot).filter(TimeSlot.label == label).first():
            db.add(TimeSlot(
                label=label,
                start_time=start,
                end_time=end,
                slot_type=slot_type,
                slot_order=slot_order,
            ))
        # Only increment ordering for actual class periods, not breaks
        if slot_type == "Class":
            slot_order += 1
    db.flush()
    print(f"Days: {db.query(Day).count()}, TimeSlots: {db.query(TimeSlot).count()}")


def _import_rooms(db: Session, root):
    """
    Import rooms and labs from the <Campus> element.

    The XML structure groups rooms inside buildings, and each building
    has a gender designation (for gender-segregated campuses). Both
    <Room> and <Lab> elements are processed identically.
    """
    campus = root.find("Campus")
    if campus is None:
        return

    for bldg in campus.findall("Building"):
        gender = bldg.get("gender", "")       # Building-level gender (e.g., "Male", "Female")
        bldg_name = bldg.get("name", "")      # Building name for reference
        rooms_el = bldg.find("Rooms")
        if rooms_el is None:
            continue
        # Process both <Room> and <Lab> elements in the same way
        for r_el in list(rooms_el.findall("Room")) + list(rooms_el.findall("Lab")):
            rid = r_el.get("id")
            # Skip if this room ID already exists in the database
            if not db.query(Room).filter(Room.room_id == rid).first():
                db.add(Room(
                    room_id=rid,
                    capacity=int(r_el.get("capacity", 40)),  # Default capacity: 40
                    gender=gender,
                    room_type=r_el.get("type", "Lecture Hall"),
                    floor=int(r_el.get("floor", 1)),
                    building=bldg_name,
                    equipment=r_el.get("equipment", ""),
                ))
    db.flush()
    print(f"Rooms: {db.query(Room).count()}")


def _import_instructors(db: Session, root):
    """
    Import instructor/professor records from the <Faculty> element.

    The XML groups professors inside faculty groups (e.g., by department).
    Each professor has attributes like gender, department, rank, and
    minimum/maximum teaching hours per week.
    """
    faculty = root.find("Faculty")
    if faculty is None:
        return

    # Iterate through faculty groups (e.g., CS faculty, IT faculty)
    for group in faculty:
        for p_el in group.findall("Professor"):
            pid = p_el.get("id")
            # Skip if this instructor already exists
            if db.query(Instructor).filter(Instructor.instructor_id == pid).first():
                continue
            # Extract the professor's name from the <Name> sub-element
            n_el = p_el.find("Name")
            name = n_el.text.strip() if n_el is not None else pid
            # Extract optional fields with sensible defaults
            rank_el = p_el.find("Rank")
            min_h = p_el.find("MinTeachingHours")
            max_h = p_el.find("MaxTeachingHours")
            db.add(Instructor(
                instructor_id=pid,
                name=name,
                gender=p_el.get("gender", "Male"),
                department=p_el.get("department", ""),
                rank=rank_el.text.strip() if rank_el is not None else "",
                min_hours=int(min_h.text.strip()) if min_h is not None else 12,  # Default: 12 hrs/week
                max_hours=int(max_h.text.strip()) if max_h is not None else 18,  # Default: 18 hrs/week
            ))
    db.flush()
    print(f"Instructors: {db.query(Instructor).count()}")


def _import_courses_and_sections(db: Session, root):
    """
    Import departments, courses, sections, and prerequisite relationships
    from the <AcademicProgram> element.

    This is the most complex import function because it handles:
      1. Creating Department records with auto-generated short codes.
      2. Creating Course records linked to their department.
      3. Creating Section records (class groups) linked to their course.
      4. Linking prerequisite relationships between courses (second pass).

    The prerequisite linking is done in a SECOND PASS after all courses
    have been created, because a course's prerequisite might be defined
    later in the XML file.

    Args:
        db: SQLAlchemy database session.
        root: The XML root element.

    Returns:
        A dictionary mapping department names to Department ORM objects.
    """
    program = root.find("AcademicProgram")
    if program is None:
        return {}

    dept_map = {}  # Maps department name -> Department ORM object

    # ── First Pass: Create departments, courses, and sections ──────────
    for dept_el in program.findall("Department"):
        dept_name = dept_el.get("name", "Unknown")

        # Generate a short department code from the name
        # Special cases for known department names; fallback uses first 2 chars
        dept_code = dept_name[:2].upper() + "S" if "Systems" in dept_name else dept_name[:2].upper()
        if dept_name == "Computer Science":
            dept_code = "CS"
        elif dept_name == "Information Technology":
            dept_code = "IT"
        elif dept_name == "Information Systems":
            dept_code = "IS"

        # Create the department if it does not already exist
        dept = db.query(Department).filter(Department.name == dept_name).first()
        if not dept:
            dept = Department(name=dept_name, code=dept_code)
            db.add(dept)
            db.flush()  # Flush to get the department's auto-generated ID
        dept_map[dept_name] = dept

        # Import each course within this department
        for course_el in dept_el.findall("Course"):
            cid = course_el.get("id")  # Course code, e.g., "CS101"
            # Skip if this course code already exists
            if db.query(Course).filter(Course.code == cid).first():
                continue

            # Extract course name and determine if it is a lab course
            n_el = course_el.find("Name")
            cname = n_el.text.strip() if n_el is not None else cid
            t_el = course_el.find("Type")
            is_lab = t_el is not None and "lab" in t_el.text.lower()

            course = Course(
                code=cid,
                name=cname,
                level=int(course_el.get("level", 1)),     # Academic level/semester
                credits=int(course_el.get("credits", 3)),  # Credit hours
                is_lab=is_lab,
                department_id=dept.id,
            )
            db.add(course)
            db.flush()  # Flush to get the course's auto-generated ID for sections

            # Import sections (class groups) for this course
            secs_el = course_el.find("Sections")
            if secs_el is None:
                continue
            for sec_el in secs_el.findall("Section"):
                sid = sec_el.get("id")
                # Skip if this section ID already exists
                if db.query(Section).filter(Section.section_id == sid).first():
                    continue
                cap_el = sec_el.find("Capacity")
                capacity = int(cap_el.text.strip()) if cap_el is not None else 40
                db.add(Section(
                    section_id=sid,
                    gender=sec_el.get("gender", "Male"),
                    capacity=capacity,
                    enrolled=0,  # No students enrolled initially
                    course_id=course.id,
                ))
    db.flush()

    # ── Second Pass: Link prerequisite relationships between courses ───
    # This must happen after ALL courses are created, because a course
    # might list a prerequisite that appears later in the XML.
    for dept_el in program.findall("Department"):
        for course_el in dept_el.findall("Course"):
            pre_el = course_el.find("Prerequisites")
            # Skip if no prerequisites or if the text is "None"
            if pre_el is None or not pre_el.text or pre_el.text.strip().lower() == "none":
                continue
            cid = course_el.get("id")
            course = db.query(Course).filter(Course.code == cid).first()
            if not course:
                continue
            # Parse comma-separated prerequisite codes (e.g., "CS101,CS102")
            prereq_codes = [p.strip() for p in pre_el.text.strip().split(",")]
            for pc in prereq_codes:
                prereq = db.query(Course).filter(Course.code == pc).first()
                # Link the prerequisite if it exists and is not already linked
                if prereq and prereq not in course.prerequisites:
                    course.prerequisites.append(prereq)
    db.flush()

    # Print summary statistics for verification
    print(f"Departments: {db.query(Department).count()}")
    print(f"Courses: {db.query(Course).count()}")
    print(f"Sections: {db.query(Section).count()}")
    return dept_map
