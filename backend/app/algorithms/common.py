import random
import re


HARD = 1.0
SOFT = 0.1


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_gender(value):
    if value is None:
        return ""

    value = str(value).strip().lower()

    if value in ["m", "male", "boys", "men"]:
        return "Male"

    if value in ["f", "female", "girls", "women"]:
        return "Female"

    return str(value).strip()


def gender_matches(a, b):
    return normalize_gender(a) == normalize_gender(b)


def period_number(period_id):
    numbers = re.findall(r"\d+", str(period_id))

    if not numbers:
        return 0

    return int(numbers[0])


def get_class_periods(data):
    class_periods = []

    for period in data["periods"]:
        period_type = str(period.get("type", "Class")).lower()
        period_id = str(period.get("id", "")).lower()

        if "prayer" in period_type or "break" in period_type:
            continue

        if "prayer" in period_id or "break" in period_id:
            continue

        class_periods.append(period)

    return class_periods


def parse_prerequisites(prerequisite_text):
    if prerequisite_text is None:
        return []

    text = str(prerequisite_text).strip()

    if text == "":
        return []

    if text.lower() in ["none", "no", "null", "n/a", "-"]:
        return []

    parts = re.split(r"[,\s;/]+", text)

    prerequisites = []

    for part in parts:
        clean_part = part.strip()

        if clean_part:
            prerequisites.append(clean_part)

    return prerequisites


def build_course_lookup(data):
    lookup = {}

    for course in data["courses"]:
        lookup[course["id"]] = course

    return lookup


def build_room_lookup(data):
    lookup = {}

    for room in data["rooms"]:
        lookup[room["id"]] = room

    return lookup


def build_professor_lookup(data):
    lookup = {}

    for professor in data["professors"]:
        lookup[professor["id"]] = professor

    return lookup


def get_available_rooms(data, gender, required_capacity=None):
    rooms = []

    for room in data["rooms"]:
        if not gender_matches(room.get("gender"), gender):
            continue

        if required_capacity is not None:
            if safe_int(room.get("capacity")) < safe_int(required_capacity):
                continue

        rooms.append(room)

    if not rooms:
        for room in data["rooms"]:
            if gender_matches(room.get("gender"), gender):
                rooms.append(room)

    return rooms


def get_available_professors(data, gender, department=None):
    professors = []

    for professor in data["professors"]:
        if not gender_matches(professor.get("gender"), gender):
            continue

        if department is not None:
            professor_department = str(professor.get("department", "")).strip()
            if professor_department and professor_department != department:
                continue

        professors.append(professor)

    if not professors:
        for professor in data["professors"]:
            if gender_matches(professor.get("gender"), gender):
                professors.append(professor)

    return professors


def make_cohort_key(course, section, gender):
    department = course.get("department", "UnknownDepartment")
    level = course.get("level", "UnknownLevel")
    section_id = section.get("id", "")

    section_group = "G"

    if "-" in section_id:
        section_group = section_id.split("-")[-1]

    return f"{normalize_gender(gender)}-{department}-L{level}-{section_group}"


def get_selected_course_sections(selected_courses, data, gender):
    selected_set = set(selected_courses)
    selected_sections = []

    for course in data["courses"]:
        course_selected = course["id"] in selected_set

        matching_sections = []

        for section in course["sections"]:
            section_selected = section["id"] in selected_set

            if not course_selected and not section_selected:
                continue

            if not gender_matches(section.get("gender"), gender):
                continue

            matching_sections.append(section)

        if course_selected and matching_sections:
            section = matching_sections[0]

            selected_sections.append({
                "course_id": course["id"],
                "course_name": course["name"],
                "department": course.get("department", ""),
                "level": course.get("level", ""),
                "credits": safe_int(course.get("credits")),
                "course_type": course.get("type", ""),
                "prerequisites": parse_prerequisites(course.get("prerequisites")),
                "section_id": section["id"],
                "section_gender": normalize_gender(section.get("gender")),
                "section_capacity": safe_int(section.get("capacity")),
                "waitlist": safe_int(section.get("waitlist")),
                "cohort_key": make_cohort_key(course, section, gender)
            })

        elif not course_selected:
            for section in matching_sections:
                selected_sections.append({
                    "course_id": course["id"],
                    "course_name": course["name"],
                    "department": course.get("department", ""),
                    "level": course.get("level", ""),
                    "credits": safe_int(course.get("credits")),
                    "course_type": course.get("type", ""),
                    "prerequisites": parse_prerequisites(course.get("prerequisites")),
                    "section_id": section["id"],
                    "section_gender": normalize_gender(section.get("gender")),
                    "section_capacity": safe_int(section.get("capacity")),
                    "waitlist": safe_int(section.get("waitlist")),
                    "cohort_key": make_cohort_key(course, section, gender)
                })

    return selected_sections


