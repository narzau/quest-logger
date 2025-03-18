import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.subscription import (
    SubscriptionCreate, 
    SubscriptionUpdate, 
    SubscriptionStatus,
    PricingInfo,
    PaymentMethodResponse,
    CheckoutSessionResponse,
    WebhookResponse
)
from app.integrations.payment import get_stripe_client
from app.core.constants import (
    SubscriptionStatus as SubscriptionStatusEnum,
    BillingCycle,
    WebhookEventType,
)


class SubscriptionService:
    """Service for subscription operations"""

    def __init__(self, db: Session):
        self.db = db
        self.repository = SubscriptionRepository(db)
        self.stripe_client = get_stripe_client()

    async def get_subscription_status(self, user_id: int) -> SubscriptionStatus:
        """Get user's subscription status"""
        await asyncio.gather(
            self.check_and_update_expired_trials(),
            self.check_and_update_expired_subscriptions()
        )
        
        subscription_status = self.repository.get_subscription_status(user_id)

        return SubscriptionStatus(**subscription_status)

    async def check_and_update_expired_trials(self) -> int:
        """
        Check for all expired trials and update their status.
        Returns the number of updated subscriptions.
        This would typically be called by a scheduled job.
        """
        expired_trials = self.repository.get_expired_trials()

        updated_count = 0
        for subscription in expired_trials:
            update_data = SubscriptionUpdate(status=SubscriptionStatusEnum.TRIAL_EXPIRED)
            self.repository.update_subscription(subscription, update_data)
            updated_count += 1

        return updated_count

    async def check_and_update_expired_subscriptions(self) -> int:
        """
        Check for all expired active subscriptions and update their status to past_due.
        Returns the number of updated subscriptions.
        This would typically be called by a scheduled job.
        """
        expired_subscriptions = self.repository.get_expired_active_subscriptions()

        updated_count = 0
        for subscription in expired_subscriptions:
            update_data = SubscriptionUpdate(status=SubscriptionStatusEnum.PAST_DUE)
            self.repository.update_subscription(subscription, update_data)
            updated_count += 1

        return updated_count

    async def get_pricing(self) -> PricingInfo:
        """Get subscription pricing information"""
        pricing_data = {
            "price": {
                "display_name": "Quest Logger Pro",
                "description": "Full featured with ample recording time",
                "monthly_price": 9.99,
                "annual_price": 99.99,
                "monthly_minutes_limit": 120,
                "features": [
                    "2 hour monthly recording limit",
                    "Advanced AI processing",
                    "Priority transcription",
                    "Export to multiple formats",
                    "Public sharing of notes",
                ],
            },
            "promotional_codes": [
                {
                    "code": "WELCOME",
                    "description": "20% off your first payment",
                    "percent_off": 20,
                }
            ],
        }
        return PricingInfo(**pricing_data)

    async def start_subscription(
        self,
        user_id: int,
        user_email: str,
        user_name: str,
        billing_cycle: BillingCycle = BillingCycle.MONTHLY,
        trial: bool = False,
        promotional_code: str = None,
        payment_method_id: str = None,
    ) -> SubscriptionStatus:
        """Start a new subscription for a user"""
        # Check if user already has a subscription
        existing_subscription = self.repository.get_by_user_id(user_id)

        if (
            existing_subscription
            and existing_subscription.status == SubscriptionStatusEnum.ACTIVE
        ):
            # User already has an active subscription
            subscription_status = self.repository.get_subscription_status(user_id)
            return SubscriptionStatus(**subscription_status)

        # Create Stripe customer
        customer = await self.stripe_client.create_customer(user_email, user_name)

        # Set up payment method if provided
        if payment_method_id:
            await self.stripe_client.create_payment_method(
                customer["id"], payment_method_id
            )

        # Create Stripe subscription with trial if requested
        trial_days = 7 if trial else 0
        subscription = await self.stripe_client.create_subscription(
            customer["id"], billing_cycle, trial_days, promotional_code
        )

        # Create local subscription record
        subscription_data = SubscriptionCreate(
            billing_cycle=billing_cycle,
            promotional_code=promotional_code,
            stripe_subscription_id=subscription["id"],
            stripe_customer_id=customer["id"],
        )

        db_subscription = self.repository.create_subscription(
            user_id, subscription_data
        )

        # Update subscription with period dates from Stripe
        update_data = SubscriptionUpdate(
            current_period_start=datetime.fromtimestamp(
                subscription["current_period_start"]
            ),
            current_period_end=datetime.fromtimestamp(
                subscription["current_period_end"]
            ),
            trial_end=datetime.fromtimestamp(subscription["trial_end"])
            if subscription.get("trial_end")
            else None,
            status=subscription["status"],
        )

        self.repository.update_subscription(db_subscription, update_data)

        # Add payment method if provided
        if payment_method_id:
            payment_method = await self.stripe_client.get_payment_method(
                payment_method_id
            )
            card = payment_method["card"]

            self.repository.add_payment_method(
                db_subscription.id,
                payment_method_id,
                card["brand"],
                card["last4"],
                card["exp_month"],
                card["exp_year"],
                True,
            )

        subscription_status = self.repository.get_subscription_status(user_id)
        return SubscriptionStatus(**subscription_status)

    async def cancel_subscription(self, user_id: int) -> SubscriptionStatus:
        """Cancel a user's subscription"""
        subscription = self.repository.get_by_user_id(user_id)

        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        # Cancel in Stripe
        if subscription.stripe_subscription_id:
            cancel_result = await self.stripe_client.cancel_subscription(
                subscription.stripe_subscription_id
            )

            # Update local subscription status
            update_data = SubscriptionUpdate(status=SubscriptionStatusEnum.CANCELED)

            self.repository.update_subscription(subscription, update_data)

        subscription_status = self.repository.get_subscription_status(user_id)
        return SubscriptionStatus(**subscription_status)

    async def change_billing_cycle(
        self, user_id: int, new_cycle: BillingCycle
    ) -> SubscriptionStatus:
        """Change a user's billing cycle between monthly and annual"""
        subscription = self.repository.get_by_user_id(user_id)

        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        if subscription.billing_cycle == new_cycle:
            subscription_status = self.repository.get_subscription_status(user_id)
            return SubscriptionStatus(**subscription_status)

        # This would typically be handled by Stripe's Billing portal
        # or by creating a new subscription with the new cycle
        # For simplicity, we'll just update our local record
        update_data = SubscriptionUpdate(
            billing_cycle=new_cycle,
        )

        self.repository.update_subscription(subscription, update_data)

        subscription_status = self.repository.get_subscription_status(user_id)
        return SubscriptionStatus(**subscription_status)

    async def apply_promotional_code(self, user_id: int, code: str) -> SubscriptionStatus:
        """Apply a promotional code to a user's subscription"""
        subscription = self.repository.get_by_user_id(user_id)

        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        # Check if code exists and is valid
        promo = self.repository.get_promotional_code(code)

        if not promo:
            raise HTTPException(
                status_code=404, detail="Invalid or expired promotional code"
            )

        # Check if code has reached max redemptions
        if promo.max_redemptions and promo.times_redeemed >= promo.max_redemptions:
            raise HTTPException(
                status_code=400, detail="This promotional code has been fully redeemed"
            )

        # Check if it has expired
        if promo.expires_at and promo.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=400, detail="This promotional code has expired"
            )

        # Apply to subscription
        update_data = SubscriptionUpdate(promotional_code=code)
        self.repository.update_subscription(subscription, update_data)

        # Update promo usage count using the repository method
        self.repository.increment_promo_code_usage(promo)

        # In a real implementation, this would use Stripe's API

        subscription_status = self.repository.get_subscription_status(user_id)
        return SubscriptionStatus(**subscription_status)

    async def update_payment_method(
        self, user_id: int, payment_method_id: str
    ) -> PaymentMethodResponse:
        """Update a user's payment method"""
        subscription = self.repository.get_by_user_id(user_id)

        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        if not subscription.stripe_customer_id:
            raise HTTPException(status_code=400, detail="Missing customer information")

        # Attach payment method to customer in Stripe
        stripe_payment_method = await self.stripe_client.create_payment_method(
            subscription.stripe_customer_id, payment_method_id
        )

        card = stripe_payment_method["card"]

        # Add to database
        payment_method = self.repository.add_payment_method(
            subscription.id,
            payment_method_id,
            card["brand"],
            card["last4"],
            card["exp_month"],
            card["exp_year"],
            True,  # Make it the default
        )

        payment_method_data = {
            "id": payment_method.id,
            "brand": payment_method.brand,
            "last4": payment_method.last4,
            "exp_month": payment_method.exp_month,
            "exp_year": payment_method.exp_year,
            "is_default": payment_method.is_default,
        }
        return PaymentMethodResponse(**payment_method_data)

    async def get_payment_history(
        self, user_id: int, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get a user's payment history"""
        subscription = self.repository.get_by_user_id(user_id)

        if not subscription:
            return []

        if not subscription.stripe_customer_id:
            return []

        # Get invoices from Stripe
        try:
            invoices = await self.stripe_client.get_invoices(
                subscription.stripe_customer_id, limit
            )
            return [
                {
                    "id": invoice["id"],
                    "amount_paid": invoice["amount_paid"]
                    / 100,  # Convert cents to dollars
                    "status": invoice["status"],
                    "created_at": datetime.fromtimestamp(invoice["created"]),
                    "paid_at": datetime.fromtimestamp(
                        invoice["status_transitions"]["paid_at"]
                    )
                    if invoice.get("status_transitions", {}).get("paid_at")
                    else None,
                    "invoice_pdf": invoice.get("invoice_pdf"),
                }
                for invoice in invoices
            ]
        except Exception as e:
            print(f"Error fetching invoices: {e}")
            return []

    async def create_checkout_session(
        self,
        user_id: int,
        success_url: str,
        cancel_url: str,
        promotional_code: Optional[str] = None,
    ) -> CheckoutSessionResponse:
        """Create a checkout session for a user"""
        subscription = self.repository.get_by_user_id(user_id)

        # If user already has a subscription, don't create a new checkout
        if subscription and subscription.status == SubscriptionStatusEnum.ACTIVE:
            raise HTTPException(
                status_code=400, detail="User already has an active subscription"
            )

        # If we have a customer ID, use it, otherwise we'll create a new one
        customer_id = subscription.stripe_customer_id if subscription else None

        if not customer_id:
            # Get user details using the repository method
            user = self.repository.get_user_by_id(user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Create customer
            customer = await self.stripe_client.create_customer(
                user.email, user.username or f"User {user.id}"
            )
            customer_id = customer["id"]

            # If we have a subscription record, update it with customer_id
            if subscription:
                update_data = SubscriptionUpdate(stripe_customer_id=customer_id)
                self.repository.update_subscription(subscription, update_data)

        # Create checkout session
        checkout_session = await self.stripe_client.create_checkout_session(
            customer_id, success_url, cancel_url, promotional_code
        )

        return CheckoutSessionResponse(
            session_id=checkout_session["id"],
            checkout_url=checkout_session["url"],
        )


    async def track_usage(self, user_id: int, audio_duration_minutes: float) -> None:
        """Track usage for a user"""
        subscription = self.repository.get_by_user_id(user_id)
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        self.repository.track_usage(user_id, audio_duration_minutes)

    async def refund_usage(self, user_id: int, audio_duration_minutes: float) -> None:
        """Refund usage for a user"""
        subscription = self.repository.get_by_user_id(user_id)
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        self.repository.refund_usage(user_id, audio_duration_minutes)
    
    async def handle_webhook(self, payload: str, signature: str) -> WebhookResponse:
        """Handle Stripe webhook events"""
        try:
            event = await self.stripe_client.handle_webhook(payload, signature)

            # Process different event types
            if event["type"] == WebhookEventType.SUBSCRIPTION_CREATED:
                await self._handle_subscription_created(event["data"]["object"])
            elif event["type"] == WebhookEventType.SUBSCRIPTION_UPDATED:
                await self._handle_subscription_updated(event["data"]["object"])
            elif event["type"] == WebhookEventType.SUBSCRIPTION_DELETED:
                await self._handle_subscription_deleted(event["data"]["object"])
            elif event["type"] == WebhookEventType.INVOICE_PAID:
                await self._handle_invoice_paid(event["data"]["object"])

            return WebhookResponse(status="success", event_type=event["type"])

        except Exception as e:
            print(f"Webhook error: {e}")
            raise HTTPException(status_code=400, detail=str(e))

    async def _handle_subscription_created(
        self, subscription_data: Dict[str, Any]
    ) -> None:
        """Handle subscription created event"""
        # Find subscription by Stripe subscription ID
        subscription = self.repository.get_by_stripe_subscription_id(
            subscription_data["id"]
        )

        if not subscription:
            # Find user by customer ID
            customer_id = subscription_data["customer"]
            subscription = self.repository.get_by_stripe_customer_id(customer_id)

            if not subscription:
                # This is a new subscription we don't know about
                # It might have been created in Stripe directly
                # We'd typically create a new record, but we need a user ID
                # In this case, we'll just log it and handle it manually
                print(f"New subscription created in Stripe: {subscription_data['id']}")
                return

        # Update subscription data
        update_data = SubscriptionUpdate(
            status=subscription_data["status"],
            current_period_start=datetime.fromtimestamp(
                subscription_data["current_period_start"]
            ),
            current_period_end=datetime.fromtimestamp(
                subscription_data["current_period_end"]
            ),
            trial_end=datetime.fromtimestamp(subscription_data["trial_end"])
            if subscription_data.get("trial_end")
            else None,
        )

        self.repository.update_subscription(subscription, update_data)

    async def _handle_subscription_updated(
        self, subscription_data: Dict[str, Any]
    ) -> None:
        """Handle subscription updated event"""
        # Find subscription by Stripe subscription ID
        subscription = self.repository.get_by_stripe_subscription_id(
            subscription_data["id"]
        )

        if not subscription:
            # We don't know about this subscription
            print(f"Unknown subscription updated in Stripe: {subscription_data['id']}")
            return

        # Update subscription data
        update_data = SubscriptionUpdate(
            status=subscription_data["status"],
            current_period_start=datetime.fromtimestamp(
                subscription_data["current_period_start"]
            ),
            current_period_end=datetime.fromtimestamp(
                subscription_data["current_period_end"]
            ),
            trial_end=datetime.fromtimestamp(subscription_data["trial_end"])
            if subscription_data.get("trial_end")
            else None,
        )

        self.repository.update_subscription(subscription, update_data)

    async def _handle_subscription_deleted(
        self, subscription_data: Dict[str, Any]
    ) -> None:
        """Handle subscription deleted event"""
        # Find subscription by Stripe subscription ID
        subscription = self.repository.get_by_stripe_subscription_id(
            subscription_data["id"]
        )

        if not subscription:
            # We don't know about this subscription
            print(f"Unknown subscription deleted in Stripe: {subscription_data['id']}")
            return

        # Update subscription status
        update_data = SubscriptionUpdate(status=SubscriptionStatusEnum.CANCELED)

        self.repository.update_subscription(subscription, update_data)

    async def _handle_invoice_paid(self, invoice_data: Dict[str, Any]) -> None:
        """Handle invoice paid event"""
        # Check if it's for a subscription
        if not invoice_data.get("subscription"):
            return

        # Find subscription by Stripe subscription ID
        subscription = self.repository.get_by_stripe_subscription_id(
            invoice_data["subscription"]
        )

        if not subscription:
            # We don't know about this subscription
            print(
                f"Invoice paid for unknown subscription: {invoice_data['subscription']}"
            )
            return

        # Add invoice to database
        self.repository.add_invoice(
            subscription.id,
            invoice_data["id"],
            invoice_data["amount_due"] / 100,  # Convert cents to dollars
            invoice_data["status"],
        )
