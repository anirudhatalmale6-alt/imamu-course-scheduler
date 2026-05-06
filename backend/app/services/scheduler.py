import os
import random
import time
import xml.etree.ElementTree as ET
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
    randomize_assignment,
    get_class_periods,
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

    student_count = 0
    xml_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "university.xml")
    if not os.path.exists(xml_path):
        xml_path = os.path.join(os.getcwd(), "university.xml")
    if os.path.exists(xml_path):
        try:
            root = ET.parse(xml_path).getroot()
            students_el = root.find("Students")
            if students_el is not None:
                for dept_el in students_el.findall("Department"):
                    for lv_el in dept_el.findall("Level"):
                        student_count += len(lv_el.findall("Student"))
        except Exception:
            pass

    return {
        "courses": courses,
        "rooms": rooms,
        "professors": professors,
        "periods": periods,
        "days": days,
        "student_count": student_count,
    }


def _print_data_summary(data, loaded_sections=None):
    day_codes = [d[:3].upper() for d in data["days"]]
    class_periods = get_class_periods(data)
    prayer_periods = [p for p in data["periods"] if p["type"].lower() == "prayer"]
    prayer_labels = [f"{p['start']}-{p['end']}" for p in prayer_periods]
    male_rooms = sum(1 for r in data["rooms"] if r["gender"] == "Male")
    female_rooms = sum(1 for r in data["rooms"] if r["gender"] == "Female")

    consecutive = 0
    all_periods = data["periods"]
    for i in range(len(all_periods) - 1):
        curr_type = str(all_periods[i].get("type", "")).lower()
        next_type = str(all_periods[i + 1].get("type", "")).lower()
        if curr_type == "class" and next_type == "class":
            consecutive += 1

    num_sections = loaded_sections if loaded_sections else sum(len(c["sections"]) for c in data["courses"])
    total_slots = len(data["rooms"]) * len(class_periods) * len(data["days"])

    all_credits = [c["credits"] for c in data["courses"] if c["credits"]]
    avg_credits = sum(all_credits) / len(all_credits) if all_credits else 3

    student_count = data.get("student_count", 0)

    print(f"Days       : {day_codes}")
    print(f"Slots      : {len(class_periods)} class slots (from XML)")
    print(f"Prayer     : {' | '.join(prayer_labels)}")
    print(f"Consecutive: {consecutive} valid pairs")
    print(f"Rooms : {len(data['rooms'])} ({male_rooms} M / {female_rooms} F)")
    print(f"Instructors: {len(data['professors'])} (hours-based load)")
    if student_count:
        print(f"Students: {student_count} loaded")
    print(f"Courses : {len(data['courses'])} (with prerequisites)")
    print(f"Sections: {num_sections}")
    print(f"Min loads: hours-based (avg_credits={avg_credits:.1f})")
    print(f"Depts   : {len(set(c['department'] for c in data['courses']))}")
    status = "OK" if num_sections <= total_slots else "WARNING: OVERLOADED"
    print(f"Slots   : {total_slots} -> {status}")


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
    pop_size=60, generations=500, max_no_improvement=100,
    run_number=None, total_runs=None,
):
    start_time = time.time()

    if not selected_codes:
        return [], 0, {}

    if run_number is not None:
        print(f"  Run {run_number}/{total_runs or '?'}")

    population = []
    scores = []

    for _ in range(pop_size):
        position = create_random_position(selected_codes, data, gender)
        score, stats = calculate_fitness(position, objective=objective, data=data)
        population.append(position)
        scores.append(score)

    best_idx = min(range(len(scores)), key=lambda i: scores[i])
    global_best = copy_position(population[best_idx])
    global_best_score = scores[best_idx]
    global_best_stats = None

    _, global_best_stats = calculate_fitness(global_best, objective=objective, data=data)

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
            for idx_c in range(len(child)):
                if random.random() < mutation_rate:
                    child[idx_c] = randomize_assignment(child[idx_c], data, gender)

            child = repair_schedule(child, data, gender)
            child_score, _ = calculate_fitness(child, objective=objective, data=data)
            new_population.append(child)
            new_scores.append(child_score)

        population = new_population
        scores = new_scores

        current_best_idx = min(range(len(scores)), key=lambda i: scores[i])
        if scores[current_best_idx] < global_best_score:
            global_best = copy_position(population[current_best_idx])
            global_best_score = scores[current_best_idx]
            _, global_best_stats = calculate_fitness(global_best, objective=objective, data=data)
            no_improvement = 0
        else:
            no_improvement += 1

        fitness_val = 1.0 / (1.0 + global_best_score) if global_best_score >= 0 else 0
        elapsed = time.time() - start_time

        if (gen + 1) % 100 == 0 or gen == 0:
            print(f"    Gen {gen + 1:5d} | Conflicts: {global_best_score:6.2f} | Fitness: {fitness_val:.4f} | {elapsed:.1f}s")

        if global_best_stats and global_best_stats["feasible"]:
            if global_best_stats["student_gaps"] == 0 and global_best_stats["instructor_gaps"] == 0:
                print(f"    Gen {gen + 1:5d} | OPTIMAL - no gaps | {elapsed:.1f}s")
                break

        if no_improvement >= max_no_improvement:
            print(f"    Stopped: no improvement for {max_no_improvement} generations")
            break

    final_schedule = sort_schedule(global_best)
    final_score, final_stats = calculate_fitness(final_schedule, objective=objective, data=data)
    final_stats["computation_time"] = round(time.time() - start_time, 3)
    final_stats["iterations_completed"] = iterations_completed

    elapsed = time.time() - start_time
    status = "FEASIBLE" if final_stats["feasible"] else f"{final_stats['hard_violations']} hard violations"
    print(f"    Result: {status} | Conflicts: {final_score:.2f} | Time: {elapsed:.2f}s | Gens: {iterations_completed}")
    print(f"    Hard: {final_stats['hard_violations']} | Soft: {final_stats['soft_cost']:.2f}")

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
    max_sections: int = 60,
) -> List[ScheduleResult]:
    data = _build_algorithm_data(db)
    selected_codes = _get_selected_course_codes(db, selected_course_ids)

    if not selected_codes:
        return []

    from app.algorithms.common import get_selected_course_sections
    loaded = get_selected_course_sections(selected_codes, data, preferred_gender, max_sections=max_sections)
    loaded_count = len(loaded)

    _print_data_summary(data, loaded_sections=loaded_count)
    print(f"Selected : {len(selected_codes)} courses ({', '.join(selected_codes)})")
    print(f"Algorithm: {algorithm.upper()}")

    results = []

    if algorithm.upper() == "PSO":
        meta = OBJ_META.get(objective, {"label": objective.title(), "description": ""})
        print(f"\n{'='*60}")
        print(f"  PSO {meta['label']}  (top 3)")
        print(f"{'='*60}")

        schedule, score, stats = run_pso_algorithm(
            selected_courses=selected_codes,
            data=data,
            gender=preferred_gender,
            objective=objective,
            swarm_size=50,
            iterations=150,
            max_no_improvement=40,
            label=f"PSO {meta['label']}",
            run_number=1,
            total_runs=3,
        )

        if schedule:
            slots = _schedule_to_slots(schedule)
            fitness_val = 1.0 / (1.0 + score) if score >= 0 else 0
            results.append(ScheduleResult(
                rank=1,
                label=f"PSO {meta['label']}",
                description=meta["description"],
                fitness=round(fitness_val, 4),
                conflicts=round(score, 2),
                objective=objective,
                slots=slots,
            ))

        for run in range(2):
            extra_schedule, extra_score, extra_stats = run_pso_algorithm(
                selected_courses=selected_codes,
                data=data,
                gender=preferred_gender,
                objective=objective,
                swarm_size=30,
                iterations=80,
                max_no_improvement=25,
                label=f"PSO Alternative {run + 1}",
                run_number=run + 2,
                total_runs=3,
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
                    objective=objective,
                    slots=extra_slots,
                ))

        results.sort(key=lambda r: r.fitness, reverse=True)
        for i, r in enumerate(results, 1):
            r.rank = i

    else:
        if objective == "all":
            for obj in ["university", "instructor", "student"]:
                meta = OBJ_META.get(obj, {"label": obj.title(), "description": ""})
                print(f"\n{'='*60}")
                print(f"  {meta['label']}  (top 1)")
                print(f"{'='*60}")

                schedule, score, stats = _run_ga_with_client_algorithm(
                    selected_codes, data, preferred_gender, objective=obj,
                    run_number=1, total_runs=1,
                )
                if schedule:
                    slots = _schedule_to_slots(schedule)
                    fitness_val = 1.0 / (1.0 + score) if score >= 0 else 0
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
            meta = OBJ_META.get(objective, {"label": objective.title(), "description": ""})
            print(f"\n{'='*60}")
            print(f"  {meta['label']}  (top 3)")
            print(f"{'='*60}")

            for run in range(3):
                schedule, score, stats = _run_ga_with_client_algorithm(
                    selected_codes, data, preferred_gender, objective=objective,
                    run_number=run + 1, total_runs=3,
                )
                if schedule:
                    slots = _schedule_to_slots(schedule)
                    fitness_val = 1.0 / (1.0 + score) if score >= 0 else 0
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

    print(f"\n{'='*60}")
    print(f"  Done. {len(results)} schedules generated.")
    print(f"{'='*60}\n")

    return results[:3]
