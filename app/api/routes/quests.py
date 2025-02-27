# app/api/endpoints/quests.py
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
        priority=quest_in.priority
    )
    
    quest = models.Quest(
        **quest_in.dict(),
        owner_id=current_user.id,
        exp_reward=exp_reward
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
    """
    Update a quest.
    """
    quest = db.query(models.Quest).filter(
        models.Quest.id == quest_id, models.Quest.owner_id == current_user.id
    ).first()
    
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    
    was_completed_before = quest.is_completed
    
    # Update quest fields
    for field in quest_in.__fields__:
        if field in quest_in.__dict__ and quest_in.__dict__[field] is not None:
            setattr(quest, field, quest_in.__dict__[field])
    
    # If quest was just completed, award XP to user
    if not was_completed_before and quest.is_completed:
        current_user.experience += quest.exp_reward
        # Check if user leveled up
        level_up = gamification_service.check_and_apply_level_up(db, current_user)
        # Check if any achievements were unlocked
        gamification_service.check_and_award_achievements(db, current_user)
    
    db.add(quest)
    db.commit()
    db.refresh(quest)
    return quest


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
    quest = db.query(models.Quest).filter(
        models.Quest.id == quest_id, models.Quest.owner_id == current_user.id
    ).first()
    
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
    quest = db.query(models.Quest).filter(
        models.Quest.id == quest_id, models.Quest.owner_id == current_user.id
    ).first()
    
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    
    db.delete(quest)
    db.commit()
    return quest