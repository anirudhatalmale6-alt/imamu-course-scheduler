import random
import time
from typing import List
from sqlalchemy.orm import Session
from app.models.models import (
    Course, Section, Instructor, Room, Day, TimeSlot,
)
from app.schemas import ScheduleResult, ScheduleSlot
from app.algorithms.common import (
    create_random_position,
    calculate_fitness,
    copy_position,
    repair_schedule,
    sort_schedule,
)
from app.algorithms.pso_algorithm import run_pso_algorithm


def _build_algorithm_data(db: Session):
    courses_db = db.query(Course).filter(Course.is_archived == False).all()
    rooms_db = db.query(Room).all()
    instructors_db = db.query(Instructor).all()
    time_slots_db = db.query(TimeSlot).order_by(TimeSlot.slot_order).all()
    days_db = db.query(Day).all()

    courses = []
    for c in courses_db:
        sections = []
        for s in c.sections:
            if not s.is_archived:
                sections.append({
                    "id": s.section_id,
                    "gender": s.gender,
                    "capacity": s.capacity,
                    "waitlist": 0,
                })
        prereq_codes = [p.code for p in c.prerequisites]
        courses.append({
            "id": c.code,
            "name": c.name,
            "department": c.department.name if c.department else "",
            "level": c.level,
            "credits": c.credits,
            "type": "Lab" if c.is_lab else "Lecture",
            "prerequisites": ",".join(prereq_codes) if prereq_codes else None,
            "sections": sections,
        })

    rooms = []
    for r in rooms_db:
        rooms.append({
            "id": r.room_id,
            "capacity": r.capacity,
            "gender": r.gender,
            "type": r.room_type,
        })

    professors = []
    for i in instructors_db:
        professors.append({
            "id": i.instructor_id,
            "name": i.name,
            "gender": i.gender,
            "department": i.department,
            "min_hours": i.min_hours,
            "max_hours": i.max_hours,
        })

    periods = []
    for ts in time_slots_db:
        periods.append({
            "id": ts.label,
            "type": ts.slot_type,
            "start": ts.start_time,
            "end": ts.end_time,
        })

    days = [d.name for d in days_db]

    return {
        "courses": courses,
        "rooms": rooms,
        "professors": professors,
        "periods": periods,
        "days": days,
    }


def _get_selected_course_codes(db: Session, course_ids: List[int]):
    courses = db.query(Course).filter(Course.id.in_(course_ids)).all()
    return [c.code for c in courses]


DAY_NAME_TO_CODE = {
    "Sunday": "SUN", "Monday": "MON", "Tuesday": "TUE",
    "Wednesday": "WED", "Thursday": "THU",
}


def _schedule_to_slots(schedule) -> List[ScheduleSlot]:
    slots = []
    for item in schedule:
        day_raw = item["day"]
        day_code = DAY_NAME_TO_CODE.get(day_raw, day_raw)

        time_raw = item["time"]
        time_label = time_raw.replace(" - ", "-").replace(" ", "")

        slots.append(ScheduleSlot(
            course_code=item["course_id"],
            course_name=item["course_name"],
            section_id=item["section_id"],
            department=item["department"],
            instructor_name=item["professor"],
            room=item["room"],
            day=day_code,
            time=time_label,
            credits=item["credits"],
            level=item.get("level", 1) if isinstance(item.get("level"), int) else 1,
            gender=item["section_gender"],
        ))
    return slots


