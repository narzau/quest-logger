from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Body, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_subscription_service
from app.models import User
from app.services.subscription_service import SubscriptionService
from app.core.config import settings
from app.core.constants import SubscriptionStatus, BillingCycle, FeatureFlag

router = APIRouter()


@router.get("/status")
async def get_subscription_status(
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: User = Depends(get_current_user),
):
    """Get the current user's subscription status"""
    return await subscription_service.get_subscription_status(current_user.id)


@router.get("/pricing")
async def get_pricing(
    subscription_service: SubscriptionService = Depends(get_subscription_service),
):
    """Get subscription pricing information"""
    return await subscription_service.get_pricing()


@router.post("/subscribe")
async def subscribe(
    billing_cycle: str = Body(BillingCycle.MONTHLY, embed=True),
    trial: bool = Body(False, embed=True),
    promotional_code: Optional[str] = Body(None, embed=True),
    payment_method_id: Optional[str] = Body(None, embed=True),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: User = Depends(get_current_user),
):
    """Subscribe to the paid tier"""
    if billing_cycle not in [BillingCycle.MONTHLY, BillingCycle.ANNUAL]:
        raise HTTPException(status_code=400, detail="Invalid billing cycle")

    # Require payment method for subscription unless it's a trial
    if not payment_method_id and not trial:
        raise HTTPException(
            status_code=400, detail="Payment method required for subscription"
        )

    return await subscription_service.start_subscription(
        current_user.id,
        current_user.email,
        current_user.username or f"User {current_user.id}",
        billing_cycle,
        trial,
        promotional_code,
        payment_method_id,
    )


@router.post("/unsubscribe")
async def unsubscribe(
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: User = Depends(get_current_user),
):
    """Cancel the current subscription"""
    return await subscription_service.cancel_subscription(current_user.id)


@router.post("/payment-method")
async def update_payment_method(
    payment_method_id: str = Body(..., embed=True),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: User = Depends(get_current_user),
):
    """Update payment method"""
    return await subscription_service.update_payment_method(
        current_user.id, payment_method_id
    )


@router.get("/payment-history")
async def get_payment_history(
    limit: int = 10,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: User = Depends(get_current_user),
):
    """Get payment history"""
    return await subscription_service.get_payment_history(current_user.id, limit)


@router.post("/billing-cycle")
async def change_billing_cycle(
    new_cycle: str = Body(..., embed=True),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: User = Depends(get_current_user),
):
    """Change billing cycle (monthly/annual)"""
    if new_cycle not in [BillingCycle.MONTHLY, BillingCycle.ANNUAL]:
        raise HTTPException(status_code=400, detail="Invalid billing cycle")

    return await subscription_service.change_billing_cycle(current_user.id, new_cycle)


@router.post("/apply-promo")
async def apply_promotional_code(
    code: str = Body(..., embed=True),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: User = Depends(get_current_user),
):
    """Apply a promotional code to subscription"""
    return await subscription_service.apply_promotional_code(current_user.id, code)


@router.post("/create-checkout")
async def create_checkout_session(
    request: Request,
    billing_cycle: str = Body(BillingCycle.MONTHLY, embed=True),
    promotional_code: Optional[str] = Body(None, embed=True),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: User = Depends(get_current_user),
):
    """Create a Stripe Checkout session for subscription payment"""
    # Create success and cancel URLs
    base_url = str(request.base_url).rstrip("/")
    frontend_url = settings.FRONTEND_URL

    success_url = (
        f"{frontend_url}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}"
    )
    cancel_url = f"{frontend_url}/subscription/cancel"

    return await subscription_service.create_checkout_session(
        current_user.id, success_url, cancel_url, promotional_code
    )


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
):
    """Handle Stripe webhook events"""
    # Get the webhook signature sent by Stripe
    signature = request.headers.get("stripe-signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")

    # Get the request body
    payload = await request.body()

    return await subscription_service.handle_webhook(payload, signature)


@router.get("/trial-notification")
async def get_trial_notification(
    current_user: User = Depends(get_current_user),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
):
    """
    Get notification information about the user's trial status.
    Returns warning messages if the trial is about to expire or has expired.
    """
    subscription = await subscription_service.get_subscription_status(current_user.id)

    # Default response
    response = {
        "has_notification": False,
        "message": "",
        "status": subscription["status"],
        "trial_end": subscription.get("trial_end"),
    }

    # Check if user is on a trial
    if subscription["status"] == SubscriptionStatus.TRIALING and subscription.get(
        "trial_end"
    ):
        # Calculate days remaining
        now = datetime.utcnow()
        trial_end = subscription["trial_end"]
        days_remaining = (trial_end - now).days

        # If less than 3 days remaining, show a warning
        if days_remaining <= 3:
            response["has_notification"] = True
            if days_remaining <= 0:
                response[
                    "message"
                ] = "Your trial ends today! Subscribe now to continue using all features."
            else:
                response[
                    "message"
                ] = f"Your trial ends in {days_remaining} {'day' if days_remaining == 1 else 'days'}. Subscribe now to avoid interruption."

    # Check if trial has expired
    elif subscription["status"] == SubscriptionStatus.TRIAL_EXPIRED:
        response["has_notification"] = True
        response[
            "message"
        ] = "Your trial has expired. Subscribe now to continue using all features."

    return response
