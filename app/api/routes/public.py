import logging
from typing import List
from datetime import datetime
import hmac
import hashlib
import json
import base64

from fastapi import APIRouter, HTTPException, Path, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from app.db.session import get_db
from app.schemas.time_tracking import TimeEntry
from app.models.time_tracking import TimeEntry as TimeEntryModel, TimeEntryPaymentStatus
from app.core.logging import log_context
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/invoice/{token}", response_model=List[TimeEntry])
async def get_public_invoice(
    token: str = Path(..., description="The signed invoice token"),
    db: Session = Depends(get_db),
) -> List[TimeEntry]:
    """
    Get invoice data using a secure signed token.
    
    The token contains user_id, filters, and expiration information,
    all cryptographically signed to prevent tampering.
    """
    with log_context(action="get_public_invoice"):
        try:
            # Add padding if needed for base64 decoding
            padding = 4 - (len(token) % 4)
            if padding != 4:
                token += '=' * padding
            
            # Decode the token
            try:
                token_data = base64.urlsafe_b64decode(token.encode('utf-8'))
            except Exception as e:
                logger.warning(f"Invalid token format: {str(e)}")
                raise HTTPException(status_code=401, detail="Invalid token format")
            
            # Split payload and signature
            try:
                payload_bytes, signature = token_data.rsplit(b'.', 1)
            except ValueError:
                logger.warning("Token missing signature")
                raise HTTPException(status_code=401, detail="Invalid token structure")
            
            # Verify the signature
            expected_signature = hmac.new(
                settings.SECRET_KEY.encode('utf-8'),
                payload_bytes,
                hashlib.sha256
            ).digest()
            
            if not hmac.compare_digest(signature, expected_signature):
                logger.warning("Invalid token signature")
                raise HTTPException(status_code=401, detail="Invalid token signature")
            
            # Parse the payload
            try:
                payload = json.loads(payload_bytes.decode('utf-8'))
            except json.JSONDecodeError:
                logger.warning("Invalid token payload")
                raise HTTPException(status_code=401, detail="Invalid token payload")
            
            # Check expiration
            expires_at = datetime.fromisoformat(payload['expires_at'])
            if datetime.utcnow() > expires_at:
                logger.warning(f"Token expired at {expires_at}")
                raise HTTPException(status_code=401, detail="Token has expired")
            
            # Extract parameters
            user_id = payload['user_id']
            filters = payload['filters']
            
            # Build the query
            query = db.query(TimeEntryModel).filter(
                and_(
                    TimeEntryModel.user_id == user_id,
                    TimeEntryModel.end_time.isnot(None)  # Only completed entries
                )
            )
            
            # Apply date filters from token
            if filters.get('start_date'):
                start_date = datetime.fromisoformat(filters['start_date']).date()
                query = query.filter(TimeEntryModel.date >= start_date)
            
            if filters.get('end_date'):
                end_date = datetime.fromisoformat(filters['end_date']).date()
                query = query.filter(TimeEntryModel.date <= end_date)

            
            # Order by start_time descending (most recent first)
            query = query.order_by(desc(TimeEntryModel.start_time))
            
            # Execute query
            entries = query.all()
            
            logger.info(f"Retrieved {len(entries)} invoice entries for user {user_id} via public token")
            
            return entries
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving public invoice: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error") 