def create_assignment(section, data, gender):
    rooms = get_available_rooms(
        data,
        gender,
        required_capacity=section["section_capacity"]
    )

    professors = get_available_professors(
        data,
        gender,
        department=section["department"]
    )

    days = data["days"]
    periods = get_class_periods(data)

    if not rooms or not professors or not days or not periods:
        return None

    room = random.choice(rooms)
    professor = random.choice(professors)
    day = random.choice(days)
    period = random.choice(periods)

    return {
        "course_id": section["course_id"],
        "course_name": section["course_name"],
        "department": section["department"],
        "level": section["level"],
        "credits": section["credits"],
        "course_type": section["course_type"],
        "prerequisites": section["prerequisites"],
        "section_id": section["section_id"],
        "section_gender": section["section_gender"],
        "section_capacity": section["section_capacity"],
        "waitlist": section["waitlist"],
        "cohort_key": section["cohort_key"],

        "day": day,
        "period": period["id"],
        "period_number": period_number(period["id"]),
        "time": period["start"] + " - " + period["end"],

        "room": room["id"],
        "room_capacity": safe_int(room.get("capacity")),
        "room_gender": normalize_gender(room.get("gender")),
        "room_type": room.get("type", ""),

        "professor": professor["name"],
        "professor_id": professor["id"],
        "professor_gender": normalize_gender(professor.get("gender")),
        "professor_department": professor.get("department", ""),
        "professor_min_hours": safe_int(professor.get("min_hours")),
        "professor_max_hours": safe_int(professor.get("max_hours"))
    }


def create_random_position(selected_courses, data, gender):
    sections = get_selected_course_sections(selected_courses, data, gender)
    position = []

    for section in sections:
        num_slots = max(section["credits"], 1)

        for _ in range(num_slots):
            assignment = create_assignment(section, data, gender)

            if assignment is not None:
                position.append(assignment)

    position = repair_schedule(position, data, gender)

    return position


def copy_position(position):
    return [item.copy() for item in position]


def same_time(first, second):
    return (
        first["day"] == second["day"]
        and first["period"] == second["period"]
    )


def get_conflicting_indices(schedule):
    conflicting_indices = set()

    for i in range(len(schedule)):
        for j in range(i + 1, len(schedule)):
            first = schedule[i]
            second = schedule[j]

            if not same_time(first, second):
                continue

            if first["professor_id"] == second["professor_id"]:
                conflicting_indices.add(i)
                conflicting_indices.add(j)

            if first["room"] == second["room"]:
                conflicting_indices.add(i)
                conflicting_indices.add(j)

            if first["cohort_key"] == second["cohort_key"]:
                conflicting_indices.add(i)
                conflicting_indices.add(j)

            first_prerequisites = set(first.get("prerequisites", []))
            second_prerequisites = set(second.get("prerequisites", []))

            if second["course_id"] in first_prerequisites:
                conflicting_indices.add(i)
                conflicting_indices.add(j)

            if first["course_id"] in second_prerequisites:
                conflicting_indices.add(i)
                conflicting_indices.add(j)

    for i, item in enumerate(schedule):
        if item["room_capacity"] < item["section_capacity"]:
            conflicting_indices.add(i)

        if not gender_matches(item["section_gender"], item["room_gender"]):
            conflicting_indices.add(i)

        if not gender_matches(item["section_gender"], item["professor_gender"]):
            conflicting_indices.add(i)

    return conflicting_indices


def randomize_assignment(current_item, data, gender):
    section = {
        "course_id": current_item["course_id"],
        "course_name": current_item["course_name"],
        "department": current_item["department"],
        "level": current_item["level"],
        "credits": current_item["credits"],
        "course_type": current_item["course_type"],
        "prerequisites": current_item["prerequisites"],
        "section_id": current_item["section_id"],
        "section_gender": current_item["section_gender"],
        "section_capacity": current_item["section_capacity"],
        "waitlist": current_item["waitlist"],
        "cohort_key": current_item["cohort_key"]
    }

    new_assignment = create_assignment(section, data, gender)

    if new_assignment is None:
        return current_item

    return new_assignment


def repair_schedule(schedule, data, gender, max_attempts=80):
    repaired = copy_position(schedule)

    for _ in range(max_attempts):
        conflicting_indices = get_conflicting_indices(repaired)

        if not conflicting_indices:
            break

        index = random.choice(list(conflicting_indices))
        repaired[index] = randomize_assignment(repaired[index], data, gender)

    return repaired


