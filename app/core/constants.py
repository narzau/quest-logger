# app/core/constants.py


# Subscription Status Constants
class SubscriptionStatus:
    ACTIVE = "active"
    CANCELED = "canceled"
    TRIALING = "trialing"
    TRIAL_EXPIRED = "trial_expired"
    PAST_DUE = "past_due"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    UNPAID = "unpaid"
    NONE = "none"


# Billing Cycle Constants
class BillingCycle:
    MONTHLY = "monthly"
    ANNUAL = "annual"


# Feature Flag Constants
class FeatureFlag:
    SHARING = "sharing"
    EXPORTING = "exporting"
    PRIORITY_PROCESSING = "priority_processing"
    ADVANCED_AI = "advanced_ai"


# Webhook Event Types
class WebhookEventType:
    SUBSCRIPTION_CREATED = "customer.subscription.created"
    SUBSCRIPTION_UPDATED = "customer.subscription.updated"
    SUBSCRIPTION_DELETED = "customer.subscription.deleted"
    INVOICE_PAID = "invoice.paid"


# Payment Constants
class PaymentStatus:
    PAID = "paid"
    UNPAID = "unpaid"
    DRAFT = "draft"
