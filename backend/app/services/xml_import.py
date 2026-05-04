import xml.etree.ElementTree as ET
import os
from sqlalchemy.orm import Session
from app.models.models import (
    Department, Course, Section, Instructor, Room, Day, TimeSlot,
)


def import_university_xml(db: Session, xml_path: str):
    if not os.path.exists(xml_path):
        print(f"XML file not found: {xml_path}")
        return

    root = ET.parse(xml_path).getroot()

    _import_days_and_timeslots(db, root)
    _import_rooms(db, root)
    _import_instructors(db, root)
    dept_map = _import_courses_and_sections(db, root)

    db.commit()
    print("XML import complete.")


def _import_days_and_timeslots(db: Session, root):
    ts = root.find("TimeSlots")
    if ts is None:
        return

    for d_el in ts.find("WorkingDays").findall("Day"):
        code = d_el.get("code", d_el.text.strip()[:3].upper())
        name = d_el.text.strip() if d_el.text else code
        if not db.query(Day).filter(Day.code == code).first():
            db.add(Day(code=code, name=name))
    db.flush()

    slot_order = 0
    for p_el in ts.find("DailyPeriods").findall("Period"):
        start = p_el.find("StartTime").text.strip()
        end = p_el.find("EndTime").text.strip()
        label = f"{start}-{end}"
        slot_type = p_el.get("type", "Class")

        if not db.query(TimeSlot).filter(TimeSlot.label == label).first():
            db.add(TimeSlot(
                label=label,
                start_time=start,
                end_time=end,
                slot_type=slot_type,
                slot_order=slot_order,
            ))
        if slot_type == "Class":
            slot_order += 1
    db.flush()
    print(f"Days: {db.query(Day).count()}, TimeSlots: {db.query(TimeSlot).count()}")


def _import_rooms(db: Session, root):
    campus = root.find("Campus")
    if campus is None:
        return

    for bldg in campus.findall("Building"):
        gender = bldg.get("gender", "")
        bldg_name = bldg.get("name", "")
        rooms_el = bldg.find("Rooms")
        if rooms_el is None:
            continue
        for r_el in list(rooms_el.findall("Room")) + list(rooms_el.findall("Lab")):
            rid = r_el.get("id")
            if not db.query(Room).filter(Room.room_id == rid).first():
                db.add(Room(
                    room_id=rid,
                    capacity=int(r_el.get("capacity", 40)),
                    gender=gender,
                    room_type=r_el.get("type", "Lecture Hall"),
                    floor=int(r_el.get("floor", 1)),
                    building=bldg_name,
                    equipment=r_el.get("equipment", ""),
                ))
    db.flush()
    print(f"Rooms: {db.query(Room).count()}")


def _import_instructors(db: Session, root):
    faculty = root.find("Faculty")
    if faculty is None:
        return

    for group in faculty:
        for p_el in group.findall("Professor"):
            pid = p_el.get("id")
            if db.query(Instructor).filter(Instructor.instructor_id == pid).first():
                continue
            n_el = p_el.find("Name")
            name = n_el.text.strip() if n_el is not None else pid
            rank_el = p_el.find("Rank")
            min_h = p_el.find("MinTeachingHours")
            max_h = p_el.find("MaxTeachingHours")
            db.add(Instructor(
                instructor_id=pid,
                name=name,
                gender=p_el.get("gender", "Male"),
                department=p_el.get("department", ""),
                rank=rank_el.text.strip() if rank_el is not None else "",
                min_hours=int(min_h.text.strip()) if min_h is not None else 12,
                max_hours=int(max_h.text.strip()) if max_h is not None else 18,
            ))
    db.flush()
    print(f"Instructors: {db.query(Instructor).count()}")


def _import_courses_and_sections(db: Session, root):
    program = root.find("AcademicProgram")
    if program is None:
        return {}

    dept_map = {}
    for dept_el in program.findall("Department"):
        dept_name = dept_el.get("name", "Unknown")
        dept_code = dept_name[:2].upper() + "S" if "Systems" in dept_name else dept_name[:2].upper()
        if dept_name == "Computer Science":
            dept_code = "CS"
        elif dept_name == "Information Technology":
            dept_code = "IT"
        elif dept_name == "Information Systems":
            dept_code = "IS"

        dept = db.query(Department).filter(Department.name == dept_name).first()
        if not dept:
            dept = Department(name=dept_name, code=dept_code)
            db.add(dept)
            db.flush()
        dept_map[dept_name] = dept

        for course_el in dept_el.findall("Course"):
            cid = course_el.get("id")
            if db.query(Course).filter(Course.code == cid).first():
                continue

            n_el = course_el.find("Name")
            cname = n_el.text.strip() if n_el is not None else cid
            t_el = course_el.find("Type")
            is_lab = t_el is not None and "lab" in t_el.text.lower()

            course = Course(
                code=cid,
                name=cname,
                level=int(course_el.get("level", 1)),
                credits=int(course_el.get("credits", 3)),
                is_lab=is_lab,
                department_id=dept.id,
            )
            db.add(course)
            db.flush()

            secs_el = course_el.find("Sections")
            if secs_el is None:
                continue
            for sec_el in secs_el.findall("Section"):
                sid = sec_el.get("id")
                if db.query(Section).filter(Section.section_id == sid).first():
                    continue
                cap_el = sec_el.find("Capacity")
                capacity = int(cap_el.text.strip()) if cap_el is not None else 40
                db.add(Section(
                    section_id=sid,
                    gender=sec_el.get("gender", "Male"),
                    capacity=capacity,
                    enrolled=0,
                    course_id=course.id,
                ))
    db.flush()

    # Now handle prerequisites
    for dept_el in program.findall("Department"):
        for course_el in dept_el.findall("Course"):
            pre_el = course_el.find("Prerequisites")
            if pre_el is None or not pre_el.text or pre_el.text.strip().lower() == "none":
                continue
            cid = course_el.get("id")
            course = db.query(Course).filter(Course.code == cid).first()
            if not course:
                continue
            prereq_codes = [p.strip() for p in pre_el.text.strip().split(",")]
            for pc in prereq_codes:
                prereq = db.query(Course).filter(Course.code == pc).first()
                if prereq and prereq not in course.prerequisites:
                    course.prerequisites.append(prereq)
    db.flush()

    print(f"Departments: {db.query(Department).count()}")
    print(f"Courses: {db.query(Course).count()}")
    print(f"Sections: {db.query(Section).count()}")
    return dept_map
