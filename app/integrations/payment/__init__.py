from app.integrations.payment.stripe import StripeClient


def get_stripe_client() -> StripeClient:
    """
    Provides a StripeClient instance for dependency injection.
    """
    return StripeClient()
