"""
Schedule Generation API Routes
==============================
This file defines the REST API endpoints for generating, saving, retrieving,
and deleting course schedules.

Endpoints overview:
  - POST   /api/schedule/generate          - Run the scheduling algorithm to produce
                                             conflict-free timetable options.
  - POST   /api/schedule/save              - Save a generated schedule for later use.
  - GET    /api/schedule/saved             - List all schedules saved by the current user.
  - DELETE /api/schedule/saved/{id}        - Delete a saved schedule.

The generation endpoint delegates to the scheduler service, which uses
optimization algorithms (e.g., genetic algorithm) to find valid timetables
that minimize conflicts like time overlaps and room double-bookings.
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.models import User, SavedSchedule, Course
from app.schemas import ScheduleGenerateRequest, ScheduleResult, SaveScheduleRequest
from app.services.auth import get_current_user
from app.services.scheduler import run_schedule_generation

# All schedule endpoints live under the "/api/schedule" prefix.
router = APIRouter(prefix="/api/schedule", tags=["schedule"])


@router.post("/generate", response_model=List[ScheduleResult])
def generate_schedule(
    req: ScheduleGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate one or more optimized schedule options for the selected courses.

    If no course IDs are provided in the request, the system automatically
    uses the courses from the user's current registrations.

    Parameters (from ScheduleGenerateRequest):
      - selected_course_ids: List of course IDs to schedule.
      - algorithm: Which algorithm to use (e.g., "genetic", "greedy").
      - objective: Optimization goal (e.g., "minimize_gaps", "early_classes").
      - preferred_gender: Gender filter for section selection; defaults to
        the current user's gender if not specified.

    Returns a list of ScheduleResult objects, each representing a complete
    timetable option with a fitness score and conflict count.
    """
    # If no courses were explicitly selected, fall back to the user's registered courses
    if not req.selected_course_ids:
        registered = current_user.registered_sections
        # Extract unique course IDs from the user's registered sections
        req.selected_course_ids = list(set(s.course_id for s in registered))

    # Ensure we have at least one course to schedule
    if not req.selected_course_ids:
        raise HTTPException(status_code=400, detail="No courses selected. Register for courses first or provide course IDs.")

    # Delegate to the scheduler service which runs the optimization algorithm
    results = run_schedule_generation(
        db=db,
        selected_course_ids=req.selected_course_ids,
        algorithm=req.algorithm,
        objective=req.objective,
        preferred_gender=req.preferred_gender or current_user.gender,
    )
    return results


@router.post("/save")
def save_schedule(
    req: SaveScheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Save a generated schedule to the database for the current user.

    The schedule data (section assignments, time slots, rooms) is stored
    as a JSON string so the user can reload it later without re-running
    the generation algorithm.
    """
    saved = SavedSchedule(
        user_id=current_user.id,
        name=req.name,
        algorithm=req.algorithm,
        objective=req.objective,
        fitness=req.fitness,
        conflicts=req.conflicts,
        schedule_data=req.schedule_data,  # JSON string of the full timetable
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)
    return {"message": "Schedule saved", "id": saved.id}


@router.get("/saved")
def get_saved_schedules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve all schedules that the current user has previously saved.

    Each saved schedule includes its metadata (name, algorithm, fitness score,
    conflict count) and the full schedule data parsed from JSON back into
    a Python dict for the frontend to render.
    """
    # Only fetch schedules belonging to the currently authenticated user
    schedules = db.query(SavedSchedule).filter(SavedSchedule.user_id == current_user.id).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "algorithm": s.algorithm,
            "objective": s.objective,
            "fitness": s.fitness,
            "conflicts": s.conflicts,
            "schedule_data": json.loads(s.schedule_data),  # Deserialize JSON string to dict
        }
        for s in schedules
    ]


@router.delete("/saved/{schedule_id}")
def delete_saved_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a saved schedule by its ID.

    The query filters by both schedule_id AND user_id to ensure a user
    can only delete their own schedules (not another user's).
    """
    saved = db.query(SavedSchedule).filter(
        SavedSchedule.id == schedule_id,
        SavedSchedule.user_id == current_user.id,  # Ownership check
    ).first()
    if not saved:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(saved)
    db.commit()
    return {"message": "Schedule deleted"}
