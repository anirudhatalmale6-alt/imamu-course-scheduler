"""
common.py - Shared Scheduling Algorithm Utilities
==================================================

This file contains all the shared helper functions used by both the Genetic Algorithm
(GA) and Particle Swarm Optimization (PSO) scheduling algorithms. It is the most
critical file in the scheduling system because it defines:

1. CONSTRAINT CHECKING - The fitness function that evaluates how "good" a schedule is.
   It checks for Hard Constraints (HC1-HC7) that MUST NOT be violated, and Soft
   Constraints (SC) that we PREFER to satisfy but can tolerate violations of.

2. POSITION CREATION - Functions that build a random schedule (called a "position" in
   PSO terminology or an "individual/chromosome" in GA terminology).

3. REPAIR MECHANISM - A function that attempts to fix constraint violations by
   re-randomizing conflicting assignments.

4. PSO PARTICLE UPDATE - The discrete adaptation of the PSO velocity/position update
   for the combinatorial scheduling domain.

Hard Constraints (violations are penalized with weight HARD = 1.0 each):
    HC1: Instructor Double Booking - An instructor cannot teach two classes at the same time.
    HC2: Room Double Booking      - A room cannot host two classes at the same time.
    HC3: Student Group Conflict   - Students in the same level/gender group cannot have
                                    two different non-lab courses at the same time.
    HC4: Room Capacity            - The room must have enough seats for the section.
    HC5: Prayer Time              - No classes may be scheduled during prayer periods.
    HC6: Gender Separation        - Room gender and instructor gender must match section gender
                                    (Saudi university policy).
    HC7: Prerequisite Overlap     - A course and its prerequisite cannot be at the same time slot.

Soft Constraints (violations are penalized with weight SOFT = 0.1 each, scaled by severity):
    These vary by optimization objective (university / instructor / student).
    - University: room utilization, class spacing, workload balance across instructors.
    - Instructor: fewer teaching days, minimal gaps between classes, balanced workload.
    - Student: fewer attendance days, minimal gaps between classes, avoid late time slots.

The fitness score is the SUM of all penalties. A lower score = a better schedule.
A score of 0.0 means a perfect schedule with no violations at all.
"""

import random
import re


# ---------------------------------------------------------------------------
# Penalty weights for constraint violations in the fitness function.
# HARD constraints are absolutely critical (weight = 1.0 per violation).
# SOFT constraints are preferences we want to optimize (weight = 0.1 per unit).
# The large difference in weights ensures the algorithm always prioritizes
# eliminating hard violations before optimizing soft preferences.
# ---------------------------------------------------------------------------
HARD = 1.0
SOFT = 0.1


# ===========================================================================
# SECTION 1: UTILITY / HELPER FUNCTIONS
# ===========================================================================


