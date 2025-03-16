from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy import and_

from sqlalchemy.orm import Session

from app.repositories.base_repository import BaseRepository
from app.models import Subscription, User, Invoice, PaymentMethod, PromotionalCode
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate
from app.core.constants import SubscriptionStatus, BillingCycle, FeatureFlag


class SubscriptionRepository(BaseRepository[Subscription]):
    """Repository for Subscription operations."""

    def __init__(self, db: Session):
        super().__init__(Subscription, db)

    def create_subscription(
        self, user_id: int, obj_in: SubscriptionCreate
    ) -> Subscription:
        """Create a new subscription for a user"""
        subscription_data = obj_in.dict()

        # All subscriptions have the same feature set
        subscription = Subscription(
            user_id=user_id,
            billing_cycle=subscription_data.get("billing_cycle", BillingCycle.MONTHLY),
            promotional_code=subscription_data.get("promotional_code"),
            stripe_subscription_id=subscription_data.get("stripe_subscription_id"),
            stripe_customer_id=subscription_data.get("stripe_customer_id"),
            allow_sharing=True,
            allow_exporting=True,
            priority_processing=True,
            advanced_ai_features=True,
            monthly_minutes_limit=120.0,  # 2 hours
            status=SubscriptionStatus.ACTIVE,
        )

        self.db.add(subscription)
        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def get_by_user_id(self, user_id: int) -> Optional[Subscription]:
        """Get subscription by user ID"""
        return (
            self.db.query(Subscription).filter(Subscription.user_id == user_id).first()
        )

    def update_subscription(
        self, subscription: Subscription, obj_in: SubscriptionUpdate
    ) -> Subscription:
        """Update subscription details"""
        update_data = obj_in.dict(exclude_unset=True)

        # Update fields based on the provided data
        for field, value in update_data.items():
            setattr(subscription, field, value)

        # Update timestamp
        subscription.updated_at = datetime.utcnow()

        self.db.add(subscription)
        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def track_usage(self, user_id: int, minutes_used: float) -> Optional[Subscription]:
        """Track voice note minutes usage"""
        subscription = self.get_by_user_id(user_id)

        if subscription:
            subscription.total_minutes_used_this_month += minutes_used
            subscription.updated_at = datetime.utcnow()

            self.db.add(subscription)
            self.db.commit()
            self.db.refresh(subscription)

        return subscription

    def refund_usage(self, user_id: int, minutes_to_refund: float) -> Optional[Subscription]:
        """Refund voice note minutes when processing fails"""
        subscription = self.get_by_user_id(user_id)

        if subscription:
            # Ensure we don't go below zero
            subscription.total_minutes_used_this_month = max(
                0, subscription.total_minutes_used_this_month - minutes_to_refund
            )
            subscription.updated_at = datetime.utcnow()

            self.db.add(subscription)
            self.db.commit()
            self.db.refresh(subscription)

        return subscription

    def reset_monthly_usage(self, user_id: int = None) -> None:
        """Reset monthly usage for a user or all users"""
        if user_id:
            # Reset for a specific user
            subscription = self.get_by_user_id(user_id)
            if subscription:
                subscription.total_minutes_used_this_month = 0
                subscription.updated_at = datetime.utcnow()
                self.db.add(subscription)
        else:
            # Reset for all users
            subscriptions = self.db.query(Subscription).all()
            for subscription in subscriptions:
                subscription.total_minutes_used_this_month = 0
                subscription.updated_at = datetime.utcnow()
                self.db.add(subscription)

        self.db.commit()

    def get_subscription_status(self, user_id: int) -> Dict[str, Any]:
        """Get user-friendly subscription status"""
        subscription = self.get_by_user_id(user_id)

        if not subscription:
            # User needs to be directed to purchase a subscription
            return {
                "status": SubscriptionStatus.NONE,
                "billing_cycle": BillingCycle.MONTHLY,
                "current_period_end": None,
                "minutes_used": 0,
                "minutes_limit": 0,
                "features": {
                    FeatureFlag.SHARING: False,
                    FeatureFlag.EXPORTING: False,
                    FeatureFlag.PRIORITY_PROCESSING: False,
                    FeatureFlag.ADVANCED_AI: False,
                },
                "payment_method": None,
                "trial_end": None,
            }

        # Get payment method
        payment_method = (
            self.db.query(PaymentMethod)
            .filter(
                PaymentMethod.subscription_id == subscription.id,
                PaymentMethod.is_default == True,
            )
            .first()
        )

        payment_info = None
        if payment_method:
            payment_info = {
                "brand": payment_method.brand,
                "last4": payment_method.last4,
                "exp_month": payment_method.exp_month,
                "exp_year": payment_method.exp_year,
            }

        # Return user's subscription details
        return {
            "status": subscription.status,
            "billing_cycle": subscription.billing_cycle,
            "current_period_end": subscription.current_period_end,
            "trial_end": subscription.trial_end,
            "minutes_used": subscription.total_minutes_used_this_month,
            "minutes_limit": subscription.monthly_minutes_limit,
            "features": {
                FeatureFlag.SHARING: subscription.allow_sharing,
                FeatureFlag.EXPORTING: subscription.allow_exporting,
                FeatureFlag.PRIORITY_PROCESSING: subscription.priority_processing,
                FeatureFlag.ADVANCED_AI: subscription.advanced_ai_features,
            },
            "payment_method": payment_info,
        }

    def delete_subscription(self, subscription: Subscription) -> bool:
        """Delete a subscription"""
        self.db.delete(subscription)
        self.db.commit()
        return True

    def initialize_user_subscription(self, user_id: int) -> Subscription:
        """Initialize a trial subscription for a new user"""
        subscription = self.get_by_user_id(user_id)

        if not subscription:
            # Create a trial subscription that expires in 7 days
            trial_end = datetime.utcnow() + timedelta(days=7)

            subscription = Subscription(
                user_id=user_id,
                status=SubscriptionStatus.TRIALING,
                billing_cycle=BillingCycle.MONTHLY,
                trial_end=trial_end,
                allow_sharing=True,
                allow_exporting=True,
                priority_processing=True,
                advanced_ai_features=True,
                monthly_minutes_limit=120.0,  # 2 hours
            )

            self.db.add(subscription)
            self.db.commit()
            self.db.refresh(subscription)

        return subscription

    def get_invoices(self, subscription_id: int, limit: int = 10) -> List[Invoice]:
        """Get recent invoices for a subscription"""
        return (
            self.db.query(Invoice)
            .filter(Invoice.subscription_id == subscription_id)
            .order_by(Invoice.created_at.desc())
            .limit(limit)
            .all()
        )

    def add_invoice(
        self,
        subscription_id: int,
        stripe_invoice_id: str,
        amount_due: float,
        status: str,
    ) -> Invoice:
        """Add a new invoice for a subscription"""
        invoice = Invoice(
            subscription_id=subscription_id,
            stripe_invoice_id=stripe_invoice_id,
            amount_due=amount_due,
            status=status,
        )

        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def update_invoice(
        self, invoice_id: int, status: str, amount_paid: float
    ) -> Invoice:
        """Update an invoice"""
        invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()

        if invoice:
            invoice.status = status
            invoice.amount_paid = amount_paid

            if status == "paid":
                invoice.paid_at = datetime.utcnow()

            self.db.add(invoice)
            self.db.commit()
            self.db.refresh(invoice)

        return invoice

    def add_payment_method(
        self,
        subscription_id: int,
        stripe_payment_method_id: str,
        brand: str,
        last4: str,
        exp_month: int,
        exp_year: int,
        is_default: bool = True,
    ) -> PaymentMethod:
        """Add a new payment method for a subscription"""
        # If this is the default, set all others to non-default
        if is_default:
            existing_methods = (
                self.db.query(PaymentMethod)
                .filter(PaymentMethod.subscription_id == subscription_id)
                .all()
            )

            for method in existing_methods:
                method.is_default = False
                self.db.add(method)

        payment_method = PaymentMethod(
            subscription_id=subscription_id,
            stripe_payment_method_id=stripe_payment_method_id,
            brand=brand,
            last4=last4,
            exp_month=exp_month,
            exp_year=exp_year,
            is_default=is_default,
        )

        self.db.add(payment_method)
        self.db.commit()
        self.db.refresh(payment_method)
        return payment_method

    def delete_payment_method(self, payment_method_id: int) -> bool:
        """Delete a payment method"""
        payment_method = (
            self.db.query(PaymentMethod)
            .filter(PaymentMethod.id == payment_method_id)
            .first()
        )

        if payment_method:
            # Don't delete if it's the only payment method
            count = (
                self.db.query(PaymentMethod)
                .filter(PaymentMethod.subscription_id == payment_method.subscription_id)
                .count()
            )

            if count > 1:
                self.db.delete(payment_method)
                self.db.commit()
                return True

        return False

    def get_promotional_code(self, code: str) -> Optional[PromotionalCode]:
        """Get a promotional code by code"""
        return (
            self.db.query(PromotionalCode)
            .filter(PromotionalCode.code == code, PromotionalCode.is_active == True)
            .first()
        )

    def get_by_stripe_subscription_id(
        self, stripe_subscription_id: str
    ) -> Optional[Subscription]:
        """Get subscription by Stripe subscription ID"""
        return (
            self.db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == stripe_subscription_id)
            .first()
        )

    def get_by_stripe_customer_id(
        self, stripe_customer_id: str
    ) -> Optional[Subscription]:
        """Get subscription by Stripe customer ID"""
        return (
            self.db.query(Subscription)
            .filter(Subscription.stripe_customer_id == stripe_customer_id)
            .first()
        )

    def get_expired_trials(self) -> List[Subscription]:
        """Get all expired trial subscriptions"""
        now = datetime.utcnow()
        return (
            self.db.query(Subscription)
            .filter(
                and_(
                    Subscription.status == SubscriptionStatus.TRIALING,
                    Subscription.trial_end < now,
                )
            )
            .all()
        )

    def get_expired_active_subscriptions(self) -> List[Subscription]:
        """Get all expired active subscriptions"""
        now = datetime.utcnow()
        return (
            self.db.query(Subscription)
            .filter(
                and_(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.current_period_end < now,
                )
            )
            .all()
        )

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return self.db.query(User).filter(User.id == user_id).first()

    def increment_promo_code_usage(self, promo_code: PromotionalCode) -> PromotionalCode:
        """Increment the usage count of a promotional code"""
        promo_code.times_redeemed += 1
        self.db.add(promo_code)
        self.db.commit()
        self.db.refresh(promo_code)
        return promo_code
