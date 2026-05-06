import random
import re
import statistics


HARD_CONSTRAINT_WEIGHT = 1000

SOFT_WEIGHTS = {
    "student_gaps": 10,
    "student_days": 5,
    "instructor_gaps": 8,
    "instructor_days": 4,
    "late_slots": 6,
    "room_utilization": 3,
    "workload_balance": 5,
    "instructor_min_load": 4,
    "consecutive_sections": 2
}


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


def calculate_hard_constraints(schedule):
    violations = {
        "instructor_double_booking": 0,
        "room_double_booking": 0,
        "student_group_conflict": 0,
        "capacity_issues": 0,
        "prayer_time_violations": 0,
        "gender_separation_violations": 0,
        "prerequisite_overlap": 0
    }

    for item in schedule:
        if item["room_capacity"] < item["section_capacity"]:
            violations["capacity_issues"] += 1

        if not gender_matches(item["section_gender"], item["room_gender"]):
            violations["gender_separation_violations"] += 1

        if not gender_matches(item["section_gender"], item["professor_gender"]):
            violations["gender_separation_violations"] += 1

        period_text = str(item.get("period", "")).lower()
        time_text = str(item.get("time", "")).lower()

        if "prayer" in period_text or "prayer" in time_text:
            violations["prayer_time_violations"] += 1

    for i in range(len(schedule)):
        for j in range(i + 1, len(schedule)):
            first = schedule[i]
            second = schedule[j]

            if not same_time(first, second):
                continue

            if first["professor_id"] == second["professor_id"]:
                violations["instructor_double_booking"] += 1

            if first["room"] == second["room"]:
                violations["room_double_booking"] += 1

            if first["cohort_key"] == second["cohort_key"]:
                violations["student_group_conflict"] += 1

            first_prerequisites = set(first.get("prerequisites", []))
            second_prerequisites = set(second.get("prerequisites", []))

            if second["course_id"] in first_prerequisites:
                violations["prerequisite_overlap"] += 1

            if first["course_id"] in second_prerequisites:
                violations["prerequisite_overlap"] += 1

    return violations


def calculate_gaps_by_key(schedule, key_name):
    groups = {}

    for item in schedule:
        key = item[key_name]

        if key not in groups:
            groups[key] = {}

        day = item["day"]

        if day not in groups[key]:
            groups[key][day] = []

        groups[key][day].append(item["period_number"])

    total_gaps = 0
    total_days = 0
    consecutive_sections = 0

    for key in groups:
        used_days = groups[key]
        total_days += len(used_days)

        for day in used_days:
            periods = sorted(used_days[day])

            for i in range(len(periods) - 1):
                difference = periods[i + 1] - periods[i]

                if difference == 1:
                    consecutive_sections += 1

                elif difference > 1:
                    total_gaps += difference - 1

    return total_gaps, total_days, consecutive_sections


def calculate_room_utilization_penalty(schedule):
    penalty = 0

    for item in schedule:
        room_capacity = max(item["room_capacity"], 1)
        enrolled = item["section_capacity"]

        utilization = enrolled / room_capacity

        if utilization < 0.50:
            penalty += 2

        elif utilization < 0.70:
            penalty += 1

    return penalty


def calculate_late_slot_penalty(schedule):
    penalty = 0

    for item in schedule:
        if item["period_number"] >= 7:
            penalty += 1

    return penalty


def calculate_workload_balance_penalty(schedule):
    professor_loads = {}

    for item in schedule:
        professor_id = item["professor_id"]

        if professor_id not in professor_loads:
            professor_loads[professor_id] = 0

        professor_loads[professor_id] += max(item["credits"], 1)

    if len(professor_loads) <= 1:
        return 0

    loads = list(professor_loads.values())
    return statistics.pstdev(loads)


def calculate_instructor_min_load_penalty(schedule):
    professor_loads = {}
    professor_min_hours = {}

    for item in schedule:
        professor_id = item["professor_id"]

        if professor_id not in professor_loads:
            professor_loads[professor_id] = 0

        professor_loads[professor_id] += max(item["credits"], 1)
        professor_min_hours[professor_id] = item["professor_min_hours"]

    penalty = 0

    for professor_id in professor_loads:
        minimum = professor_min_hours.get(professor_id, 0)

        if minimum > 0 and professor_loads[professor_id] < minimum:
            penalty += minimum - professor_loads[professor_id]

    return penalty


def calculate_soft_constraints(schedule):
    student_gaps, student_days, student_consecutive = calculate_gaps_by_key(
        schedule,
        "cohort_key"
    )

    instructor_gaps, instructor_days, instructor_consecutive = calculate_gaps_by_key(
        schedule,
        "professor_id"
    )

    room_utilization_penalty = calculate_room_utilization_penalty(schedule)
    late_slot_penalty = calculate_late_slot_penalty(schedule)
    workload_balance_penalty = calculate_workload_balance_penalty(schedule)
    instructor_min_load_penalty = calculate_instructor_min_load_penalty(schedule)

    soft_values = {
        "student_gaps": student_gaps,
        "student_days": student_days,
        "instructor_gaps": instructor_gaps,
        "instructor_days": instructor_days,
        "late_slots": late_slot_penalty,
        "room_utilization": room_utilization_penalty,
        "workload_balance": workload_balance_penalty,
        "instructor_min_load": instructor_min_load_penalty,
        "consecutive_sections": -(student_consecutive + instructor_consecutive)
    }

    soft_cost = 0

    for key, value in soft_values.items():
        soft_cost += value * SOFT_WEIGHTS[key]

    return soft_cost, soft_values


def calculate_fitness(schedule):
    hard_violations = calculate_hard_constraints(schedule)
    soft_cost, soft_values = calculate_soft_constraints(schedule)

    total_hard_violations = sum(hard_violations.values())

    fitness_score = (
        total_hard_violations * HARD_CONSTRAINT_WEIGHT
        + soft_cost
    )

    stats = {
        "fitness_score": round(fitness_score, 2),
        "hard_violations": total_hard_violations,
        "soft_cost": round(soft_cost, 2),
        "feasible": total_hard_violations == 0,

        "instructor_double_booking": hard_violations["instructor_double_booking"],
        "room_double_booking": hard_violations["room_double_booking"],
        "student_group_conflict": hard_violations["student_group_conflict"],
        "capacity_issues": hard_violations["capacity_issues"],
        "prayer_time_violations": hard_violations["prayer_time_violations"],
        "gender_separation_violations": hard_violations["gender_separation_violations"],
        "prerequisite_overlap": hard_violations["prerequisite_overlap"],

        "student_gaps": soft_values["student_gaps"],
        "student_days": soft_values["student_days"],
        "instructor_gaps": soft_values["instructor_gaps"],
        "instructor_days": soft_values["instructor_days"],
        "late_slots": soft_values["late_slots"],
        "room_utilization_penalty": soft_values["room_utilization"],
        "workload_balance_penalty": round(soft_values["workload_balance"], 2),
        "instructor_min_load_penalty": soft_values["instructor_min_load"]
    }

    return fitness_score, stats


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