def safe_int(value, default=0):
    """
    Safely convert a value to an integer, returning a default if conversion fails.

    This is used throughout the codebase when reading capacity, credits, hours, etc.
    from data dictionaries that may contain None, empty strings, or non-numeric values.

    Args:
        value:   The value to convert (could be int, str, None, etc.).
        default: The fallback integer to return if conversion fails (default: 0).

    Returns:
        int: The converted integer, or `default` if conversion was not possible.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_gender(value):
    """
    Normalize gender strings to a consistent format ("Male" or "Female").

    The university data may contain various representations of gender
    (e.g., "m", "male", "boys", "men", "f", "female", "girls", "women").
    This function standardizes them so gender comparisons work reliably
    throughout the scheduling algorithm.

    Args:
        value: A gender string in any format, or None.

    Returns:
        str: "Male", "Female", or the cleaned original string if unrecognized.
             Returns "" if input is None.
    """
    if value is None:
        return ""

    value = str(value).strip().lower()

    if value in ["m", "male", "boys", "men"]:
        return "Male"

    if value in ["f", "female", "girls", "women"]:
        return "Female"

    return str(value).strip()


def gender_matches(a, b):
    """
    Check if two gender values refer to the same gender after normalization.

    Used for constraint HC6 (gender separation) to verify that rooms and
    instructors match the section's gender.

    Args:
        a: First gender value (any format).
        b: Second gender value (any format).

    Returns:
        bool: True if both values normalize to the same gender string.
    """
    return normalize_gender(a) == normalize_gender(b)


def period_number(period_id):
    """
    Extract the numeric portion from a period/time-slot ID string.

    Period IDs may look like "Period1", "P2", "slot_3", etc. This function
    extracts the first number found and returns it as an integer. The numeric
    ordering is used to detect gaps between consecutive classes (e.g., if a
    student has Period 1 and Period 4, there is a 2-slot gap).

    Args:
        period_id: The period identifier string (e.g., "Period3").

    Returns:
        int: The extracted number (e.g., 3), or 0 if no digits are found.
    """
    numbers = re.findall(r"\d+", str(period_id))

    if not numbers:
        return 0

    return int(numbers[0])


def get_class_periods(data):
    """
    Filter the list of all time periods to return only CLASS periods.

    The university day includes prayer breaks and regular breaks in addition
    to class periods. This function removes any period whose type or ID
    contains "prayer" or "break", returning only the slots where classes
    can actually be scheduled.

    This filtering is essential for constraint HC5 (prayer time) - we never
    assign classes to prayer/break slots.

    Args:
        data: The algorithm data dictionary containing a "periods" list.

    Returns:
        list: A list of period dictionaries that are valid for class scheduling.
    """
    class_periods = []

    for period in data["periods"]:
        period_type = str(period.get("type", "Class")).lower()
        period_id = str(period.get("id", "")).lower()

        # Skip prayer time slots - classes must not be scheduled during prayers (HC5)
        if "prayer" in period_type or "break" in period_type:
            continue

        if "prayer" in period_id or "break" in period_id:
            continue

        class_periods.append(period)

    return class_periods


def parse_prerequisites(prerequisite_text):
    """
    Parse a prerequisite string into a list of individual course codes.

    Prerequisites in the data may be stored as a comma-separated string like
    "CS101,CS102" or "CS101 CS102" or even "CS101;CS102/CS103". This function
    splits on any common delimiter and returns a clean list of course codes.

    These codes are used for constraint HC7 (prerequisite overlap) - a course
    and its prerequisite must not be scheduled at the exact same time slot.

    Args:
        prerequisite_text: A string of prerequisite course codes, or None.

    Returns:
        list: A list of stripped course code strings, or an empty list if none.
    """
    if prerequisite_text is None:
        return []

    text = str(prerequisite_text).strip()

    if text == "":
        return []

    # Handle common "no prerequisites" markers
    if text.lower() in ["none", "no", "null", "n/a", "-"]:
        return []

    # Split on commas, spaces, semicolons, or slashes
    parts = re.split(r"[,\s;/]+", text)

    prerequisites = []

    for part in parts:
        clean_part = part.strip()

        if clean_part:
            prerequisites.append(clean_part)

    return prerequisites


# ===========================================================================
# SECTION 2: DATA LOOKUP BUILDERS
# These create dictionaries for O(1) lookups by ID, avoiding repeated
# linear scans through the course/room/professor lists.
# ===========================================================================


def build_course_lookup(data):
    """
    Build a dictionary mapping course IDs to course data for fast lookup.

    Args:
        data: The algorithm data dictionary containing a "courses" list.

    Returns:
        dict: {course_id: course_dict, ...}
    """
    lookup = {}

    for course in data["courses"]:
        lookup[course["id"]] = course

    return lookup


def build_room_lookup(data):
    """
    Build a dictionary mapping room IDs to room data for fast lookup.

    Args:
        data: The algorithm data dictionary containing a "rooms" list.

    Returns:
        dict: {room_id: room_dict, ...}
    """
    lookup = {}

    for room in data["rooms"]:
        lookup[room["id"]] = room

    return lookup


def build_professor_lookup(data):
    """
    Build a dictionary mapping professor IDs to professor data for fast lookup.

    Args:
        data: The algorithm data dictionary containing a "professors" list.

    Returns:
        dict: {professor_id: professor_dict, ...}
    """
    lookup = {}

    for professor in data["professors"]:
        lookup[professor["id"]] = professor

    return lookup


# ===========================================================================
# SECTION 3: RESOURCE FILTERING (gender + capacity matching)
# ===========================================================================


def get_available_rooms(data, gender, required_capacity=None):
    """
    Get rooms that match the required gender and capacity constraints (HC4, HC6).

    This implements a two-pass approach:
      Pass 1: Find rooms matching BOTH the gender AND the minimum capacity.
      Pass 2 (fallback): If no rooms passed both filters, relax the capacity
              requirement and return all gender-matching rooms. This ensures
              the algorithm can still produce a schedule even if no room is
              large enough - the fitness function will penalize the capacity
              violation as a hard constraint (HC4).

    Args:
        data:              The algorithm data dictionary containing a "rooms" list.
        gender:            The required gender for the room (e.g., "Male").
        required_capacity: Minimum number of seats needed, or None to skip check.

    Returns:
        list: A list of room dictionaries that are candidates for assignment.
    """
    rooms = []

    for room in data["rooms"]:
        # HC6: Room gender must match section gender
        if not gender_matches(room.get("gender"), gender):
            continue

        # HC4: Room capacity must be >= section capacity
        if required_capacity is not None:
            if safe_int(room.get("capacity")) < safe_int(required_capacity):
                continue

        rooms.append(room)

    # Fallback: if no room met both criteria, drop the capacity filter
    # so we at least get gender-matching rooms (capacity violation will be
    # caught and penalized by the fitness function)
    if not rooms:
        for room in data["rooms"]:
            if gender_matches(room.get("gender"), gender):
                rooms.append(room)

    return rooms


def get_available_professors(data, gender, department=None):
    """
    Get professors that match the required gender and optionally department (HC6).

    Similar two-pass approach as get_available_rooms:
      Pass 1: Match both gender AND department.
      Pass 2 (fallback): If none matched, relax department filter.

    Args:
        data:       The algorithm data dictionary containing a "professors" list.
        gender:     The required gender for the instructor (e.g., "Female").
        department: The preferred department, or None to skip department matching.

    Returns:
        list: A list of professor dictionaries that are candidates for assignment.
    """
    professors = []

    for professor in data["professors"]:
        # HC6: Professor gender must match section gender
        if not gender_matches(professor.get("gender"), gender):
            continue

        # Prefer professors from the same department as the course
        if department is not None:
            professor_department = str(professor.get("department", "")).strip()
            if professor_department and professor_department != department:
                continue

        professors.append(professor)

    # Fallback: if no professor matched both criteria, drop department filter
    if not professors:
        for professor in data["professors"]:
            if gender_matches(professor.get("gender"), gender):
                professors.append(professor)

    return professors


# ===========================================================================
# SECTION 4: COHORT / STUDENT GROUP IDENTIFICATION
# ===========================================================================


def make_cohort_key(course, section, gender):
    """
    Create a unique key identifying a student cohort (group of students
    who share the same classes).

    In Saudi university scheduling, students are grouped by:
      - Gender (Male/Female - separate campuses/sections)
      - Department (e.g., Computer Science, Mathematics)
      - Level (e.g., Level 1 = freshman, Level 4 = senior)
      - Section group (extracted from section ID, e.g., "A" from "CS101-A")

    Students in the same cohort take the same set of courses, so they
    must NOT have two different courses at the same time (HC3).

    Args:
        course:  The course dictionary (has "department" and "level").
        section: The section dictionary (has "id" like "CS101-A").
        gender:  The gender of the section.

    Returns:
        str: A cohort key like "Male-CS-L2-A".
    """
    department = course.get("department", "UnknownDepartment")
    level = course.get("level", "UnknownLevel")
    section_id = section.get("id", "")

    # Extract the group letter/number from the section ID (part after the dash)
    section_group = "G"

    if "-" in section_id:
        section_group = section_id.split("-")[-1]

    return f"{normalize_gender(gender)}-{department}-L{level}-{section_group}"


# ===========================================================================
# SECTION 5: SECTION SELECTION (which course sections to schedule)
# ===========================================================================


def get_selected_course_sections(selected_courses, data, gender, max_sections=60):
    """
    Build a flat list of section descriptors for all selected courses.

    This function performs ROUND-ROBIN selection across courses to ensure
    fairness: it picks one section from each course before picking a second
    section from any course. This prevents a single course with many sections
    from consuming the entire section budget.

    Each section descriptor is a dictionary containing all the information
    needed to create an assignment (course details, section details, cohort key).

    Args:
        selected_courses: List of course IDs the user wants to schedule.
        data:             The algorithm data dictionary.
        gender:           The preferred gender filter.
        max_sections:     Maximum number of sections to include (default: 60).
                          This caps the problem size for performance.

    Returns:
        list: A list of section descriptor dictionaries, up to max_sections.
    """
    selected_set = set(selected_courses)

    # Phase 1: Gather all sections for each selected course
    course_sections = {}
    for course in data["courses"]:
        if course["id"] not in selected_set:
            continue
        secs = []
        for section in course["sections"]:
            sec_gender = normalize_gender(section.get("gender"))
            secs.append({
                "course_id": course["id"],
                "course_name": course["name"],
                "department": course.get("department", ""),
                "level": course.get("level", ""),
                "credits": safe_int(course.get("credits")),
                "course_type": course.get("type", ""),
                "prerequisites": parse_prerequisites(course.get("prerequisites")),
                "section_id": section["id"],
                "section_gender": sec_gender,
                "section_capacity": safe_int(section.get("capacity")),
                "waitlist": safe_int(section.get("waitlist")),
                "cohort_key": make_cohort_key(course, section, sec_gender)
            })
        if secs:
            course_sections[course["id"]] = secs

    # Phase 2: Round-robin selection - pick one section per course per round
    # until we reach max_sections or run out of sections
    selected_sections = []
    round_idx = 0
    while max_sections is None or len(selected_sections) < max_sections:
        added = 0
        for cid in course_sections:
            if max_sections and len(selected_sections) >= max_sections:
                break
            secs = course_sections[cid]
            # If this course still has a section at round_idx, pick it
            if round_idx >= len(secs):
                continue
            selected_sections.append(secs[round_idx])
            added += 1
        # If no course had a section at this round index, all are exhausted
        if added == 0:
            break
        round_idx += 1

    return selected_sections


# ===========================================================================
# SECTION 6: ASSIGNMENT CREATION (building a single schedule entry)
# ===========================================================================


def create_assignment(section, data, gender):
    """
    Create a RANDOM assignment for a single course section.

    An "assignment" is one row in the schedule: it maps a section to a specific
    day, time period, room, and instructor. This function randomly selects
    from the available (gender-compatible) options.

    The randomness is intentional - the optimization algorithms (GA/PSO) start
    with random schedules and then iteratively improve them. The fitness function
    evaluates whether the random choices caused constraint violations.

    Args:
        section: A section descriptor dict (from get_selected_course_sections).
        data:    The algorithm data dictionary with rooms, professors, days, periods.
        gender:  The gender context for filtering rooms and professors.

    Returns:
        dict: A complete assignment dictionary with all schedule details,
              or None if no valid resources are available (missing rooms/profs/etc).
    """
    sec_gender = section["section_gender"]

    # Find rooms that match the section's gender and have enough capacity
    rooms = get_available_rooms(
        data,
        sec_gender,
        required_capacity=section["section_capacity"]
    )

    # Find instructors that match the section's gender and department
    professors = get_available_professors(
        data,
        sec_gender,
        department=section["department"]
    )

    days = data["days"]
    periods = get_class_periods(data)  # Only class periods, no prayer/break

    # If any resource list is empty, we cannot create an assignment
    if not rooms or not professors or not days or not periods:
        return None

    # Randomly select one option from each resource pool
    room = random.choice(rooms)
    professor = random.choice(professors)
    day = random.choice(days)
    period = random.choice(periods)

    # Build and return the complete assignment dictionary
    return {
        # --- Course information (copied from section descriptor) ---
        "course_id": section["course_id"],
        "course_name": section["course_name"],
        "department": section["department"],
        "level": section["level"],
        "credits": section["credits"],
        "course_type": section["course_type"],
        "prerequisites": section["prerequisites"],

        # --- Section information ---
        "section_id": section["section_id"],
        "section_gender": section["section_gender"],
        "section_capacity": section["section_capacity"],
        "waitlist": section["waitlist"],
        "cohort_key": section["cohort_key"],

        # --- Time assignment (randomly chosen) ---
        "day": day,
        "period": period["id"],
        "period_number": period_number(period["id"]),
        "time": period["start"] + " - " + period["end"],

        # --- Room assignment (randomly chosen) ---
        "room": room["id"],
        "room_capacity": safe_int(room.get("capacity")),
        "room_gender": normalize_gender(room.get("gender")),
        "room_type": room.get("type", ""),

        # --- Instructor assignment (randomly chosen) ---
        "professor": professor["name"],
        "professor_id": professor["id"],
        "professor_gender": normalize_gender(professor.get("gender")),
        "professor_department": professor.get("department", ""),
        "professor_min_hours": safe_int(professor.get("min_hours")),
        "professor_max_hours": safe_int(professor.get("max_hours"))
    }


# ===========================================================================
# SECTION 7: POSITION (FULL SCHEDULE) CREATION
# A "position" is the complete schedule for all sections - it is one
# candidate solution in the search space. In GA terms, this is a
# "chromosome". In PSO terms, this is a "particle position".
# ===========================================================================


def create_random_position(selected_courses, data, gender):
    """
    Create a complete random schedule (position/chromosome) for all sections.

    For each section, the number of time slots needed equals the course's credit
    hours. For example, a 3-credit course needs 3 class periods per week.
    Each slot gets a random assignment (day, period, room, instructor).

    After random creation, the repair_schedule function is called to attempt
    to fix any obvious constraint violations.

    Args:
        selected_courses: List of course IDs to include in the schedule.
        data:             The algorithm data dictionary.
        gender:           Gender context for resource filtering.

    Returns:
        list: A list of assignment dictionaries representing the full schedule.
    """
    sections = get_selected_course_sections(selected_courses, data, gender)
    position = []

    for section in sections:
        # Each credit hour requires one weekly time slot
        # (minimum 1 slot even for 0-credit courses)
        num_slots = max(section["credits"], 1)

        for _ in range(num_slots):
            assignment = create_assignment(section, data, gender)

            if assignment is not None:
                position.append(assignment)

    # Attempt to fix constraint violations in the randomly generated schedule
    position = repair_schedule(position, data, gender)

    return position


def copy_position(position):
    """
    Create a shallow copy of a schedule (list of assignment dicts).

    Each assignment dict is individually copied so modifications to one
    schedule do not affect others. This is important because GA and PSO
    maintain multiple candidate solutions simultaneously (population/swarm).

    Args:
        position: A list of assignment dictionaries (a complete schedule).

    Returns:
        list: A new list with copied assignment dictionaries.
    """
    return [item.copy() for item in position]


# ===========================================================================
# SECTION 8: CONFLICT DETECTION AND SCHEDULE REPAIR
# ===========================================================================


def same_time(first, second):
    """
    Check if two assignments are scheduled at the exact same day and period.

    This is the core check used to detect pairwise conflicts like instructor
    double-booking (HC1), room double-booking (HC2), and student group
    conflicts (HC3).

    Args:
        first:  An assignment dictionary.
        second: An assignment dictionary.

    Returns:
        bool: True if both assignments occupy the same day and time period.
    """
    return (
        first["day"] == second["day"]
        and first["period"] == second["period"]
    )


def get_conflicting_indices(schedule):
    """
    Find all assignment indices in the schedule that violate hard constraints.

    This function checks for:
    - HC1: Instructor double-booking (same professor, same time)
    - HC2: Room double-booking (same room, same time)
    - HC3: Student group conflict (same cohort, same time)
    - HC4: Room capacity insufficient
    - HC6: Gender mismatch between section and room/instructor
    - HC7: Prerequisite courses scheduled at the same time

    These indices are used by repair_schedule to identify WHICH assignments
    need to be re-randomized in order to fix violations.

    Args:
        schedule: A list of assignment dictionaries (a complete schedule).

    Returns:
        set: A set of integer indices into the schedule list that are involved
             in at least one hard constraint violation.
    """
    conflicting_indices = set()

    # --- Pairwise checks: compare every pair of assignments ---
    for i in range(len(schedule)):
        for j in range(i + 1, len(schedule)):
            first = schedule[i]
            second = schedule[j]

            # Only check pairs that are at the same day+period
            if not same_time(first, second):
                continue

            # HC1: Same instructor teaching two classes at the same time
            if first["professor_id"] == second["professor_id"]:
                conflicting_indices.add(i)
                conflicting_indices.add(j)

            # HC2: Same room hosting two classes at the same time
            if first["room"] == second["room"]:
                conflicting_indices.add(i)
                conflicting_indices.add(j)

            # HC3: Same student cohort has two classes at the same time
            if first["cohort_key"] == second["cohort_key"]:
                conflicting_indices.add(i)
                conflicting_indices.add(j)

            # HC7: A course and its prerequisite at the same time
            first_prerequisites = set(first.get("prerequisites", []))
            second_prerequisites = set(second.get("prerequisites", []))

            if second["course_id"] in first_prerequisites:
                conflicting_indices.add(i)
                conflicting_indices.add(j)

            if first["course_id"] in second_prerequisites:
                conflicting_indices.add(i)
                conflicting_indices.add(j)

    # --- Single-assignment checks: each assignment checked individually ---
    for i, item in enumerate(schedule):
        # HC4: Room too small for the section
        if item["room_capacity"] < item["section_capacity"]:
            conflicting_indices.add(i)

        # HC6: Room gender does not match section gender
        if not gender_matches(item["section_gender"], item["room_gender"]):
            conflicting_indices.add(i)

        # HC6: Instructor gender does not match section gender
        if not gender_matches(item["section_gender"], item["professor_gender"]):
            conflicting_indices.add(i)

    return conflicting_indices


def randomize_assignment(current_item, data, gender):
    """
    Re-randomize the time, room, and instructor of a conflicting assignment.

    This preserves all course/section information but generates a new random
    combination of day, period, room, and instructor. It is used by the
    repair mechanism and by mutation in the GA.

    Args:
        current_item: The assignment dictionary to re-randomize.
        data:         The algorithm data dictionary.
        gender:       Gender context for resource filtering.

    Returns:
        dict: A new assignment with different day/period/room/professor,
              or the original item unchanged if creation failed.
    """
    # Extract the section descriptor fields from the current assignment
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

    # Generate a brand new random assignment for this section
    new_assignment = create_assignment(section, data, gender)

    if new_assignment is None:
        return current_item

    return new_assignment


def repair_schedule(schedule, data, gender, max_attempts=80):
    """
    Attempt to fix hard constraint violations by re-randomizing conflicting slots.

    This is a STOCHASTIC REPAIR heuristic: it repeatedly identifies conflicting
    assignments, picks one at random, and gives it a new random day/period/room/
    professor. After up to max_attempts iterations, it returns the (hopefully
    improved) schedule.

    The repair is not guaranteed to eliminate all violations, but it significantly
    reduces them. Any remaining violations will be penalized by the fitness function,
    driving the GA/PSO to find better solutions over subsequent generations/iterations.

    Args:
        schedule:     A list of assignment dictionaries (a complete schedule).
        data:         The algorithm data dictionary.
        gender:       Gender context for resource filtering.
        max_attempts: Maximum number of repair iterations (default: 80).

    Returns:
        list: The repaired schedule (a new list; the original is not modified).
    """
    repaired = copy_position(schedule)

    for _ in range(max_attempts):
        # Find all assignments involved in at least one hard violation
        conflicting_indices = get_conflicting_indices(repaired)

        # If no conflicts remain, the schedule is feasible - stop early
        if not conflicting_indices:
            break

        # Pick one conflicting assignment at random and re-randomize it
        index = random.choice(list(conflicting_indices))
        repaired[index] = randomize_assignment(repaired[index], data, gender)

    return repaired


# ===========================================================================
# SECTION 9: FITNESS FUNCTION
# This is the CORE of the scheduling system. It evaluates the quality of
# a candidate schedule by computing a penalty score. Lower = better.
#
# The fitness function mirrors GA_runner.py's calculate_fitness_multi with:
#   - HARD weight = 1.0 per hard constraint violation
#   - SOFT weight = 0.1 per soft constraint violation unit
#
# A schedule is "feasible" if and only if total_hard == 0.
# ===========================================================================


def calculate_fitness(schedule, objective="student", data=None):
    """
    Evaluate the quality of a schedule by computing a weighted penalty score.

    This function calculates the total "conflict score" (lower is better) by:
    1. Checking all HARD constraints (HC1-HC7), each adding HARD (1.0) per violation.
    2. Checking SOFT constraints based on the chosen objective, each adding
       SOFT (0.1) scaled by severity.

    The objective parameter selects which soft constraints to evaluate:
    - "university": Optimizes room utilization, class spacing, workload balance.
    - "instructor": Optimizes teaching day count, gaps, workload balance.
    - "student":    Optimizes attendance days, gaps, avoids late time slots.

    All three objectives share the same hard constraints and the instructor
    minimum load penalty.

    Args:
        schedule:  A list of assignment dictionaries (a complete schedule).
        objective: One of "university", "instructor", "student" (default: "student").
        data:      The algorithm data dictionary (optional, used for accurate
                   slot counting).

    Returns:
        tuple: (conflicts, stats)
            - conflicts (float): The total penalty score. 0.0 = perfect schedule.
            - stats (dict): A detailed breakdown of all violation counts and metrics.
              stats["feasible"] is True if there are zero hard violations.
    """
    # Total penalty score (accumulates both hard and soft penalties)
    conflicts = 0.0

    # --- Accumulators for tracking resource usage across the schedule ---
    # Maps instructor_id -> set of days they teach on
    instructor_days_map = {}
    # Maps instructor_id -> list of (day, slot_index) tuples
    instructor_slots_map = {}
    # Maps instructor_id -> total credit hours assigned
    instructor_hours = {}
    # Maps room_id -> number of times it is used
    room_usage = {}
    # Maps (level, section_gender) -> set of days that student group has classes
    student_days_map = {}

    # First pass: build the tracking maps from the schedule
    for item in schedule:
        iid = item["professor_id"]
        rid = item["room"]
        level = item["level"]
        sgender = item["section_gender"]
        day = item["day"]
        slot_idx = item["period_number"]
        credits = max(item["credits"], 1)

        # Track total hours per instructor (for workload balancing)
        instructor_hours[iid] = instructor_hours.get(iid, 0) + credits
        # Track room usage count (for utilization metrics)
        room_usage[rid] = room_usage.get(rid, 0) + 1
        # Track which days each instructor teaches on (for day-spread checks)
        instructor_days_map.setdefault(iid, set()).add(day)
        # Track each instructor's specific time slots (for gap detection)
        instructor_slots_map.setdefault(iid, []).append((day, slot_idx))
        # Track which days each student group has classes (for day-spread checks)
        student_days_map.setdefault((level, sgender), set()).add(day)

    # Determine the last (latest) time slot number - used for late-slot penalty
    if data:
        class_periods = get_class_periods(data)
        all_pnums = [period_number(p["id"]) for p in class_periods]
        last_slot = max(all_pnums) if all_pnums else 99
    else:
        all_slots = [item["period_number"] for item in schedule]
        last_slot = max(all_slots) if all_slots else 99

    # Build a map from course_id -> list of (day, period) tuples
    # Used for HC7 prerequisite overlap detection
    course_schedule_map = {}
    for item in schedule:
        cid = item["course_id"]
        key = (item["day"], item["period"])
        course_schedule_map.setdefault(cid, []).append(key)

    # -----------------------------------------------------------------------
    # HARD CONSTRAINT VIOLATION COUNTERS (HC1-HC7)
    # Each violation adds exactly HARD (1.0) to the total penalty.
    # -----------------------------------------------------------------------
    hv = {
        "instructor_double_booking": 0,   # HC1
        "room_double_booking": 0,          # HC2
        "student_group_conflict": 0,       # HC3
        "capacity_issues": 0,              # HC4
        "prayer_time_violations": 0,       # HC5
        "gender_separation_violations": 0, # HC6
        "prerequisite_overlap": 0,         # HC7
    }

    # -----------------------------------------------------------------------
    # HARD CONSTRAINT CHECKING LOOP
    # Outer loop: check single-item constraints for each assignment.
    # Inner loop: check pairwise constraints for each pair of assignments.
    # -----------------------------------------------------------------------
    for i in range(len(schedule)):
        ci = schedule[i]

        # --- HC4: Room Capacity Check ---
        # The room must have enough seats for all students in the section.
        if ci["room_capacity"] < ci["section_capacity"]:
            conflicts += HARD
            hv["capacity_issues"] += 1

        # --- HC5: Prayer Time Check ---
        # No class should be scheduled during a prayer period.
        # (The get_class_periods filter should prevent this, but this is a
        # safety net in case data is inconsistent.)
        period_text = str(ci.get("period", "")).lower()
        time_text = str(ci.get("time", "")).lower()
        if "prayer" in period_text or "prayer" in time_text:
            conflicts += HARD
            hv["prayer_time_violations"] += 1

        # --- HC6: Gender Separation Check (room) ---
        # The room's designated gender must match the section's gender.
        if not gender_matches(ci["section_gender"], ci["room_gender"]):
            conflicts += HARD
            hv["gender_separation_violations"] += 1

        # --- HC7: Prerequisite Overlap Check ---
        # A course must not be scheduled at the same time as its prerequisite.
        # (Students need to complete the prerequisite first.)
        prereqs = ci.get("prerequisites", [])
        if prereqs:
            my_key = (ci["day"], ci["period"])
            for prereq_id in prereqs:
                if prereq_id in course_schedule_map:
                    if my_key in course_schedule_map[prereq_id]:
                        conflicts += HARD
                        hv["prerequisite_overlap"] += 1

        # --- Pairwise checks (only look at assignments AFTER index i to avoid double-counting) ---
        for j in range(i + 1, len(schedule)):
            cj = schedule[j]

            # Only check pairs at the same day + time period
            if not same_time(ci, cj):
                continue

            # --- HC1: Instructor Double Booking ---
            # One instructor cannot teach two classes simultaneously.
            if ci["professor_id"] == cj["professor_id"]:
                conflicts += HARD
                hv["instructor_double_booking"] += 1

            # --- HC2: Room Double Booking ---
            # One room cannot host two classes simultaneously.
            if ci["room"] == cj["room"]:
                conflicts += HARD
                hv["room_double_booking"] += 1

            # --- HC3: Student Group Conflict ---
            # Students in the same level+gender group cannot have two different
            # non-lab courses at the same time. Lab sections are excluded because
            # different lab groups can run concurrently.
            same_lvl = ci["level"] == cj["level"]
            same_gen = ci["section_gender"] == cj["section_gender"]
            same_crs = ci["course_id"] == cj["course_id"]
            both_lab = ci["course_type"] == "Lab" and cj["course_type"] == "Lab"
            if same_lvl and same_gen and not same_crs and not both_lab:
                conflicts += HARD
                hv["student_group_conflict"] += 1

    # Total count of all hard constraint violations
    total_hard = sum(hv.values())

    # -----------------------------------------------------------------------
    # SOFT CONSTRAINT: INSTRUCTOR MINIMUM LOAD (applies to ALL objectives)
    # Penalize instructors who have less than half the average workload.
    # This encourages balanced workload distribution.
    # -----------------------------------------------------------------------
    instructor_min_load_penalty = 0.0
    if instructor_hours:
        avg_hrs = sum(instructor_hours.values()) / len(instructor_hours)
        for iid, actual in instructor_hours.items():
            if actual < avg_hrs * 0.5:
                # The further below 50% of average, the higher the penalty
                penalty = avg_hrs * 0.5 - actual
                conflicts += SOFT * penalty
                instructor_min_load_penalty += penalty

    # -----------------------------------------------------------------------
    # OBJECTIVE-SPECIFIC SOFT CONSTRAINT ACCUMULATORS
    # -----------------------------------------------------------------------
    student_gaps = 0              # Number of gap periods between student classes
    student_days_count = 0        # Extra days beyond 3 that students must attend
    instructor_gaps = 0           # Number of gap periods between instructor classes
    instructor_days_count = 0     # Extra days beyond 3 that instructors must teach
    late_slots = 0                # Number of classes in the last/second-to-last period
    room_utilization_penalty = 0  # Count of under-utilized rooms or oversized rooms
    workload_balance_penalty = 0  # Count of instructors with >2x average workload

    # ===================================================================
    # OBJECTIVE: UNIVERSITY
    # Focus: efficient resource utilization across the entire institution.
    # ===================================================================
    if objective == "university":
        # --- SC-U1: Room Utilization ---
        # Penalize rooms that are used less than 10% of available slots.
        # This encourages spreading classes across rooms efficiently.
        if data:
            num_slots = len(data["days"]) * len(get_class_periods(data))
        else:
            num_slots = 45  # Fallback estimate (5 days * 9 periods)
        for rid, used in room_usage.items():
            util = used / num_slots if num_slots > 0 else 0
            if util < 0.1:
                conflicts += SOFT * 0.5
                room_utilization_penalty += 1

        # --- SC-U2: Room-to-Section Size Mismatch ---
        # Penalize assigning a very large room to a small section
        # (e.g., 200-seat hall for a 30-student class wastes space).
        for item in schedule:
            capacity = item["room_capacity"]
            enrolled = item["section_capacity"]
            if enrolled > 0 and capacity > enrolled * 2:
                ratio = capacity / enrolled
                # Penalty scales with how oversized the room is, capped at 2.0
                conflicts += SOFT * 0.5 * min(ratio / 2, 2.0)
                room_utilization_penalty += 1

        # --- SC-U3: Class Spacing for Same Course ---
        # Penalize gaps between periods of the same course on the same day.
        # Consecutive periods are preferred (e.g., a 3-credit course should
        # ideally have Period 1, 2, 3 rather than Period 1, 3, 5).
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
                        # Larger gaps get proportionally higher penalty
                        conflicts += SOFT * 0.3 * gap
                        student_gaps += gap

        # --- SC-U4: Workload Balance ---
        # Penalize any instructor whose load exceeds 2x the average.
        if len(instructor_hours) > 1:
            avg_h = sum(instructor_hours.values()) / len(instructor_hours)
            for hrs in instructor_hours.values():
                if hrs > avg_h * 2:
                    conflicts += SOFT
                    workload_balance_penalty += 1

    # ===================================================================
    # OBJECTIVE: INSTRUCTOR
    # Focus: convenient schedule for instructors (fewer days, no gaps).
    # ===================================================================
    elif objective == "instructor":
        # --- SC-I1: Teaching Days Spread ---
        # Penalize instructors who teach on more than 3 days per week.
        # Instructors prefer compact schedules (e.g., Sun/Tue/Thu only).
        for iid, days in instructor_days_map.items():
            if len(days) > 3:
                conflicts += SOFT * (len(days) - 3)
                instructor_days_count += len(days) - 3

        # --- SC-I2: Gaps Between Classes ---
        # Penalize gaps in an instructor's daily schedule.
        # For example, if an instructor has Period 1 and Period 4 on the
        # same day, there is a 2-slot gap (they have to wait around).
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

        # --- SC-I3: Workload Balance ---
        # Same as university objective: penalize >2x average workload.
        if len(instructor_hours) > 1:
            avg_h = sum(instructor_hours.values()) / len(instructor_hours)
            for hrs in instructor_hours.values():
                if hrs > avg_h * 2:
                    conflicts += SOFT
                    workload_balance_penalty += 1

    # ===================================================================
    # OBJECTIVE: STUDENT
    # Focus: convenient schedule for students (fewer days, no gaps, no late).
    # ===================================================================
    elif objective == "student":
        # --- SC-S1: Attendance Days Spread ---
        # Penalize student groups that have classes on more than 3 days.
        # Students prefer compact weekly schedules.
        for (level, sgender), days in student_days_map.items():
            if len(days) > 3:
                conflicts += SOFT * (len(days) - 3)
                student_days_count += len(days) - 3

        # --- SC-S2: Gaps Between Classes ---
        # Penalize gaps in a student group's daily schedule.
        # A student with Period 1 and Period 5 has a painful 3-slot gap.
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

        # --- SC-S3: Late Time Slot Penalty ---
        # Penalize classes in the last or second-to-last period of the day.
        # Students prefer earlier schedules. The last slot gets full penalty,
        # the second-to-last gets half penalty.
        for item in schedule:
            idx = item["period_number"]
            if idx == last_slot:
                conflicts += SOFT
                late_slots += 1
            elif idx == last_slot - 1:
                conflicts += SOFT * 0.5
                late_slots += 1

    # -----------------------------------------------------------------------
    # BUILD THE STATISTICS DICTIONARY
    # This provides a detailed breakdown of all violations and metrics,
    # useful for debugging and for displaying to the user.
    # -----------------------------------------------------------------------
    stats = {
        "fitness_score": round(conflicts, 2),         # Total penalty (lower = better)
        "hard_violations": total_hard,                 # Count of all hard violations
        "soft_cost": round(conflicts - total_hard * HARD, 2),  # Soft penalty portion only
        "feasible": total_hard == 0,                   # True = no hard violations

        # Hard constraint breakdown (HC1-HC7)
        "instructor_double_booking": hv["instructor_double_booking"],   # HC1
        "room_double_booking": hv["room_double_booking"],               # HC2
        "student_group_conflict": hv["student_group_conflict"],         # HC3
        "capacity_issues": hv["capacity_issues"],                       # HC4
        "prayer_time_violations": hv["prayer_time_violations"],         # HC5
        "gender_separation_violations": hv["gender_separation_violations"],  # HC6
        "prerequisite_overlap": hv["prerequisite_overlap"],             # HC7

        # Soft constraint metrics
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


# ===========================================================================
# SECTION 10: PSO PARTICLE POSITION UPDATE
# These functions implement the discrete PSO movement strategy adapted
# for the combinatorial scheduling problem.
# ===========================================================================


def copy_assignment_from_best(current_item, best_item):
    """
    Copy the scheduling fields (day, period, room, instructor) from a "best"
    assignment into a current assignment, keeping the course/section data intact.

    In PSO, this is how a particle "moves toward" a better-known position.
    Instead of continuous velocity vectors, we copy the scheduling decisions
    (which day, which room, etc.) from a better solution.

    Args:
        current_item: The assignment to update (course/section info preserved).
        best_item:    The better assignment to copy scheduling fields from.

    Returns:
        dict: The current_item with updated scheduling fields.
    """
    # These are all the "decision variable" fields - the choices the algorithm
    # makes. Course/section info stays the same; only the schedule changes.
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
    """
    Update a particle's position using the PSO movement strategy.

    In standard (continuous) PSO, each particle moves based on:
        new_velocity = w * velocity + c1 * rand * (personal_best - position)
                       + c2 * rand * (global_best - position)
        new_position = position + new_velocity

    Since our problem is DISCRETE (combinatorial scheduling), we cannot use
    continuous velocity. Instead, we use a PROBABILISTIC approach for each
    assignment in the schedule:

        - With 35% probability: copy from PERSONAL BEST position.
          (Exploiting the particle's own best-known solution.)

        - With 40% probability (0.35 to 0.75): copy from GLOBAL BEST position.
          (Exploiting the swarm's best-known solution. This has a larger
          probability band because the global best is usually higher quality.)

        - With 25% probability (0.75 to 1.0): RANDOMIZE the assignment.
          (Exploration - introducing new diversity to escape local optima.)

    After updating all assignments, the repair function fixes any new violations.

    Args:
        current_position: The particle's current schedule (list of assignments).
        personal_best:    This particle's best-ever schedule.
        global_best:      The best schedule found by ANY particle in the swarm.
        data:             The algorithm data dictionary.
        gender:           Gender context for resource filtering.

    Returns:
        list: The particle's new schedule after movement and repair.
    """
    new_position = []

    for i in range(len(current_position)):
        current_item = current_position[i].copy()
        probability = random.random()  # Uniform random in [0.0, 1.0)

        if personal_best and probability < 0.35:
            # --- COGNITIVE COMPONENT (35% chance) ---
            # Move toward this particle's personal best position.
            # This represents the particle's "memory" of where it found
            # good solutions in the past.
            current_item = copy_assignment_from_best(
                current_item,
                personal_best[i]
            )

        elif global_best and probability < 0.75:
            # --- SOCIAL COMPONENT (40% chance) ---
            # Move toward the global best position found by the entire swarm.
            # This represents the swarm's collective knowledge.
            current_item = copy_assignment_from_best(
                current_item,
                global_best[i]
            )

        else:
            # --- EXPLORATION COMPONENT (25% chance) ---
            # Generate a completely random assignment for this slot.
            # This prevents the swarm from converging too early on a
            # sub-optimal solution (premature convergence).
            current_item = randomize_assignment(
                current_item,
                data,
                gender
            )

        new_position.append(current_item)

    # Repair any hard constraint violations introduced by the movement
    new_position = repair_schedule(new_position, data, gender)

    return new_position


# ===========================================================================
# SECTION 11: SCHEDULE SORTING (for display)
# ===========================================================================


def sort_schedule(schedule):
    """
    Sort the final schedule in a human-friendly order for display.

    Sorting order:
    1. Day of the week (Sunday=1 through Thursday=5, matching the Saudi work week).
    2. Period number (earliest to latest within each day).
    3. Course ID (alphabetical within the same time slot).

    Args:
        schedule: A list of assignment dictionaries.

    Returns:
        list: The same assignments sorted in display order.
    """
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
