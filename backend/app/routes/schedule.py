import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.models import User, SavedSchedule, Course
from app.schemas import ScheduleGenerateRequest, ScheduleResult, SaveScheduleRequest
from app.services.auth import get_current_user
from app.services.scheduler import run_schedule_generation

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


@router.post("/generate", response_model=List[ScheduleResult])
def generate_schedule(
    req: ScheduleGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not req.selected_course_ids:
        registered = current_user.registered_sections
        req.selected_course_ids = list(set(s.course_id for s in registered))

    if not req.selected_course_ids:
        raise HTTPException(status_code=400, detail="No courses selected. Register for courses first or provide course IDs.")

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
    saved = SavedSchedule(
        user_id=current_user.id,
        name=req.name,
        algorithm=req.algorithm,
        objective=req.objective,
        fitness=req.fitness,
        conflicts=req.conflicts,
        schedule_data=req.schedule_data,
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
    schedules = db.query(SavedSchedule).filter(SavedSchedule.user_id == current_user.id).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "algorithm": s.algorithm,
            "objective": s.objective,
            "fitness": s.fitness,
            "conflicts": s.conflicts,
            "schedule_data": json.loads(s.schedule_data),
        }
        for s in schedules
    ]


@router.delete("/saved/{schedule_id}")
def delete_saved_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    saved = db.query(SavedSchedule).filter(
        SavedSchedule.id == schedule_id,
        SavedSchedule.user_id == current_user.id,
    ).first()
    if not saved:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(saved)
    db.commit()
    return {"message": "Schedule deleted"}
