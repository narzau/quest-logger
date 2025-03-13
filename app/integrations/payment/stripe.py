import stripe
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.core.config import settings


class StripeClient:
    """
    Client for Stripe API interactions
    """

    def __init__(self):
        """Initialize the Stripe client with API key from settings"""
        self.api_key = settings.STRIPE_API_KEY
        stripe.api_key = self.api_key

    async def create_customer(self, email: str, name: str) -> Dict[str, Any]:
        """
        Create a new Stripe customer

        Args:
            email: Customer's email address
            name: Customer's name

        Returns:
            Stripe customer object
        """
        try:
            customer = stripe.Customer.create(
                email=email, name=name, metadata={"application": "quest-logger"}
            )
            return customer
        except stripe.error.StripeError as e:
            raise ValueError(f"Failed to create Stripe customer: {str(e)}")

    async def create_subscription(
        self,
        customer_id: str,
        billing_cycle: str = "monthly",
        trial_days: int = 0,
        promotional_code: str = None,
    ) -> Dict[str, Any]:
        """
        Create a new subscription for a customer

        Args:
            customer_id: Stripe customer ID
            billing_cycle: "monthly" or "annual"
            trial_days: Number of trial days (0 for no trial)
            promotional_code: Optional promotional code

        Returns:
            Stripe subscription object
        """
        try:
            # Get the correct price ID based on billing cycle
            price_id = settings.STRIPE_PRO_PRICE_ID

            # Set up subscription parameters
            subscription_params = {
                "customer": customer_id,
                "items": [{"price": price_id}],
                "expand": ["latest_invoice.payment_intent"],
            }

            # Add trial period if specified
            if trial_days > 0:
                subscription_params["trial_period_days"] = trial_days

            # Add promotional code if specified
            if promotional_code:
                # Lookup promotion code
                promo_codes = stripe.PromotionCode.list(
                    code=promotional_code, active=True, limit=1
                )
                if promo_codes and promo_codes.data:
                    subscription_params["promotion_code"] = promo_codes.data[0].id

            # Create the subscription
            subscription = stripe.Subscription.create(**subscription_params)
            return subscription

        except stripe.error.StripeError as e:
            raise ValueError(f"Failed to create Stripe subscription: {str(e)}")

    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Cancel a subscription

        Args:
            subscription_id: Stripe subscription ID

        Returns:
            Canceled subscription object
        """
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            canceled_subscription = stripe.Subscription.modify(
                subscription_id, cancel_at_period_end=True
            )
            return canceled_subscription

        except stripe.error.StripeError as e:
            raise ValueError(f"Failed to cancel subscription: {str(e)}")

    async def create_payment_method(
        self, customer_id: str, payment_method_id: str
    ) -> Dict[str, Any]:
        """
        Attach a payment method to a customer

        Args:
            customer_id: Stripe customer ID
            payment_method_id: Stripe payment method ID

        Returns:
            Attached payment method object
        """
        try:
            # Attach the payment method to the customer
            payment_method = stripe.PaymentMethod.attach(
                payment_method_id, customer=customer_id
            )

            # Set as default payment method
            stripe.Customer.modify(
                customer_id,
                invoice_settings={"default_payment_method": payment_method_id},
            )

            return payment_method

        except stripe.error.StripeError as e:
            raise ValueError(f"Failed to create/attach payment method: {str(e)}")

    async def get_payment_method(self, payment_method_id: str) -> Dict[str, Any]:
        """
        Retrieve a payment method

        Args:
            payment_method_id: Stripe payment method ID

        Returns:
            Payment method object
        """
        try:
            return stripe.PaymentMethod.retrieve(payment_method_id)
        except stripe.error.StripeError as e:
            raise ValueError(f"Failed to retrieve payment method: {str(e)}")

    async def delete_payment_method(self, payment_method_id: str) -> bool:
        """
        Detach a payment method from a customer

        Args:
            payment_method_id: Stripe payment method ID

        Returns:
            True if successful
        """
        try:
            stripe.PaymentMethod.detach(payment_method_id)
            return True
        except stripe.error.StripeError as e:
            raise ValueError(f"Failed to delete payment method: {str(e)}")

    async def get_invoices(
        self, customer_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get invoices for a customer

        Args:
            customer_id: Stripe customer ID
            limit: Maximum number of invoices to return

        Returns:
            List of invoice objects
        """
        try:
            invoices = stripe.Invoice.list(
                customer=customer_id, limit=limit, status="paid"
            )
            return invoices.data
        except stripe.error.StripeError as e:
            raise ValueError(f"Failed to retrieve invoices: {str(e)}")

    async def create_checkout_session(
        self,
        customer_id: str,
        success_url: str,
        cancel_url: str,
        promotional_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a checkout session for a customer

        Args:
            customer_id: Stripe customer ID
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect after canceled payment
            promotional_code: Optional promotional code

        Returns:
            Checkout session object
        """
        try:
            # Set up session parameters
            session_params = {
                "customer": customer_id,
                "payment_method_types": ["card"],
                "line_items": [{"price": settings.STRIPE_PRO_PRICE_ID, "quantity": 1}],
                "mode": "subscription",
                "success_url": success_url,
                "cancel_url": cancel_url,
            }

            # Add promotional code if specified
            if promotional_code:
                # Get promotion codes
                promo_codes = stripe.PromotionCode.list(
                    code=promotional_code, active=True, limit=1
                )

                if promo_codes and promo_codes.data:
                    session_params["discounts"] = [
                        {"promotion_code": promo_codes.data[0].id}
                    ]

            # Create the checkout session
            session = stripe.checkout.Session.create(**session_params)
            return session

        except stripe.error.StripeError as e:
            raise ValueError(f"Failed to create checkout session: {str(e)}")

    async def handle_webhook(self, payload: str, signature: str) -> Dict[str, Any]:
        """
        Handle Stripe webhook event

        Args:
            payload: Raw request payload
            signature: Stripe signature header

        Returns:
            Parsed webhook event
        """
        try:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, signature, settings.STRIPE_WEBHOOK_SECRET
            )
            return event
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            raise ValueError(f"Invalid webhook signature: {str(e)}")
        except stripe.error.StripeError as e:
            raise ValueError(f"Webhook error: {str(e)}")
