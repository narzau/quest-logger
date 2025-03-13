from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Float, Boolean
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.core.constants import SubscriptionStatus, BillingCycle, PaymentStatus


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Subscription details
    billing_cycle = Column(String, default=BillingCycle.MONTHLY)  # monthly, annual
    stripe_subscription_id = Column(String, nullable=True)
    stripe_customer_id = Column(String, nullable=True)

    # Subscription status
    status = Column(
        String, default=SubscriptionStatus.ACTIVE
    )  # active, canceled, past_due, etc.
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    trial_end = Column(DateTime, nullable=True)

    # Usage tracking
    total_minutes_used_this_month = Column(Float, default=0.0)
    monthly_minutes_limit = Column(Float, default=120.0)  # 2 hours

    # Feature flags - there is only one tier so all features are enabled
    allow_sharing = Column(Boolean, default=True)
    allow_exporting = Column(Boolean, default=True)
    priority_processing = Column(Boolean, default=True)
    advanced_ai_features = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="subscription")
    invoices = relationship(
        "Invoice", back_populates="subscription", cascade="all, delete-orphan"
    )
    payment_methods = relationship(
        "PaymentMethod", back_populates="subscription", cascade="all, delete-orphan"
    )


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(
        Integer, ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    stripe_invoice_id = Column(String, nullable=True)
    amount_due = Column(Float, default=0.0)
    amount_paid = Column(Float, default=0.0)
    status = Column(String, default=PaymentStatus.DRAFT)
    invoice_pdf = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)

    # Relationships
    subscription = relationship("Subscription", back_populates="invoices")


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(
        Integer, ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    stripe_payment_method_id = Column(String, nullable=True)
    brand = Column(String, nullable=True)
    last4 = Column(String, nullable=True)
    exp_month = Column(Integer, nullable=True)
    exp_year = Column(Integer, nullable=True)
    is_default = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    subscription = relationship("Subscription", back_populates="payment_methods")


class PromotionalCode(Base):
    __tablename__ = "promotional_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    percent_off = Column(Float, nullable=True)
    amount_off = Column(Float, nullable=True)
    duration = Column(String, default="once")  # "forever", "once", "repeating"
    duration_in_months = Column(Integer, nullable=True)
    max_redemptions = Column(Integer, nullable=True)
    times_redeemed = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