def calculate_fitness(schedule, objective="student", data=None):
    """Fitness matching GA_runner.py calculate_fitness_multi exactly."""
    conflicts = 0.0

    instructor_days_map = {}
    instructor_slots_map = {}
    instructor_hours = {}
    room_usage = {}
    student_days_map = {}

    for item in schedule:
        iid = item["professor_id"]
        rid = item["room"]
        level = item["level"]
        sgender = item["section_gender"]
        day = item["day"]
        slot_idx = item["period_number"]
        credits = max(item["credits"], 1)

        instructor_hours[iid] = instructor_hours.get(iid, 0) + credits
        room_usage[rid] = room_usage.get(rid, 0) + 1
        instructor_days_map.setdefault(iid, set()).add(day)
        instructor_slots_map.setdefault(iid, []).append((day, slot_idx))
        student_days_map.setdefault((level, sgender), set()).add(day)

    if data:
        class_periods = get_class_periods(data)
        all_pnums = [period_number(p["id"]) for p in class_periods]
        last_slot = max(all_pnums) if all_pnums else 99
    else:
        all_slots = [item["period_number"] for item in schedule]
        last_slot = max(all_slots) if all_slots else 99

    course_schedule_map = {}
    for item in schedule:
        cid = item["course_id"]
        key = (item["day"], item["period"])
        course_schedule_map.setdefault(cid, []).append(key)

    hv = {
        "instructor_double_booking": 0,
        "room_double_booking": 0,
        "student_group_conflict": 0,
        "capacity_issues": 0,
        "prayer_time_violations": 0,
        "gender_separation_violations": 0,
        "prerequisite_overlap": 0,
    }

    for i in range(len(schedule)):
        ci = schedule[i]

        if ci["room_capacity"] < ci["section_capacity"]:
            conflicts += HARD
            hv["capacity_issues"] += 1

        period_text = str(ci.get("period", "")).lower()
        time_text = str(ci.get("time", "")).lower()
        if "prayer" in period_text or "prayer" in time_text:
            conflicts += HARD
            hv["prayer_time_violations"] += 1

        if not gender_matches(ci["section_gender"], ci["room_gender"]):
            conflicts += HARD
            hv["gender_separation_violations"] += 1

        prereqs = ci.get("prerequisites", [])
        if prereqs:
            my_key = (ci["day"], ci["period"])
            for prereq_id in prereqs:
                if prereq_id in course_schedule_map:
                    if my_key in course_schedule_map[prereq_id]:
                        conflicts += HARD
                        hv["prerequisite_overlap"] += 1

        for j in range(i + 1, len(schedule)):
            cj = schedule[j]
            if not same_time(ci, cj):
                continue

            if ci["professor_id"] == cj["professor_id"]:
                conflicts += HARD
                hv["instructor_double_booking"] += 1

            if ci["room"] == cj["room"]:
                conflicts += HARD
                hv["room_double_booking"] += 1

            same_lvl = ci["level"] == cj["level"]
            same_gen = ci["section_gender"] == cj["section_gender"]
            same_crs = ci["course_id"] == cj["course_id"]
            both_lab = ci["course_type"] == "Lab" and cj["course_type"] == "Lab"
            if same_lvl and same_gen and not same_crs and not both_lab:
                conflicts += HARD
                hv["student_group_conflict"] += 1

    total_hard = sum(hv.values())

    instructor_min_load_penalty = 0.0
    if instructor_hours:
        avg_hrs = sum(instructor_hours.values()) / len(instructor_hours)
        for iid, actual in instructor_hours.items():
            if actual < avg_hrs * 0.5:
                penalty = avg_hrs * 0.5 - actual
                conflicts += SOFT * penalty
                instructor_min_load_penalty += penalty

    student_gaps = 0
    student_days_count = 0
    instructor_gaps = 0
    instructor_days_count = 0
    late_slots = 0
    room_utilization_penalty = 0
    workload_balance_penalty = 0

    if objective == "university":
        if data:
            num_slots = len(data["days"]) * len(get_class_periods(data))
        else:
            num_slots = 45
        for rid, used in room_usage.items():
            util = used / num_slots if num_slots > 0 else 0
            if util < 0.1:
                conflicts += SOFT * 0.5
                room_utilization_penalty += 1

        course_day_slots = {}
        for item in schedule:
            cid = item["course_id"]
            day = item["day"]
            idx = item["period_number"]
            course_day_slots.setdefault((cid, day), []).append(idx)
        for slots in course_day_slots.values():
            if len(slots) > 1:
                slots.sort()
                for k in range(len(slots) - 1):
                    gap = slots[k + 1] - slots[k]
                    if gap > 1:
                        conflicts += SOFT * gap
                        student_gaps += gap

        if len(instructor_hours) > 1:
            avg_h = sum(instructor_hours.values()) / len(instructor_hours)
            for hrs in instructor_hours.values():
                if hrs > avg_h * 2:
                    conflicts += SOFT
                    workload_balance_penalty += 1

    elif objective == "instructor":
        for iid, days in instructor_days_map.items():
            if len(days) > 3:
                conflicts += SOFT * (len(days) - 3)
                instructor_days_count += len(days) - 3

        for iid, slot_list in instructor_slots_map.items():
            by_day = {}
            for (day, idx) in slot_list:
                by_day.setdefault(day, []).append(idx)
            for slots in by_day.values():
                slots.sort()
                for k in range(len(slots) - 1):
                    gap = slots[k + 1] - slots[k]
                    if gap > 1:
                        conflicts += SOFT * gap
                        instructor_gaps += gap

        if len(instructor_hours) > 1:
            avg_h = sum(instructor_hours.values()) / len(instructor_hours)
            for hrs in instructor_hours.values():
                if hrs > avg_h * 2:
                    conflicts += SOFT
                    workload_balance_penalty += 1

    elif objective == "student":
        for (level, sgender), days in student_days_map.items():
            if len(days) > 3:
                conflicts += SOFT * (len(days) - 3)
                student_days_count += len(days) - 3

        level_slots = {}
        for item in schedule:
            key = (item["level"], item["section_gender"], item["day"])
            idx = item["period_number"]
            level_slots.setdefault(key, []).append(idx)
        for slots in level_slots.values():
            slots.sort()
            for k in range(len(slots) - 1):
                gap = slots[k + 1] - slots[k]
                if gap > 1:
                    conflicts += SOFT * gap
                    student_gaps += gap

        for item in schedule:
            idx = item["period_number"]
            if idx == last_slot:
                conflicts += SOFT
                late_slots += 1
            elif idx == last_slot - 1:
                conflicts += SOFT * 0.5
                late_slots += 1

    stats = {
        "fitness_score": round(conflicts, 2),
        "hard_violations": total_hard,
        "soft_cost": round(conflicts - total_hard * HARD, 2),
        "feasible": total_hard == 0,
        "instructor_double_booking": hv["instructor_double_booking"],
        "room_double_booking": hv["room_double_booking"],
        "student_group_conflict": hv["student_group_conflict"],
        "capacity_issues": hv["capacity_issues"],
        "prayer_time_violations": hv["prayer_time_violations"],
        "gender_separation_violations": hv["gender_separation_violations"],
        "prerequisite_overlap": hv["prerequisite_overlap"],
        "student_gaps": student_gaps,
        "student_days": student_days_count,
        "instructor_gaps": instructor_gaps,
        "instructor_days": instructor_days_count,
        "late_slots": late_slots,
        "room_utilization_penalty": room_utilization_penalty,
        "workload_balance_penalty": workload_balance_penalty,
        "instructor_min_load_penalty": round(instructor_min_load_penalty, 2),
    }

    return conflicts, stats


