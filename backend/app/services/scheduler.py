import random
import time
from typing import List
from sqlalchemy.orm import Session
from app.models.models import (
    Course, Section, Instructor, Room, Day, TimeSlot,
)
from app.schemas import ScheduleResult, ScheduleSlot


HARD_WEIGHT = 1.0
SOFT_WEIGHT = 0.1


def _load_data(db: Session):
    rooms = db.query(Room).all()
    instructors = db.query(Instructor).all()
    days = db.query(Day).all()
    time_slots = db.query(TimeSlot).filter(TimeSlot.slot_type == "Class").order_by(TimeSlot.slot_order).all()
    prayer_slots = db.query(TimeSlot).filter(TimeSlot.slot_type == "Prayer").all()
    male_rooms = [r for r in rooms if r.gender == "Male"]
    female_rooms = [r for r in rooms if r.gender == "Female"]
    return {
        "rooms": rooms,
        "instructors": instructors,
        "days": days,
        "time_slots": time_slots,
        "prayer_labels": {ts.label for ts in prayer_slots},
        "male_rooms": male_rooms,
        "female_rooms": female_rooms,
        "male_room_ids": {r.room_id for r in male_rooms},
        "female_room_ids": {r.room_id for r in female_rooms},
        "slot_order": {ts.label: ts.slot_order for ts in time_slots},
    }


def _get_sections_for_courses(db: Session, course_ids: List[int], preferred_gender: str):
    sections = (
        db.query(Section)
        .filter(Section.course_id.in_(course_ids), Section.is_archived == False)
        .all()
    )
    gender_sections = [s for s in sections if s.gender == preferred_gender]
    if gender_sections:
        sections = gender_sections
    return sections


def _get_eligible_instructors(data, section_gender, dept_name):
    pool = [i for i in data["instructors"] if i.gender == section_gender and i.department == dept_name]
    if not pool:
        pool = [i for i in data["instructors"] if i.gender == section_gender]
    if not pool:
        pool = data["instructors"]
    return pool


def _get_consecutive_pairs(data):
    slots = data["time_slots"]
    pairs = []
    for i in range(len(slots) - 1):
        pairs.append((slots[i].label, slots[i + 1].label))
    return pairs