def _run_ga_with_client_algorithm(
    selected_codes, data, gender, objective="student",
    pop_size=60, generations=200, max_no_improvement=40
):
    start_time = time.time()

    if not selected_codes:
        return [], 0, {}

    population = []
    scores = []

    for _ in range(pop_size):
        position = create_random_position(selected_codes, data, gender)
        score, stats = calculate_fitness(position)
        population.append(position)
        scores.append(score)

    best_idx = min(range(len(scores)), key=lambda i: scores[i])
    global_best = copy_position(population[best_idx])
    global_best_score = scores[best_idx]
    global_best_stats = None

    _, global_best_stats = calculate_fitness(global_best)

    no_improvement = 0
    iterations_completed = 0

    for gen in range(generations):
        iterations_completed = gen + 1

        ranked = sorted(range(len(population)), key=lambda i: scores[i])
        elite_count = max(2, pop_size // 10)

        new_population = []
        new_scores = []

        for idx in ranked[:elite_count]:
            new_population.append(copy_position(population[idx]))
            new_scores.append(scores[idx])

        while len(new_population) < pop_size:
            t1 = random.sample(ranked, min(5, len(ranked)))
            t2 = random.sample(ranked, min(5, len(ranked)))
            p1_idx = min(t1, key=lambda i: scores[i])
            p2_idx = min(t2, key=lambda i: scores[i])

            parent1 = population[p1_idx]
            parent2 = population[p2_idx]

            child = []
            for k in range(max(len(parent1), len(parent2))):
                if k < len(parent1) and k < len(parent2):
                    child.append(parent1[k].copy() if random.random() > 0.5 else parent2[k].copy())
                elif k < len(parent1):
                    child.append(parent1[k].copy())
                else:
                    child.append(parent2[k].copy())

            mutation_rate = 0.15
            for item in child:
                if random.random() < mutation_rate:
                    from app.algorithms.common import randomize_assignment
                    child[child.index(item)] = randomize_assignment(item, data, gender)

            child = repair_schedule(child, data, gender)
            child_score, _ = calculate_fitness(child)
            new_population.append(child)
            new_scores.append(child_score)

        population = new_population
        scores = new_scores

        current_best_idx = min(range(len(scores)), key=lambda i: scores[i])
        if scores[current_best_idx] < global_best_score:
            global_best = copy_position(population[current_best_idx])
            global_best_score = scores[current_best_idx]
            _, global_best_stats = calculate_fitness(global_best)
            no_improvement = 0
        else:
            no_improvement += 1

        if global_best_stats and global_best_stats["feasible"]:
            if global_best_stats["student_gaps"] == 0 and global_best_stats["instructor_gaps"] == 0:
                break

        if no_improvement >= max_no_improvement:
            break

    final_schedule = sort_schedule(global_best)
    final_score, final_stats = calculate_fitness(final_schedule)
    final_stats["computation_time"] = round(time.time() - start_time, 3)
    final_stats["iterations_completed"] = iterations_completed

    return final_schedule, final_score, final_stats


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
    data = _build_algorithm_data(db)
    selected_codes = _get_selected_course_codes(db, selected_course_ids)

    if not selected_codes:
        return []

    results = []

    if algorithm.upper() == "PSO":
        schedule, score, stats = run_pso_algorithm(
            selected_courses=selected_codes,
            data=data,
            gender=preferred_gender,
            swarm_size=50,
            iterations=150,
            max_no_improvement=40,
        )

        if schedule:
            slots = _schedule_to_slots(schedule)
            fitness_val = 1.0 / (1.0 + score) if score >= 0 else 0
            results.append(ScheduleResult(
                rank=1,
                label="PSO-Optimized",
                description="Particle Swarm Optimization - best schedule found",
                fitness=round(fitness_val, 4),
                conflicts=round(score, 2),
                objective="student",
                slots=slots,
            ))

        for run in range(2):
            extra_schedule, extra_score, extra_stats = run_pso_algorithm(
                selected_courses=selected_codes,
                data=data,
                gender=preferred_gender,
                swarm_size=30,
                iterations=80,
                max_no_improvement=25,
            )
            if extra_schedule:
                extra_slots = _schedule_to_slots(extra_schedule)
                extra_fitness = 1.0 / (1.0 + extra_score) if extra_score >= 0 else 0
                results.append(ScheduleResult(
                    rank=run + 2,
                    label=f"PSO Alternative {run + 1}",
                    description="Alternative schedule from PSO",
                    fitness=round(extra_fitness, 4),
                    conflicts=round(extra_score, 2),
                    objective="student",
                    slots=extra_slots,
                ))

        results.sort(key=lambda r: r.fitness, reverse=True)
        for i, r in enumerate(results, 1):
            r.rank = i

    else:
        if objective == "all":
            for obj in ["university", "instructor", "student"]:
                schedule, score, stats = _run_ga_with_client_algorithm(
                    selected_codes, data, preferred_gender, objective=obj
                )
                if schedule:
                    slots = _schedule_to_slots(schedule)
                    fitness_val = 1.0 / (1.0 + score) if score >= 0 else 0
                    meta = OBJ_META.get(obj, {"label": obj.title(), "description": ""})
                    results.append(ScheduleResult(
                        rank=len(results) + 1,
                        label=meta["label"],
                        description=meta["description"],
                        fitness=round(fitness_val, 4),
                        conflicts=round(score, 2),
                        objective=obj,
                        slots=slots,
                    ))
        else:
            for run in range(3):
                schedule, score, stats = _run_ga_with_client_algorithm(
                    selected_codes, data, preferred_gender, objective=objective
                )
                if schedule:
                    slots = _schedule_to_slots(schedule)
                    fitness_val = 1.0 / (1.0 + score) if score >= 0 else 0
                    meta = OBJ_META.get(objective, {"label": objective.title(), "description": ""})
                    results.append(ScheduleResult(
                        rank=run + 1,
                        label=meta["label"] if run == 0 else f"{meta['label']} (Alt {run})",
                        description=meta["description"],
                        fitness=round(fitness_val, 4),
                        conflicts=round(score, 2),
                        objective=objective,
                        slots=slots,
                    ))

        results.sort(key=lambda r: r.fitness, reverse=True)
        for i, r in enumerate(results, 1):
            r.rank = i

    return results[:3]