def copy_assignment_from_best(current_item, best_item):
    fields_to_copy = [
        "day",
        "period",
        "period_number",
        "time",
        "room",
        "room_capacity",
        "room_gender",
        "room_type",
        "professor",
        "professor_id",
        "professor_gender",
        "professor_department",
        "professor_min_hours",
        "professor_max_hours"
    ]

    for field in fields_to_copy:
        current_item[field] = best_item[field]

    return current_item


def update_particle_position(current_position, personal_best, global_best, data, gender):
    new_position = []

    for i in range(len(current_position)):
        current_item = current_position[i].copy()
        probability = random.random()

        if personal_best and probability < 0.35:
            current_item = copy_assignment_from_best(
                current_item,
                personal_best[i]
            )

        elif global_best and probability < 0.75:
            current_item = copy_assignment_from_best(
                current_item,
                global_best[i]
            )

        else:
            current_item = randomize_assignment(
                current_item,
                data,
                gender
            )

        new_position.append(current_item)

    new_position = repair_schedule(new_position, data, gender)

    return new_position


def sort_schedule(schedule):
    day_order = {
        "Sunday": 1,
        "Monday": 2,
        "Tuesday": 3,
        "Wednesday": 4,
        "Thursday": 5
    }

    return sorted(
        schedule,
        key=lambda item: (
            day_order.get(item["day"], 99),
            item["period_number"],
            item["course_id"]
        )
    )
