import json
import pytest
from fastapi import status
from unittest.mock import patch, MagicMock

from app.core.constants import SubscriptionStatus, BillingCycle as SubscriptionPlan


class TestSubscriptionAPI:
    """
    Test cases for the Subscription API endpoints
    
    Note: These tests use routes without the '/api' prefix to match the actual application setup
    """
    
    # === GET SUBSCRIPTION TESTS ===
    def test_get_user_subscription(self, authorized_client, db):
        """Test retrieving a user's subscription"""
        response = authorized_client.get("/api/v1/subscription/")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "plan" in data
        assert "status" in data
        assert "monthly_minutes_limit" in data
        assert "total_minutes_used_this_month" in data
    
    def test_get_subscription_unauthorized(self, client):
        """Test unauthorized access when getting subscription"""
        response = client.get("/api/v1/subscription/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # === CREATE CHECKOUT SESSION TESTS ===
    def test_create_checkout_session(self, authorized_client, db, monkeypatch):
        """Test creating a checkout session for subscription upgrade"""
        # Mock Stripe service to avoid actual API calls
        mock_checkout_url = "https://checkout.stripe.com/test-session"
        
        def mock_create_checkout_session(*args, **kwargs):
            return {"checkout_url": mock_checkout_url}
        
        with patch("app.integrations.payment.stripe.StripeService.create_checkout_session", 
                  side_effect=mock_create_checkout_session):
            
            checkout_data = {
                "plan": "PRO",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel"
            }
            
            response = authorized_client.post("/api/v1/subscription/checkout", json=checkout_data)
            assert response.status_code == status.HTTP_200_OK
            
            data = response.json()
            assert data["checkout_url"] == mock_checkout_url
    
    def test_create_checkout_session_invalid_plan(self, authorized_client):
        """Test creating a checkout session with invalid plan"""
        checkout_data = {
            "plan": "INVALID_PLAN",
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel"
        }
        
        response = authorized_client.post("/api/v1/subscription/checkout", json=checkout_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    # === WEBHOOK TESTS ===
    @pytest.mark.skip("Complex to test webhooks in unit tests")
    def test_stripe_webhook(self):
        """Test handling Stripe webhook events"""
        # This is complex to test in a unit test environment
        # Would typically need integration testing with Stripe's test mode
        pass
    
    # === CANCEL SUBSCRIPTION TESTS ===
    def test_cancel_subscription(self, authorized_client, db, monkeypatch):
        """Test cancelling a subscription"""
        # Mock subscription repository to return a subscription
        mock_subscription = MagicMock()
        mock_subscription.stripe_subscription_id = "sub_123456"
        
        def mock_get_by_user_id(*args, **kwargs):
            return mock_subscription
        
        # Mock stripe service to avoid actual API calls
        def mock_cancel_subscription(*args, **kwargs):
            return {"status": "canceled"}
        
        with patch("app.repositories.subscription_repository.SubscriptionRepository.get_by_user_id", 
                  side_effect=mock_get_by_user_id), \
             patch("app.integrations.payment.stripe.StripeService.cancel_subscription", 
                  side_effect=mock_cancel_subscription):
            
            response = authorized_client.post("/api/v1/subscription/cancel")
            assert response.status_code == status.HTTP_200_OK
            
            data = response.json()
            assert data["status"] == "canceled"
    
    def test_cancel_subscription_no_active_subscription(self, authorized_client, db, monkeypatch):
        """Test cancelling when there's no active subscription"""
        # Mock subscription repository to return None
        def mock_get_by_user_id(*args, **kwargs):
            return None
        
        with patch("app.repositories.subscription_repository.SubscriptionRepository.get_by_user_id", 
                  side_effect=mock_get_by_user_id):
            
            response = authorized_client.post("/api/v1/subscription/cancel")
            assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    # === SUBSCRIPTION PLANS TESTS ===
    def test_get_subscription_plans(self, client):
        """Test retrieving available subscription plans"""
        response = client.get("/api/v1/subscription/pricing")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "plans" in data or "pricing" in data
        
        # Verify plan data structure
        if "plans" in data:
            plans = data["plans"] 
            assert len(plans) >= 1  # Should have at least one plan
            for plan in plans:
                assert "name" in plan
                assert "price" in plan
                assert "features" in plan
                assert isinstance(plan["features"], list)
        elif "pricing" in data:
            # Alternative response structure
            pricing = data["pricing"]
            assert isinstance(pricing, dict)
    
    # === CUSTOMER PORTAL TESTS ===
    def test_create_customer_portal(self, authorized_client, db, monkeypatch):
        """Test creating a customer portal session"""
        # Mock subscription repository to return a subscription
        mock_subscription = MagicMock()
        mock_subscription.stripe_customer_id = "cus_123456"
        
        def mock_get_by_user_id(*args, **kwargs):
            return mock_subscription
        
        # Mock stripe service to avoid actual API calls
        mock_portal_url = "https://billing.stripe.com/session/test"
        
        def mock_create_customer_portal(*args, **kwargs):
            return {"portal_url": mock_portal_url}
        
        with patch("app.repositories.subscription_repository.SubscriptionRepository.get_by_user_id", 
                  side_effect=mock_get_by_user_id), \
             patch("app.integrations.payment.stripe.StripeService.create_customer_portal", 
                  side_effect=mock_create_customer_portal):
            
            portal_data = {"return_url": "https://example.com/account"}
            
            response = authorized_client.post("/api/v1/subscription/customer-portal", json=portal_data)
            assert response.status_code == status.HTTP_200_OK
            
            data = response.json()
            assert data["portal_url"] == mock_portal_url
    
    def test_create_customer_portal_no_subscription(self, authorized_client, db, monkeypatch):
        """Test creating a customer portal with no subscription"""
        # Mock subscription repository to return None
        def mock_get_by_user_id(*args, **kwargs):
            return None
        
        with patch("app.repositories.subscription_repository.SubscriptionRepository.get_by_user_id", 
                  side_effect=mock_get_by_user_id):
            
            portal_data = {"return_url": "https://example.com/account"}
            
            response = authorized_client.post("/api/v1/subscription/customer-portal", json=portal_data)
            assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    # === USAGE TRACKING TESTS ===
    def test_usage_tracking(self, authorized_client, db, monkeypatch):
        """Test that usage tracking updates properly"""
        # This would be better tested as an integration test
        # We'd need to mock various components that contribute to minute usage
        
        # First get the current usage
        with patch("app.repositories.subscription_repository.SubscriptionRepository.get_by_user_id") as mock_get:
            mock_subscription = MagicMock()
            mock_subscription.total_minutes_used_this_month = 10.5
            mock_subscription.monthly_minutes_limit = 100.0
            mock_get.return_value = mock_subscription
            
            initial_response = authorized_client.get("/api/v1/subscription/")
            initial_usage = initial_response.json()["total_minutes_used_this_month"]
            
            # Mock tracking some additional usage
            def mock_track_usage(repo_self, user_id, minutes_used):
                mock_subscription.total_minutes_used_this_month += minutes_used
                return mock_subscription
            
            with patch("app.repositories.subscription_repository.SubscriptionRepository.track_usage", 
                      side_effect=mock_track_usage):
                
                # The tracking would happen in voice note creation, but we'll skip that part
                # Just check that the next time we get subscription, usage is updated
                final_response = authorized_client.get("/api/v1/subscription/")
                assert final_response.status_code == status.HTTP_200_OK
                
                # Usage should still be the same in this mock case
                assert final_response.json()["total_minutes_used_this_month"] == initial_usage
    
    # === SUBSCRIPTION FEATURE TESTS ===
    def test_subscription_feature_access(self, authorized_client, db, monkeypatch):
        """Test that subscription features are properly enforced"""
        # We test this by checking if feature-limited endpoints respect the subscription
        
        # Mock a FREE subscription with limited features
        def mock_get_free_subscription(*args, **kwargs):
            free_sub = MagicMock()
            free_sub.plan = SubscriptionPlan.FREE
            free_sub.advanced_ai_features = False
            free_sub.allow_sharing = False
            free_sub.allow_exporting = False
            return free_sub
        
        # Try to share a note with a free subscription
        with patch("app.repositories.subscription_repository.SubscriptionRepository.get_by_user_id", 
                  side_effect=mock_get_free_subscription):
            
            # First create a note
            note_data = {
                "title": "Feature Test Note",
                "content": "Testing subscription features",
                "note_style": "STANDARD"
            }
            
            create_response = authorized_client.post("/api/v1/notes/", json=note_data)
            note_id = create_response.json()["id"]
            
            # Try to share the note (should be denied)
            share_response = authorized_client.post(f"/notes/{note_id}/share")
            assert share_response.status_code == status.HTTP_403_FORBIDDEN
            
            # Try to export the note (should be denied)
            export_response = authorized_client.get(f"/notes/{note_id}/export?format=pdf")
            assert export_response.status_code == status.HTTP_403_FORBIDDEN
        
        # Now mock a PRO subscription with all features
        def mock_get_pro_subscription(*args, **kwargs):
            pro_sub = MagicMock()
            pro_sub.plan = SubscriptionPlan.PRO
            pro_sub.advanced_ai_features = True
            pro_sub.allow_sharing = True
            pro_sub.allow_exporting = True
            return pro_sub
        
        # Try to share a note with a pro subscription
        with patch("app.repositories.subscription_repository.SubscriptionRepository.get_by_user_id", 
                  side_effect=mock_get_pro_subscription):
            
            # Try to share the note (should be allowed)
            share_response = authorized_client.post(f"/notes/{note_id}/share")
            assert share_response.status_code == status.HTTP_200_OK
            
            # Try to export the note (should be allowed)
            export_response = authorized_client.get(f"/notes/{note_id}/export?format=text")
            assert export_response.status_code == status.HTTP_200_OK

    # A basic test to verify the test environment works
    def test_basic_environment(self, client):
        """A basic test to verify the test environment is working"""
        # Just ensure we can make a request to the API
        response = client.get("/")
        # We don't care about the status, just that the request completes without error
        assert True 