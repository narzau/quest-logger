from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, validator


# Base Schema
class SubscriptionBase(BaseModel):
    billing_cycle: Optional[str] = "monthly"  # "monthly" or "annual"
    promotional_code: Optional[str] = None


# DB Schema
class Subscription(SubscriptionBase):
    id: int
    user_id: int
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    status: Optional[str] = "active"
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    total_minutes_used_this_month: float
    monthly_minutes_limit: float
    allow_sharing: bool
    allow_exporting: bool
    priority_processing: bool
    advanced_ai_features: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Create/Update Schema
class SubscriptionCreate(SubscriptionBase):
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None


# Update Schema
class SubscriptionUpdate(BaseModel):
    status: Optional[str] = None
    billing_cycle: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    monthly_minutes_limit: Optional[float] = None
    promotional_code: Optional[str] = None


# User-facing subscription status
class SubscriptionStatus(BaseModel):
    status: str
    billing_cycle: str
    current_period_end: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    minutes_used: float
    minutes_limit: float
    features: dict
    payment_method: Optional[dict] = None

    class Config:
        from_attributes = True


# Schema for subscription pricing information
class PricingInfo(BaseModel):
    price: dict
    promotional_codes: List[dict]


# Schema for share link responses
class ShareLinkResponse(BaseModel):
    share_id: Optional[str]
    share_url: Optional[str]
    already_shared: bool = False


# Schema for unshare responses
class UnshareResponse(BaseModel):
    success: bool
    already_unshared: bool = False


# Schema for payment method response
class PaymentMethodResponse(BaseModel):
    id: int
    brand: str
    last4: str
    exp_month: int
    exp_year: int
    is_default: bool


# Schema for checkout session response
class CheckoutSessionResponse(BaseModel):
    session_id: str
    checkout_url: str


# Schema for webhook response
class WebhookResponse(BaseModel):
    status: str
    event_type: str


# Response for folders and tags
class FolderListResponse(BaseModel):
    folders: List[str]


class TagListResponse(BaseModel):
    tags: List[str]


class ExportResponse(BaseModel):
    content: bytes
    content_type: str
    filename: str
