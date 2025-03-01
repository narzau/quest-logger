# app/api/endpoints/quests.py
import datetime

from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.api import deps
from app.services import gamification_service

router = APIRouter()


@router.get("/", response_model=List[schemas.Quest])
def read_quests(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    quest_type: Optional[str] = Query(None),
    is_completed: Optional[bool] = Query(None),
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve quests.
    """
    query = db.query(models.Quest).filter(models.Quest.owner_id == current_user.id)

    if quest_type:
        query = query.filter(models.Quest.quest_type == quest_type)
    if is_completed is not None:
        query = query.filter(models.Quest.is_completed == is_completed)

    quests = query.offset(skip).limit(limit).all()
    return quests


@router.post("/", response_model=schemas.Quest)
def create_quest(
    *,
    db: Session = Depends(deps.get_db),
    quest_in: schemas.QuestCreate,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create new quest.
    """
    # Calculate exp reward based on quest properties
    exp_reward = gamification_service.calculate_quest_exp_reward(
        rarity=quest_in.rarity,
        quest_type=quest_in.quest_type,
        priority=quest_in.priority,
    )
    quest = models.Quest(
        **quest_in.model_dump(exclude={"exp_reward"}),
        owner_id=current_user.id,
        exp_reward=exp_reward,
    )
    db.add(quest)
    db.commit()
    db.refresh(quest)
    return quest


@router.put("/{quest_id}", response_model=schemas.Quest)
def update_quest(
    *,
    db: Session = Depends(deps.get_db),
    quest_id: int,
    quest_in: schemas.QuestUpdate,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    quest = (
        db.query(models.Quest)
        .filter(models.Quest.id == quest_id, models.Quest.owner_id == current_user.id)
        .first()
    )

    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")

    was_completed_before = quest.is_completed
    completion_time = datetime.datetime.now(datetime.timezone.utc)

    # Update quest fields
    for field in quest_in.dict(exclude_unset=True):
        setattr(quest, field, getattr(quest_in, field))

    if not was_completed_before and quest.is_completed:
        quest.completed_at = completion_time
        current_user.experience += quest.exp_reward
        db.add(current_user)
        db.commit()  # Commit XP update first

        # Check for level-based achievements
        level_up = gamification_service.check_and_apply_level_up(db, current_user)

        # Update quest-specific achievements
        update_quest_achievements(db, current_user, quest, completion_time)

        # Explicit achievement check
        gamification_service.check_achievements(db, current_user)

    db.add(quest)
    db.commit()
    db.refresh(quest)
    return quest


def update_quest_achievements(
    db: Session, user: models.User, quest: models.Quest, completion_time: datetime
):
    # General quest completion
    gamification_service.update_progress_and_check_achievements(
        db=db, user=user, criterion_type="quests_completed", amount=1
    )

    # Type-specific achievements
    if quest.quest_type == models.QuestType.BOSS:
        gamification_service.update_progress_and_check_achievements(
            db=db, user=user, criterion_type="boss_quests_completed", amount=1
        )
    elif quest.quest_type == models.QuestType.EPIC:
        gamification_service.update_progress_and_check_achievements(
            db=db, user=user, criterion_type="legendary_quests_completed", amount=1
        )

    # Time-based achievements
    completion_hour = completion_time.hour
    if completion_hour < 8:
        gamification_service.update_progress_and_check_achievements(
            db=db, user=user, criterion_type="early_morning_completion", amount=1
        )
    elif completion_hour >= 22:
        gamification_service.update_progress_and_check_achievements(
            db=db, user=user, criterion_type="late_night_completion", amount=1
        )

    # Rarity-based achievements
    if quest.rarity == models.QuestRarity.LEGENDARY:
        gamification_service.update_progress_and_check_achievements(
            db=db, user=user, criterion_type="legendary_quests_completed", amount=1
        )


@router.get("/{quest_id}", response_model=schemas.Quest)
def read_quest(
    *,
    db: Session = Depends(deps.get_db),
    quest_id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get quest by ID.
    """
    quest = (
        db.query(models.Quest)
        .filter(models.Quest.id == quest_id, models.Quest.owner_id == current_user.id)
        .first()
    )

    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")

    return quest


@router.delete("/{quest_id}", response_model=schemas.Quest)
def delete_quest(
    *,
    db: Session = Depends(deps.get_db),
    quest_id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Delete a quest.
    """
    quest = (
        db.query(models.Quest)
        .filter(models.Quest.id == quest_id, models.Quest.owner_id == current_user.id)
        .first()
    )

    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")

    db.delete(quest)
    db.commit()
    return quest
