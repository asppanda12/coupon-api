import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from bson import ObjectId
from datetime import datetime, timedelta
import json

# Import the main app
from main import app

# Create test client
client = TestClient(app)

# Mock data for tests
mock_customer_id = "60d21b4667d0d8992e610c85"
mock_product_id = "p123"
mock_coupon_id = "WELCOME10"

# Mock coupon data
mock_cart_coupon = {
    "coupon_id": "CART20",
    "type": "cart-wise",
    "details": {
        "threshold": 100.0,
        "discount_percentage": 20.0,
        "max_discount": 50.0
    },
    "is_active": True,
    "valid_from": datetime.now() - timedelta(days=10),
    "valid_until": datetime.now() + timedelta(days=20),
    "user_tiers": ["Basic", "Silver", "Gold", "Platinum"],
    "description": "20% off on orders above $100, max discount $50"
}

mock_product_coupon = {
    "coupon_id": "PROD15",
    "type": "product-wise",
    "details": {
        "product_ids": ["p123", "p456"],
        "discount_percentage": 15.0,
        "min_quantity": 2
    },
    "is_active": True,
    "valid_from": datetime.now() - timedelta(days=5),
    "valid_until": None,
    "user_tiers": ["Basic", "Silver", "Gold", "Platinum"],
    "description": "15% off on selected products"
}

mock_bxgy_coupon = {
    "coupon_id": "BUY2GET1",
    "type": "bxgy",
    "details": {
        "buy_products": ["p123", "p456"],
        "buy_quantity": 2,
        "get_products": ["p789"],
        "get_quantity": 1,
        "discount_percentage": 100.0,
        "repetition_limit": 1
    },
    "is_active": True,
    "valid_from": datetime.now() - timedelta(days=2),
    "valid_until": datetime.now() + timedelta(days=30),
    "user_tiers": ["Silver", "Gold", "Platinum"],
    "description": "Buy 2, Get 1 Free"
}

mock_customer = {
    "_id": ObjectId(mock_customer_id),
    "name": "Test User",
    "email": "test@example.com",
    "tier": "Silver",
    "cart": {
        "p123": {"product_id": "p123", "quantity": 2, "price": 50.0, "subtotal": 100.0},
        "p456": {"product_id": "p456", "quantity": 1, "price": 30.0, "subtotal": 30.0},
        "p789": {"product_id": "p789", "quantity": 1, "price": 20.0, "subtotal": 20.0}
    },
    "exclusive_coupons": {
        "EXCLUSIVE10": 2
    },
    "coupon_history": []
}

mock_product = {
    "product_id": mock_product_id,
    "name": "Test Product",
    "price": 50.0,
    "stock": 100
}

# Setup patches for MongoDB collections
@pytest.fixture(autouse=True)
def mock_db_connections():
    with patch('main.customers_collection') as mock_customers, \
         patch('main.products_collection') as mock_products, \
         patch('main.coupons_collection') as mock_coupons:
        
        # Set up mock returns
        mock_customers.find_one.side_effect = lambda filter: mock_customer if filter.get("_id") == ObjectId(mock_customer_id) else None
        mock_products.find_one.side_effect = lambda filter: mock_product if filter.get("product_id") == mock_product_id else None
        
        # For coupons
        def find_one_coupon(filter):
            if filter.get("coupon_id") == mock_cart_coupon["coupon_id"]:
                return mock_cart_coupon
            elif filter.get("coupon_id") == mock_product_coupon["coupon_id"]:
                return mock_product_coupon
            elif filter.get("coupon_id") == mock_bxgy_coupon["coupon_id"]:
                return mock_bxgy_coupon
            return None
            
        mock_coupons.find_one.side_effect = find_one_coupon
        mock_coupons.find.return_value = [mock_cart_coupon, mock_product_coupon, mock_bxgy_coupon]
        
        yield mock_customers, mock_products, mock_coupons


# ------------------------ Part 1: Coupon Management Tests ------------------------