def _create_random_schedule(sections, data, preferred_gender):
    schedule = []
    consecutive_pairs = _get_consecutive_pairs(data)
    slot_labels = [ts.label for ts in data["time_slots"]]

    for section in sections:
        course = section.course if hasattr(section, '_course_obj') else None
        dept_name = ""
        credits = 3
        course_code = ""
        course_name = ""
        is_lab = False

        if hasattr(section, '_course_obj') and section._course_obj:
            c = section._course_obj
            dept_name = c.department.name if c.department else ""
            credits = c.credits
            course_code = c.code
            course_name = c.name
            is_lab = c.is_lab

        gender_rooms = data["male_rooms"] if section.gender == "Male" else data["female_rooms"]
        if not gender_rooms:
            gender_rooms = data["rooms"]

        instructors = _get_eligible_instructors(data, section.gender, dept_name)
        instructor = random.choice(instructors)
        room = random.choice(gender_rooms)

        if credits <= 2:
            day1 = random.choice(data["days"])
            day2 = random.choice([d for d in data["days"] if d != day1] or data["days"])
            t1 = random.choice(slot_labels)
            t2 = random.choice(slot_labels)
            for day, t in [(day1, t1), (day2, t2)]:
                schedule.append({
                    "course_code": course_code,
                    "course_name": course_name,
                    "section_id": section.section_id,
                    "department": dept_name,
                    "gender": section.gender,
                    "level": section._course_obj.level if hasattr(section, '_course_obj') and section._course_obj else 1,
                    "credits": credits,
                    "is_lab": is_lab,
                    "instructor_id": instructor.instructor_id,
                    "instructor_name": instructor.name,
                    "room_id": room.room_id,
                    "room_capacity": room.capacity,
                    "room_type": room.room_type,
                    "day": day.code,
                    "time": t,
                    "enrolled": section.enrolled or 10,
                    "capacity": section.capacity,
                })
        elif credits == 3:
            day1 = random.choice(data["days"])
            day2 = random.choice(data["days"])
            if consecutive_pairs:
                pair = random.choice(consecutive_pairs)
                t_a, t_b = pair
            else:
                t_a = random.choice(slot_labels)
                t_b = random.choice(slot_labels)
            t_c = random.choice(slot_labels)
            for day, t in [(day1, t_a), (day1, t_b), (day2, t_c)]:
                schedule.append({
                    "course_code": course_code,
                    "course_name": course_name,
                    "section_id": section.section_id,
                    "department": dept_name,
                    "gender": section.gender,
                    "level": section._course_obj.level if hasattr(section, '_course_obj') and section._course_obj else 1,
                    "credits": credits,
                    "is_lab": is_lab,
                    "instructor_id": instructor.instructor_id,
                    "instructor_name": instructor.name,
                    "room_id": room.room_id,
                    "room_capacity": room.capacity,
                    "room_type": room.room_type,
                    "day": day.code,
                    "time": t,
                    "enrolled": section.enrolled or 10,
                    "capacity": section.capacity,
                })
        else:
            day1 = random.choice(data["days"])
            day2 = random.choice(data["days"])
            if consecutive_pairs:
                p1 = random.choice(consecutive_pairs)
                p2 = random.choice(consecutive_pairs)
            else:
                p1 = (random.choice(slot_labels), random.choice(slot_labels))
                p2 = (random.choice(slot_labels), random.choice(slot_labels))
            for day, t in [(day1, p1[0]), (day1, p1[1]), (day2, p2[0]), (day2, p2[1])]:
                schedule.append({
                    "course_code": course_code,
                    "course_name": course_name,
                    "section_id": section.section_id,
                    "department": dept_name,
                    "gender": section.gender,
                    "level": section._course_obj.level if hasattr(section, '_course_obj') and section._course_obj else 1,
                    "credits": credits,
                    "is_lab": is_lab,
                    "instructor_id": instructor.instructor_id,
                    "instructor_name": instructor.name,
                    "room_id": room.room_id,
                    "room_capacity": room.capacity,
                    "room_type": room.room_type,
                    "day": day.code,
                    "time": t,
                    "enrolled": section.enrolled or 10,
                    "capacity": section.capacity,
                })
    return schedule


def _calculate_fitness(schedule, data, objective="student"):
    conflicts = 0.0
    slot_order = data["slot_order"]
    prayer_labels = data["prayer_labels"]
    male_room_ids = data["male_room_ids"]
    female_room_ids = data["female_room_ids"]

    for i, si in enumerate(schedule):
        if si["time"] in prayer_labels:
            conflicts += HARD_WEIGHT
        if si["room_capacity"] < si.get("enrolled", 0):
            conflicts += HARD_WEIGHT
        if si["gender"] == "Female" and si["room_id"] in male_room_ids:
            conflicts += HARD_WEIGHT
        if si["gender"] == "Male" and si["room_id"] in female_room_ids:
            conflicts += HARD_WEIGHT

        for j in range(i + 1, len(schedule)):
            sj = schedule[j]
            if si["day"] == sj["day"] and si["time"] == sj["time"]:
                if si["instructor_id"] == sj["instructor_id"]:
                    conflicts += HARD_WEIGHT
                if si["room_id"] == sj["room_id"]:
                    conflicts += HARD_WEIGHT
                if (si["level"] == sj["level"] and si["gender"] == sj["gender"]
                        and si["course_code"] != sj["course_code"]
                        and not (si["is_lab"] and sj["is_lab"])):
                    conflicts += HARD_WEIGHT

    if objective == "student":
        level_days = {}
        for si in schedule:
            key = (si["level"], si["gender"])
            level_days.setdefault(key, set()).add(si["day"])
        for days in level_days.values():
            if len(days) > 3:
                conflicts += SOFT_WEIGHT * (len(days) - 3)

        last_slot = max(slot_order.values()) if slot_order else 99
        for si in schedule:
            idx = slot_order.get(si["time"], 0)
            if idx == last_slot:
                conflicts += SOFT_WEIGHT
            elif idx == last_slot - 1:
                conflicts += SOFT_WEIGHT * 0.5

    elif objective == "instructor":
        inst_days = {}
        for si in schedule:
            inst_days.setdefault(si["instructor_id"], set()).add(si["day"])
        for days in inst_days.values():
            if len(days) > 3:
                conflicts += SOFT_WEIGHT * (len(days) - 3)

    elif objective == "university":
        room_usage = {}
        for si in schedule:
            room_usage[si["room_id"]] = room_usage.get(si["room_id"], 0) + 1
        num_slots = len(data["days"]) * len(data["time_slots"])
        for used in room_usage.values():
            if num_slots > 0 and used / num_slots < 0.1:
                conflicts += SOFT_WEIGHT * 0.5

    return {"score": conflicts, "fitness": 1.0 / (1.0 + conflicts)}


