# app/repositories/base_repository.py
from typing import TypeVar, Generic, Type, List, Optional, Any, Dict, Union
from sqlalchemy.orm import Session
from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base) # type: ignore


class BaseRepository(Generic[ModelType]):
    """
    Base repository with common CRUD operations.
    Extend this class for specific models.
    """
    def __init__(self, model: Type[ModelType], db: Session):
        self.model = model
        self.db = db

    def get(self, id: Any) -> Optional[ModelType]:
        """Get a single record by ID."""
        return self.db.query(self.model).filter(self.model.id == id).first()
    
    def get_by(self, **kwargs) -> Optional[ModelType]:
        """Get a single record by arbitrary filters."""
        query = self.db.query(self.model)
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)
        return query.first()
    
    def list(
        self, 
        *,
        skip: int = 0, 
        limit: int = 100, 
        **filters
    ) -> List[ModelType]:
        """Get multiple records with optional filtering."""
        query = self.db.query(self.model)
        
        # Apply filters
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)
        
        return query.offset(skip).limit(limit).all()
    
    def create(self, obj_in: Union[Dict[str, Any], BaseModel]) -> ModelType:
        """Create a new record."""
        if isinstance(obj_in, BaseModel):
            obj_in_data = jsonable_encoder(obj_in)
        else:
            obj_in_data = obj_in
            
        db_obj = self.model(**obj_in_data)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def update(
        self, 
        db_obj: ModelType, 
        obj_in: Union[Dict[str, Any], BaseModel]
    ) -> ModelType:
        """Update an existing record."""
        if isinstance(obj_in, BaseModel):
            update_data = obj_in.dict(exclude_unset=True)
        else:
            update_data = obj_in
            
        for field in update_data:
            if hasattr(db_obj, field):
                setattr(db_obj, field, update_data[field])
                
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def delete(self, id: Any) -> bool:
        """Delete a record by ID."""
        obj = self.db.query(self.model).get(id)
        if obj:
            self.db.delete(obj)
            self.db.commit()
            return True
        return False
    
    def save(self, obj: ModelType) -> ModelType:
        """Save an already instantiated model object."""
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj