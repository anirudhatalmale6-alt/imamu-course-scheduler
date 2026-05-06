import time

from app.algorithms.common import (
    create_random_position,
    calculate_fitness,
    update_particle_position,
    sort_schedule,
    copy_position
)


def run_pso_algorithm(
    selected_courses,
    data,
    gender,
    objective="student",
    swarm_size=50,
    iterations=150,
    max_no_improvement=40,
    label="PSO",
    run_number=None,
    total_runs=None,
):
    start_time = time.time()

    empty_stats = {
        "fitness_score": 0,
        "hard_violations": 0,
        "soft_cost": 0,
        "feasible": False,
        "instructor_double_booking": 0,
        "room_double_booking": 0,
        "student_group_conflict": 0,
        "capacity_issues": 0,
        "prayer_time_violations": 0,
        "gender_separation_violations": 0,
        "prerequisite_overlap": 0,
        "student_gaps": 0,
        "student_days": 0,
        "instructor_gaps": 0,
        "instructor_days": 0,
        "late_slots": 0,
        "room_utilization_penalty": 0,
        "workload_balance_penalty": 0,
        "instructor_min_load_penalty": 0,
        "computation_time": 0,
        "iterations_completed": 0
    }

    if not selected_courses:
        return [], 0, empty_stats

    if run_number is not None:
        print(f"  Run {run_number}/{total_runs or '?'}")

    particles = []
    personal_best_positions = []
    personal_best_scores = []

    global_best_position = None
    global_best_score = float("inf")
    global_best_stats = None

    for _ in range(swarm_size):
        position = create_random_position(
            selected_courses,
            data,
            gender
        )

        score, stats = calculate_fitness(position, objective=objective, data=data)

        particles.append(position)
        personal_best_positions.append(copy_position(position))
        personal_best_scores.append(score)

        if score < global_best_score:
            global_best_position = copy_position(position)
            global_best_score = score
            global_best_stats = stats

    no_improvement_count = 0
    iterations_completed = 0

    for iteration in range(iterations):
        iterations_completed = iteration + 1
        improved_this_iteration = False

        for i in range(swarm_size):
            current_position = particles[i]

            new_position = update_particle_position(
                current_position=current_position,
                personal_best=personal_best_positions[i],
                global_best=global_best_position,
                data=data,
                gender=gender
            )

            new_score, new_stats = calculate_fitness(new_position, objective=objective, data=data)

            particles[i] = new_position

            if new_score < personal_best_scores[i]:
                personal_best_positions[i] = copy_position(new_position)
                personal_best_scores[i] = new_score

            if new_score < global_best_score:
                global_best_position = copy_position(new_position)
                global_best_score = new_score
                global_best_stats = new_stats
                improved_this_iteration = True

        if improved_this_iteration:
            no_improvement_count = 0
        else:
            no_improvement_count += 1

        fitness_val = 1.0 / (1.0 + global_best_score) if global_best_score >= 0 else 0
        elapsed = time.time() - start_time

        if (iteration + 1) % 10 == 0 or iteration == 0:
            print(f"    Iter {iteration + 1:5d} | Conflicts: {global_best_score:6.2f} | Fitness: {fitness_val:.4f} | {elapsed:.1f}s")

        if global_best_stats and global_best_stats["feasible"]:
            if global_best_stats["student_gaps"] == 0 and global_best_stats["instructor_gaps"] == 0:
                print(f"    Iter {iteration + 1:5d} | OPTIMAL - no gaps | {elapsed:.1f}s")
                break

        if no_improvement_count >= max_no_improvement:
            print(f"    Stopped: no improvement for {max_no_improvement} iterations")
            break

    final_schedule = sort_schedule(global_best_position)

    final_score, final_stats = calculate_fitness(final_schedule, objective=objective, data=data)

    final_stats["computation_time"] = round(time.time() - start_time, 3)
    final_stats["iterations_completed"] = iterations_completed

    elapsed = time.time() - start_time
    status = "FEASIBLE" if final_stats["feasible"] else f"{final_stats['hard_violations']} hard violations"
    print(f"    Result: {status} | Conflicts: {final_score:.2f} | Time: {elapsed:.2f}s | Iters: {iterations_completed}")
    print(f"    Hard: {final_stats['hard_violations']} | Soft: {final_stats['soft_cost']:.2f}")

    return final_schedule, final_score, final_stats