def _mutate_schedule(schedule, data, mutation_rate=0.15):
    new_schedule = [item.copy() for item in schedule]
    slot_labels = [ts.label for ts in data["time_slots"]]
    for item in new_schedule:
        if random.random() < mutation_rate:
            item["day"] = random.choice(data["days"]).code
            item["time"] = random.choice(slot_labels)
        if random.random() < mutation_rate / 2:
            gender_rooms = data["male_rooms"] if item["gender"] == "Male" else data["female_rooms"]
            if not gender_rooms:
                gender_rooms = data["rooms"]
            room = random.choice(gender_rooms)
            item["room_id"] = room.room_id
            item["room_capacity"] = room.capacity
            item["room_type"] = room.room_type
        if random.random() < mutation_rate / 2:
            instructors = _get_eligible_instructors(data, item["gender"], item["department"])
            inst = random.choice(instructors)
            item["instructor_id"] = inst.instructor_id
            item["instructor_name"] = inst.name
    return new_schedule


def _run_ga(sections, data, objective, pop_size=60, mutation_rate=0.12, max_gens=500):
    population = [_create_random_schedule(sections, data, None) for _ in range(pop_size)]
    fitnesses = [_calculate_fitness(s, data, objective) for s in population]

    elite_count = max(2, pop_size // 20)
    tournament_size = 5

    for gen in range(max_gens):
        ranked = sorted(zip(population, fitnesses), key=lambda x: x[1]["score"])
        population = [s for s, _ in ranked]
        fitnesses = [f for _, f in ranked]

        if fitnesses[0]["score"] == 0:
            break

        new_pop = population[:elite_count]
        while len(new_pop) < pop_size:
            t1 = random.sample(list(zip(population, fitnesses)), tournament_size)
            t2 = random.sample(list(zip(population, fitnesses)), tournament_size)
            p1 = min(t1, key=lambda x: x[1]["score"])[0]
            p2 = min(t2, key=lambda x: x[1]["score"])[0]

            child = []
            for k in range(max(len(p1), len(p2))):
                if k < len(p1) and k < len(p2):
                    child.append(p1[k].copy() if random.random() > 0.5 else p2[k].copy())
                elif k < len(p1):
                    child.append(p1[k].copy())
                else:
                    child.append(p2[k].copy())

            child = _mutate_schedule(child, data, mutation_rate)
            new_pop.append(child)

        population = new_pop
        fitnesses = [_calculate_fitness(s, data, objective) for s in population]

    ranked = sorted(zip(population, fitnesses), key=lambda x: x[1]["score"])
    return [(s, f) for s, f in ranked[:3]]


def _run_pso(sections, data, preferred_gender, swarm_size=40, iterations=80):
    def copy_schedule(s):
        return [item.copy() for item in s]

    def move_toward(source, target, probability=0.45):
        new_s = copy_schedule(source)
        for i in range(min(len(new_s), len(target))):
            if random.random() < probability:
                new_s[i]["day"] = target[i]["day"]
                new_s[i]["time"] = target[i]["time"]
            if random.random() < probability / 2:
                new_s[i]["room_id"] = target[i]["room_id"]
                new_s[i]["room_capacity"] = target[i]["room_capacity"]
                new_s[i]["room_type"] = target[i].get("room_type", "")
            if random.random() < probability / 2:
                new_s[i]["instructor_id"] = target[i]["instructor_id"]
                new_s[i]["instructor_name"] = target[i]["instructor_name"]
        return new_s

    particles = [_create_random_schedule(sections, data, preferred_gender) for _ in range(swarm_size)]
    personal_best = [copy_schedule(p) for p in particles]
    personal_best_fitness = [_calculate_fitness(p, data, "student") for p in particles]

    best_idx = min(range(swarm_size), key=lambda i: personal_best_fitness[i]["score"])
    global_best = copy_schedule(personal_best[best_idx])
    global_best_fitness = personal_best_fitness[best_idx]

    for _ in range(iterations):
        for i in range(swarm_size):
            particle = particles[i]
            particle = move_toward(particle, personal_best[i], 0.35)
            particle = move_toward(particle, global_best, 0.50)
            particle = _mutate_schedule(particle, data, 0.18)

            fitness = _calculate_fitness(particle, data, "student")
            particles[i] = particle

            if fitness["score"] < personal_best_fitness[i]["score"]:
                personal_best[i] = copy_schedule(particle)
                personal_best_fitness[i] = fitness
                if fitness["score"] < global_best_fitness["score"]:
                    global_best = copy_schedule(particle)
                    global_best_fitness = fitness

    all_results = list(zip(
        [copy_schedule(p) for p in personal_best],
        personal_best_fitness,
    ))
    all_results.append((global_best, global_best_fitness))
    all_results.sort(key=lambda x: x[1]["score"])
    seen = set()
    unique = []
    for s, f in all_results:
        key = tuple(sorted((item["course_code"], item["day"], item["time"]) for item in s))
        if key not in seen:
            seen.add(key)
            unique.append((s, f))
        if len(unique) >= 3:
            break
    return unique[:3]


OBJ_META = {
    "university": {
        "label": "University-Optimized",
        "description": "Best overall schedule - minimises all hard and soft conflicts",
    },
    "instructor": {
        "label": "Instructor-Optimized",
        "description": "Compact teaching days, minimal gaps, balanced workloads",
    },
    "student": {
        "label": "Student-Optimized",
        "description": "Consecutive lectures, fewer travel days, no late slots",
    },
}


def run_schedule_generation(
    db: Session,
    selected_course_ids: List[int],
    algorithm: str = "GA",
    objective: str = "student",
    preferred_gender: str = "Male",
) -> List[ScheduleResult]:
    data = _load_data(db)
    sections = _get_sections_for_courses(db, selected_course_ids, preferred_gender)

    if not sections:
        return []

    courses_map = {}
    for sec in sections:
        if sec.course_id not in courses_map:
            course = db.query(Course).filter(Course.id == sec.course_id).first()
            courses_map[sec.course_id] = course
        sec._course_obj = courses_map[sec.course_id]

    if algorithm.upper() == "PSO":
        raw_results = _run_pso(sections, data, preferred_gender)
        objectives = ["student"] * len(raw_results)
    else:
        if objective == "all":
            raw_results = []
            objectives = []
            for obj in ["university", "instructor", "student"]:
                res = _run_ga(sections, data, obj)
                if res:
                    raw_results.append(res[0])
                    objectives.append(obj)
        else:
            raw_results = _run_ga(sections, data, objective)
            objectives = [objective] * len(raw_results)

    results = []
    for rank, (idx_data) in enumerate(zip(raw_results, objectives), 1):
        (schedule, fitness), obj = idx_data
        meta = OBJ_META.get(obj, {"label": obj.title(), "description": ""})
        slots = []
        for item in schedule:
            slots.append(ScheduleSlot(
                course_code=item["course_code"],
                course_name=item["course_name"],
                section_id=item["section_id"],
                department=item["department"],
                instructor_name=item["instructor_name"],
                room=item["room_id"],
                day=item["day"],
                time=item["time"],
                credits=item["credits"],
                level=item["level"],
                gender=item["gender"],
            ))
        results.append(ScheduleResult(
            rank=rank,
            label=meta["label"],
            description=meta["description"],
            fitness=round(fitness["fitness"], 4),
            conflicts=round(fitness["score"], 2),
            objective=obj,
            slots=slots,
        ))

    results.sort(key=lambda r: r.fitness, reverse=True)
    for i, r in enumerate(results, 1):
        r.rank = i

    return results[:3]
