"""
pso_algorithm.py - Particle Swarm Optimization for University Course Scheduling
================================================================================

This file implements the Particle Swarm Optimization (PSO) metaheuristic algorithm
adapted for the university course scheduling problem.

WHAT IS PSO?
------------
PSO is a population-based optimization algorithm inspired by the social behavior of
bird flocking or fish schooling. A group of candidate solutions (called "particles")
moves through the search space, with each particle adjusting its trajectory based on:
  1. Its own best-known position (personal/cognitive memory).
  2. The best position found by any particle in the swarm (global/social knowledge).

In the original continuous PSO, particles have velocity vectors. Here, because our
problem is DISCRETE (choosing days, rooms, professors for each class), we use a
probabilistic adaptation where each assignment is either:
  - Copied from the particle's personal best (35% chance)
  - Copied from the global best (40% chance)
  - Randomized for exploration (25% chance)

HOW IT WORKS IN THIS SCHEDULER:
--------------------------------
1. INITIALIZATION: Create `swarm_size` random schedules (particles). Each particle
   is a complete timetable assigning every course section to a day, period, room,
   and instructor.

2. EVALUATION: Score each particle using the fitness function (calculate_fitness)
   which penalizes hard constraint violations (HC1-HC7) heavily and soft constraint
   violations lightly. Lower score = better schedule.

3. TRACKING BESTS: Each particle remembers its own best-ever score ("personal best",
   abbreviated pbest). The swarm also tracks the single best score across all
   particles ("global best", abbreviated gbest).

4. MOVEMENT (ITERATION LOOP): For each iteration:
   a. Every particle generates a new position using update_particle_position(),
      which probabilistically blends its personal best, the global best, and
      random exploration.
   b. The new position is evaluated.
   c. If the new score is better than the particle's personal best, update pbest.
   d. If the new score is better than the global best, update gbest.

5. CONVERGENCE: The algorithm stops when:
   - An optimal solution is found (feasible + no gaps), OR
   - No improvement for `max_no_improvement` consecutive iterations, OR
   - The maximum number of iterations is reached.

6. OUTPUT: The global best schedule is returned, sorted for display.

PARAMETERS:
-----------
- swarm_size: Number of particles (candidate schedules). More particles explore
  more of the search space but take longer per iteration.
- iterations: Maximum number of iterations (generations of movement).
- max_no_improvement: Early stopping threshold - if no particle improves the
  global best for this many consecutive iterations, the algorithm stops.

RELATIONSHIP TO OTHER FILES:
-----------------------------
- common.py: Provides create_random_position(), calculate_fitness(),
  update_particle_position(), repair_schedule(), sort_schedule(), etc.
- scheduler.py: Calls run_pso_algorithm() and converts its output to API responses.
"""

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
    """
    Run the Particle Swarm Optimization algorithm to find an optimal schedule.

    This is the main entry point for PSO scheduling. It initializes a swarm of
    random schedules, then iteratively moves particles toward better solutions
    using personal best and global best information.

    Args:
        selected_courses:   List of course IDs to schedule.
        data:               Algorithm data dict (courses, rooms, professors, periods, days).
        gender:             Preferred gender for filtering resources (e.g., "Male").
        objective:          Optimization focus: "university", "instructor", or "student".
        swarm_size:         Number of particles in the swarm (default: 50).
        iterations:         Maximum iterations before stopping (default: 150).
        max_no_improvement: Stop if no improvement for this many iterations (default: 40).
        label:              Display label for logging (e.g., "PSO Student-Optimized").
        run_number:         Current run number (for multi-run logging).
        total_runs:         Total number of runs planned (for multi-run logging).

    Returns:
        tuple: (schedule, score, stats)
            - schedule (list): The best schedule found (list of assignment dicts),
              sorted by day/period/course for display.
            - score (float): The fitness score (lower = better; 0.0 = perfect).
            - stats (dict): Detailed breakdown of violations and metrics, including
              computation_time and iterations_completed.
    """
    start_time = time.time()

    # Default statistics returned if there are no courses to schedule
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

    # Edge case: no courses selected, return empty result
    if not selected_courses:
        return [], 0, empty_stats

    if run_number is not None:
        print(f"  Run {run_number}/{total_runs or '?'}")

    # ===================================================================
    # PHASE 1: SWARM INITIALIZATION
    # Create `swarm_size` random schedules. Each particle starts at a
    # random position in the search space.
    # ===================================================================

    # List of current positions (schedules) for all particles
    particles = []
    # Each particle's personal best position (copy of its best-ever schedule)
    personal_best_positions = []
    # Each particle's personal best fitness score
    personal_best_scores = []

    # The single best position found by ANY particle across the entire swarm
    global_best_position = None
    global_best_score = float("inf")  # Start at infinity so any real score is better
    global_best_stats = None

    for _ in range(swarm_size):
        # Create a random schedule (position) for this particle
        position = create_random_position(
            selected_courses,
            data,
            gender
        )

        # Evaluate how good this random schedule is
        score, stats = calculate_fitness(position, objective=objective, data=data)

        # Store the particle and initialize its personal best to its starting position
        particles.append(position)
        personal_best_positions.append(copy_position(position))
        personal_best_scores.append(score)

        # Update global best if this particle's initial position is the best so far
        if score < global_best_score:
            global_best_position = copy_position(position)
            global_best_score = score
            global_best_stats = stats

    # ===================================================================
    # PHASE 2: ITERATIVE OPTIMIZATION (the main PSO loop)
    # Each iteration: move all particles, evaluate, update bests.
    # ===================================================================

    # Counter for early stopping: how many iterations since last improvement
    no_improvement_count = 0
    iterations_completed = 0

    for iteration in range(iterations):
        iterations_completed = iteration + 1
        improved_this_iteration = False

        # --- Move each particle in the swarm ---
        for i in range(swarm_size):
            current_position = particles[i]

            # Generate a new position by blending personal best, global best,
            # and random exploration (see update_particle_position in common.py)
            new_position = update_particle_position(
                current_position=current_position,
                personal_best=personal_best_positions[i],
                global_best=global_best_position,
                data=data,
                gender=gender
            )

            # Evaluate the new position
            new_score, new_stats = calculate_fitness(new_position, objective=objective, data=data)

            # Update this particle's current position (always move, even if worse -
            # this is standard PSO behavior; the personal best tracks the best-ever)
            particles[i] = new_position

            # Update PERSONAL BEST if the new position is better than this
            # particle's previous best (cognitive/memory update)
            if new_score < personal_best_scores[i]:
                personal_best_positions[i] = copy_position(new_position)
                personal_best_scores[i] = new_score

            # Update GLOBAL BEST if the new position is the best found by
            # any particle ever (social/swarm knowledge update)
            if new_score < global_best_score:
                global_best_position = copy_position(new_position)
                global_best_score = new_score
                global_best_stats = new_stats
                improved_this_iteration = True

        # --- Early stopping check: track stagnation ---
        if improved_this_iteration:
            no_improvement_count = 0  # Reset counter on any improvement
        else:
            no_improvement_count += 1

        # --- Progress logging (every 10 iterations and first iteration) ---
        # Convert conflict score to a 0-1 fitness value for display
        # (higher = better, using inverse transformation)
        fitness_val = 1.0 / (1.0 + global_best_score) if global_best_score >= 0 else 0
        elapsed = time.time() - start_time

        if (iteration + 1) % 10 == 0 or iteration == 0:
            print(f"    Iter {iteration + 1:5d} | Conflicts: {global_best_score:6.2f} | Fitness: {fitness_val:.4f} | {elapsed:.1f}s")

        # --- Optimality check: stop if we found a perfect schedule ---
        # A schedule is optimal if it is feasible (no hard violations) AND
        # has no gaps in student/instructor schedules
        if global_best_stats and global_best_stats["feasible"]:
            if global_best_stats["student_gaps"] == 0 and global_best_stats["instructor_gaps"] == 0:
                print(f"    Iter {iteration + 1:5d} | OPTIMAL - no gaps | {elapsed:.1f}s")
                break

        # --- Stagnation check: stop if no improvement for too many iterations ---
        # This prevents wasting time when the algorithm has converged
        if no_improvement_count >= max_no_improvement:
            print(f"    Stopped: no improvement for {max_no_improvement} iterations")
            break

    # ===================================================================
    # PHASE 3: FINALIZE AND RETURN THE BEST SCHEDULE
    # ===================================================================

    # Sort the best schedule by day/period/course for human-readable display
    final_schedule = sort_schedule(global_best_position)

    # Re-evaluate the sorted schedule to get final accurate statistics
    final_score, final_stats = calculate_fitness(final_schedule, objective=objective, data=data)

    # Add timing and iteration metadata to the statistics
    final_stats["computation_time"] = round(time.time() - start_time, 3)
    final_stats["iterations_completed"] = iterations_completed

    # --- Final summary log ---
    elapsed = time.time() - start_time
    status = "FEASIBLE" if final_stats["feasible"] else f"{final_stats['hard_violations']} hard violations"
    print(f"    Result: {status} | Conflicts: {final_score:.2f} | Time: {elapsed:.2f}s | Iters: {iterations_completed}")
    print(f"    Hard: {final_stats['hard_violations']} | Soft: {final_stats['soft_cost']:.2f}")

    return final_schedule, final_score, final_stats