class TestCouponManagement:
    def test_create_coupon(self, mock_db_connections):
        _, _, mock_coupons = mock_db_connections
        mock_coupons.find_one.return_value = None  # No coupon exists yet
        
        response = client.post(
            "/coupons",
            json={
                "coupon_id": "NEW10",
                "type": "cart-wise",
                "details": {
                    "threshold": 50.0,
                    "discount_percentage": 10.0
                },
                "is_active": True,
                "valid_from": datetime.now().isoformat(),
                "description": "10% off on orders above $50"
            }
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Coupon created successfully"
        assert response.json()["coupon_id"] == "NEW10"
        mock_coupons.insert_one.assert_called_once()
    
    def test_create_duplicate_coupon(self, mock_db_connections):
        _, _, mock_coupons = mock_db_connections
        mock_coupons.find_one.return_value = mock_cart_coupon  # Coupon already exists
        
        response = client.post(
            "/coupons",
            json={
                "coupon_id": mock_cart_coupon["coupon_id"],
                "type": "cart-wise",
                "details": {
                    "threshold": 50.0,
                    "discount_percentage": 10.0
                },
                "is_active": True,
                "valid_from": datetime.now().isoformat(),
                "description": "Duplicate coupon"
            }
        )
        
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]
    
    def test_get_all_coupons(self, mock_db_connections):
        _, _, mock_coupons = mock_db_connections
        # Convert ObjectId to string for each coupon
        for coupon in [mock_cart_coupon, mock_product_coupon, mock_bxgy_coupon]:
            coupon["_id"] = str(ObjectId())
            
        response = client.get("/coupons")
        
        assert response.status_code == 200
        assert len(response.json()) == 3
    
    def test_get_coupon_by_id(self, mock_db_connections):
        _, _, mock_coupons = mock_db_connections
        mock_cart_coupon["_id"] = str(ObjectId())
        mock_coupons.find_one.return_value = mock_cart_coupon
        
        response = client.get(f"/coupons/{mock_cart_coupon['coupon_id']}")
        
        assert response.status_code == 200
        assert response.json()["coupon_id"] == mock_cart_coupon["coupon_id"]
        assert response.json()["type"] == "cart-wise"
    
    def test_get_nonexistent_coupon(self, mock_db_connections):
        _, _, mock_coupons = mock_db_connections
        mock_coupons.find_one.return_value = None
        
        response = client.get("/coupons/NONEXISTENT")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    def test_update_coupon(self, mock_db_connections):
        _, _, mock_coupons = mock_db_connections
        mock_coupons.update_one.return_value = MagicMock(matched_count=1)
        
        response = client.put(
            f"/coupons/{mock_cart_coupon['coupon_id']}",
            json={"is_active": False}
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Coupon updated successfully"
        mock_coupons.update_one.assert_called_once()
    
    def test_update_nonexistent_coupon(self, mock_db_connections):
        _, _, mock_coupons = mock_db_connections
        mock_coupons.update_one.return_value = MagicMock(matched_count=0)
        
        response = client.put(
            "/coupons/NONEXISTENT",
            json={"is_active": False}
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    def test_delete_coupon(self, mock_db_connections):
        _, _, mock_coupons = mock_db_connections
        mock_coupons.delete_one.return_value = MagicMock(deleted_count=1)
        
        response = client.delete(f"/coupons/{mock_cart_coupon['coupon_id']}")
        
        assert response.status_code == 200
        assert response.json()["message"] == "Coupon deleted successfully"
        mock_coupons.delete_one.assert_called_once()
    
    def test_delete_nonexistent_coupon(self, mock_db_connections):
        _, _, mock_coupons = mock_db_connections
        mock_coupons.delete_one.return_value = MagicMock(deleted_count=0)
        
        response = client.delete("/coupons/NONEXISTENT")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


# ------------------------ Part 2: Cart Management Tests ------------------------

class TestCartManagement:
    def test_add_to_cart(self, mock_db_connections):
        mock_customers, mock_products, _ = mock_db_connections
        
        response = client.post(
            f"/customers/{mock_customer_id}/cart",
            params={
                "product_id": mock_product_id,
                "quantity": 3,
                "price": 50.0
            }
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Product added to cart"
        mock_customers.update_one.assert_called_once()
    
    def test_add_nonexistent_product(self, mock_db_connections):
        _, mock_products, _ = mock_db_connections
        mock_products.find_one.return_value = None
        
        response = client.post(
            f"/customers/{mock_customer_id}/cart",
            params={
                "product_id": "nonexistent",
                "quantity": 1,
                "price": 10.0
            }
        )
        
        assert response.status_code == 404
        assert "Product not found" in response.json()["detail"]
    
    def test_get_cart(self, mock_db_connections):
        mock_customers, _, _ = mock_db_connections
        
        response = client.get(f"/customers/{mock_customer_id}/cart")
        
        assert response.status_code == 200
        assert "cart" in response.json()
        assert "total" in response.json()
        assert response.json()["total"] == 150.0  # Sum of all subtotals
    
    def test_get_cart_nonexistent_customer(self, mock_db_connections):
        mock_customers, _, _ = mock_db_connections
        mock_customers.find_one.return_value = None
        
        response = client.get("/customers/nonexistent/cart")
        
        assert response.status_code == 404
        assert "Customer not found" in response.json()["detail"]
    
    def test_remove_from_cart(self, mock_db_connections):
        mock_customers, _, _ = mock_db_connections
        mock_customers.update_one.return_value = MagicMock(matched_count=1)
        
        response = client.delete(f"/customers/{mock_customer_id}/cart/{mock_product_id}")
        
        assert response.status_code == 200
        assert response.json()["message"] == "Product removed from cart"
        mock_customers.update_one.assert_called_once()
    
    def test_update_cart_item(self, mock_db_connections):
        mock_customers, _, _ = mock_db_connections
        
        response = client.put(
            f"/customers/{mock_customer_id}/cart/{mock_product_id}",
            params={"quantity": 5}
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Cart updated successfully"
        mock_customers.update_one.assert_called_once()


# ------------------------ Part 3: Coupon Application Tests ------------------------

class TestCouponApplication:
    @patch('main.datetime')
    def test_get_applicable_coupons(self, mock_datetime, mock_db_connections):
        mock_customers, _, mock_coupons = mock_db_connections
        mock_datetime.now.return_value = datetime.now()
        
        # Convert ObjectIds to strings
        for coupon in [mock_cart_coupon, mock_product_coupon, mock_bxgy_coupon]:
            coupon["_id"] = str(ObjectId())
        
        def mock_find(*args, **kwargs):
            return [mock_cart_coupon, mock_product_coupon, mock_bxgy_coupon]
        
        mock_coupons.find.side_effect = mock_find
        
        response = client.get(f"/customers/{mock_customer_id}/applicable-coupons")
        
        assert response.status_code == 200
        assert "applicable_coupons" in response.json()
        
        # Check that we have cart-wise and product-wise coupons (bxgy would be excluded due to tier)
        coupon_types = {coupon["type"] for coupon in response.json()["applicable_coupons"]}
        assert "cart-wise" in coupon_types
        assert "product-wise" in coupon_types
    
    def test_apply_cart_coupon(self, mock_db_connections):
        mock_customers, _, mock_coupons = mock_db_connections
        mock_coupons.find_one.return_value = mock_cart_coupon
        
        response = client.post(f"/customers/{mock_customer_id}/apply-coupon/{mock_cart_coupon['coupon_id']}")
        
        assert response.status_code == 200
        assert response.json()["message"] == "Coupon applied successfully"
        assert response.json()["discount_amount"] == 30.0  # 20% of 150, capped at 50
        assert response.json()["original_total"] == 150.0
        assert response.json()["final_total"] == 120.0
        mock_customers.update_one.assert_called_once()
    
    def test_apply_product_coupon(self, mock_db_connections):
        mock_customers, _, mock_coupons = mock_db_connections
        mock_coupons.find_one.return_value = mock_product_coupon
        
        response = client.post(f"/customers/{mock_customer_id}/apply-coupon/{mock_product_coupon['coupon_id']}")
        
        assert response.status_code == 200
        assert response.json()["message"] == "Coupon applied successfully"
        assert response.json()["discount_amount"] == 15.0  # 15% of 100 (product p123)
        assert response.json()["original_total"] == 150.0
        assert response.json()["final_total"] == 135.0
    
    def test_apply_bxgy_coupon(self, mock_db_connections):
        mock_customers, _, mock_coupons = mock_db_connections
        mock_coupons.find_one.return_value = mock_bxgy_coupon
        
        response = client.post(f"/customers/{mock_customer_id}/apply-coupon/{mock_bxgy_coupon['coupon_id']}")
        
        assert response.status_code == 200
        assert response.json()["message"] == "Coupon applied successfully"
        assert response.json()["discount_amount"] == 20.0  # 100% off on product p789
        assert response.json()["original_total"] == 150.0
        assert response.json()["final_total"] == 130.0
    
    def test_apply_nonexistent_coupon(self, mock_db_connections):
        mock_customers, _, mock_coupons = mock_db_connections
        mock_coupons.find_one.return_value = None
        
        response = client.post(f"/customers/{mock_customer_id}/apply-coupon/NONEXISTENT")
        
        assert response.status_code == 404
        assert "Coupon not found" in response.json()["detail"]
    
    def test_apply_expired_coupon(self, mock_db_connections):
        mock_customers, _, mock_coupons = mock_db_connections
        
        expired_coupon = mock_cart_coupon.copy()
        expired_coupon["valid_until"] = datetime.now() - timedelta(days=1)
        mock_coupons.find_one.return_value = expired_coupon
        
        response = client.post(f"/customers/{mock_customer_id}/apply-coupon/{expired_coupon['coupon_id']}")
        
        assert response.status_code == 400
        assert "expired" in response.json()["detail"]
    
    def test_apply_invalid_tier_coupon(self, mock_db_connections):
        mock_customers, _, mock_coupons = mock_db_connections
        
        tier_restricted_coupon = mock_cart_coupon.copy()
        tier_restricted_coupon["user_tiers"] = ["Gold", "Platinum"]  # Customer is Silver
        mock_coupons.find_one.return_value = tier_restricted_coupon
        
        response = client.post(f"/customers/{mock_customer_id}/apply-coupon/{tier_restricted_coupon['coupon_id']}")
        
        assert response.status_code == 400
        assert "not valid for Silver tier" in response.json()["detail"]