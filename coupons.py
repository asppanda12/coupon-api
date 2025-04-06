from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from typing import Dict, List, Optional, Union
from bson import ObjectId
from pydantic import BaseModel, Field
from datetime import datetime
import json

app = FastAPI(title="Coupon Management API")

# MongoDB Connection
client = MongoClient("mongodb://localhost:27017/")
db = client["ecommerce_db"]
customers_collection = db["customers"]
products_collection = db["products"]
coupons_collection = db["coupons"]

# Pydantic Models for request validation
class ProductItem(BaseModel):
    product_id: str
    quantity: int
    price: float

class CartBasedCoupon(BaseModel):
    threshold: float
    discount_percentage: float
    max_discount: Optional[float] = None

class ProductBasedCoupon(BaseModel):
    product_ids: List[str]
    discount_percentage: float
    min_quantity: Optional[int] = 1

class BxGyCoupon(BaseModel):
    buy_products: List[str]  # List of product IDs eligible for "Buy" part
    buy_quantity: int  # Number of items to buy
    get_products: List[str]  # List of product IDs eligible for "Get" part
    get_quantity: int  # Number of items to get free/discounted
    discount_percentage: float = 100.0  # Default is 100% (free)
    repetition_limit: Optional[int] = 1  # How many times this offer can be applied

class CouponCreate(BaseModel):
    coupon_id: str
    type: str
    details: Union[CartBasedCoupon, ProductBasedCoupon, BxGyCoupon, Dict]
    is_active: bool = True
    valid_from: datetime
    valid_until: Optional[datetime] = None
    user_tiers: Optional[List[str]] = ["Basic", "Silver", "Gold", "Platinum"]
    description: str

# Helper function to convert ObjectId to string for JSON serialization
def json_serialize(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    raise TypeError("Type not serializable")

# ------------------- Part 1: Coupon Management -------------------

@app.post("/coupons", tags=["Coupon Management"])
def create_coupon(coupon: CouponCreate):
    """Create a new coupon in the system"""
    if coupons_collection.find_one({"coupon_id": coupon.coupon_id}):
        raise HTTPException(status_code=400, detail="Coupon ID already exists")
    
    coupon_dict = coupon.dict()
    
    # Convert Pydantic model to dict for MongoDB
    if isinstance(coupon_dict["details"], dict) and "product_ids" in coupon_dict["details"]:
        coupon_dict["type"] = "product-wise"
    elif isinstance(coupon_dict["details"], dict) and "threshold" in coupon_dict["details"]:
        coupon_dict["type"] = "cart-wise"
    elif isinstance(coupon_dict["details"], dict) and "buy_products" in coupon_dict["details"]:
        coupon_dict["type"] = "bxgy"
    
    coupons_collection.insert_one(coupon_dict)
    return {"message": "Coupon created successfully", "coupon_id": coupon.coupon_id}

@app.get("/coupons", tags=["Coupon Management"])
def get_all_coupons():
    """Get all coupons in the system"""
    coupons = list(coupons_collection.find())
    # Convert ObjectId to string for JSON serialization
    for coupon in coupons:
        coupon["_id"] = str(coupon["_id"])
    return coupons

@app.get("/coupons/{coupon_id}", tags=["Coupon Management"])
def get_coupon(coupon_id: str):
    """Get a specific coupon by ID"""
    coupon = coupons_collection.find_one({"coupon_id": coupon_id})
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    coupon["_id"] = str(coupon["_id"])
    return coupon

@app.put("/coupons/{coupon_id}", tags=["Coupon Management"])
def update_coupon(coupon_id: str, updates: Dict):
    """Update an existing coupon"""
    result = coupons_collection.update_one({"coupon_id": coupon_id}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return {"message": "Coupon updated successfully"}

@app.delete("/coupons/{coupon_id}", tags=["Coupon Management"])
def delete_coupon(coupon_id: str):
    """Delete a coupon from the system"""
    result = coupons_collection.delete_one({"coupon_id": coupon_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return {"message": "Coupon deleted successfully"}

# ------------------- Part 2: Customer Cart Management -------------------

@app.post("/customers/{customer_id}/cart", tags=["Cart Management"])
def add_to_cart(customer_id: str, product_id: str, quantity: int, price: float):
    """Add a product to customer cart"""
    product = products_collection.find_one({"product_id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    cart_item = {
        "product_id": product_id,
        "quantity": quantity,
        "price": price,
        "subtotal": quantity * price
    }
    
    # Update or insert the cart item
    customers_collection.update_one(
        {"_id": ObjectId(customer_id)},
        {"$set": {f"cart.{product_id}": cart_item}}
    )
    
    return {"message": "Product added to cart"}

@app.get("/customers/{customer_id}/cart", tags=["Cart Management"])
def get_cart(customer_id: str):
    """Get customer's current cart"""
    customer = customers_collection.find_one({"_id": ObjectId(customer_id)})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    if "cart" not in customer or not customer["cart"]:
        return {"cart": {}, "total": 0}
    
    cart = customer["cart"]
    cart_total = sum(item["subtotal"] for item in cart.values())
    
    return {"cart": cart, "total": cart_total}

@app.delete("/customers/{customer_id}/cart/{product_id}", tags=["Cart Management"])
def remove_from_cart(customer_id: str, product_id: str):
    """Remove a product from customer cart"""
    result = customers_collection.update_one(
        {"_id": ObjectId(customer_id)},
        {"$unset": {f"cart.{product_id}": ""}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    return {"message": "Product removed from cart"}

@app.put("/customers/{customer_id}/cart/{product_id}", tags=["Cart Management"])
def update_cart_item(customer_id: str, product_id: str, quantity: int):
    """Update the quantity of a product in the cart"""
    customer = customers_collection.find_one({"_id": ObjectId(customer_id)})
    if not customer or "cart" not in customer or product_id not in customer["cart"]:
        raise HTTPException(status_code=404, detail="Product not found in cart")
    
    cart_item = customer["cart"][product_id]
    cart_item["quantity"] = quantity
    cart_item["subtotal"] = quantity * cart_item["price"]
    
    customers_collection.update_one(
        {"_id": ObjectId(customer_id)},
        {"$set": {f"cart.{product_id}": cart_item}}
    )
    
    return {"message": "Cart updated successfully"}

# ------------------- Part 3: Coupon Application -------------------

@app.get("/customers/{customer_id}/applicable-coupons", tags=["Coupon Application"])
def get_applicable_coupons(customer_id: str):
    """Get all coupons applicable to a customer's current cart"""
    customer = customers_collection.find_one({"_id": ObjectId(customer_id)})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Check if customer has a cart
    if "cart" not in customer or not customer["cart"]:
        return {"applicable_coupons": []}
    
    cart = customer["cart"]
    cart_items = list(cart.values())
    cart_total = sum(item["subtotal"] for item in cart_items)
    customer_tier = customer.get("tier", "Basic")
    
    # Get all active coupons that match the customer tier
    all_coupons = list(coupons_collection.find({
        "is_active": True,
        "valid_from": {"$lte": datetime.now()},
        "$or": [
            {"valid_until": {"$gte": datetime.now()}},
            {"valid_until": None}
        ],
        "user_tiers": customer_tier
    }))
    
    applicable_coupons = []
    
    for coupon in all_coupons:
        coupon["_id"] = str(coupon["_id"])
        
        # Check each coupon type
        if coupon["type"] == "cart-wise":
            # Check if cart total meets threshold
            if cart_total >= coupon["details"]["threshold"]:
                discount = min(
                    cart_total * (coupon["details"]["discount_percentage"] / 100),
                    coupon["details"].get("max_discount", float('inf'))
                )
                coupon["calculated_discount"] = discount
                applicable_coupons.append(coupon)
        
        elif coupon["type"] == "product-wise":
            product_discount = 0
            for product_id in coupon["details"]["product_ids"]:
                if product_id in cart and cart[product_id]["quantity"] >= coupon["details"].get("min_quantity", 1):
                    product_subtotal = cart[product_id]["subtotal"]
                    product_discount += product_subtotal * (coupon["details"]["discount_percentage"] / 100)
            
            if product_discount > 0:
                coupon["calculated_discount"] = product_discount
                applicable_coupons.append(coupon)
        
        elif coupon["type"] == "bxgy":
            # BxGy logic is more complex
            eligible_buy_products = {}
            eligible_get_products = {}
            
            # Count eligible products for "buy" part
            for product_id in coupon["details"]["buy_products"]:
                if product_id in cart:
                    eligible_buy_products[product_id] = cart[product_id]["quantity"]
            
            # Count eligible products for "get" part
            for product_id in coupon["details"]["get_products"]:
                if product_id in cart:
                    eligible_get_products[product_id] = {
                        "quantity": cart[product_id]["quantity"],
                        "price": cart[product_id]["price"]
                    }
            
            if eligible_buy_products and eligible_get_products:
                # Calculate how many "buy" units we have
                total_buy_quantity = sum(eligible_buy_products.values())
                buy_units = total_buy_quantity // coupon["details"]["buy_quantity"]
                
                # Apply repetition limit if set
                if coupon["details"].get("repetition_limit"):
                    buy_units = min(buy_units, coupon["details"]["repetition_limit"])
                
                if buy_units > 0:
                    # Calculate how many "get" items can be discounted
                    total_get_units = buy_units * coupon["details"]["get_quantity"]
                    
                    # Sort eligible "get" products by price (lowest first for maximum discount)
                    sorted_get_products = sorted(
                        [(pid, data["price"]) for pid, data in eligible_get_products.items()],
                        key=lambda x: x[1]
                    )
                    
                    # Calculate discount
                    discount = 0
                    units_discounted = 0
                    
                    for pid, price in sorted_get_products:
                        available_units = eligible_get_products[pid]["quantity"]
                        units_to_discount = min(available_units, total_get_units - units_discounted)
                        
                        if units_to_discount > 0:
                            discount += units_to_discount * price * (coupon["details"]["discount_percentage"] / 100)
                            units_discounted += units_to_discount
                            
                            if units_discounted >= total_get_units:
                                break
                    
                    if discount > 0:
                        coupon["calculated_discount"] = discount
                        applicable_coupons.append(coupon)
    
    # Sort by discount value, highest first
    applicable_coupons.sort(key=lambda x: x["calculated_discount"], reverse=True)
    
    return {"applicable_coupons": applicable_coupons}

@app.post("/customers/{customer_id}/apply-coupon/{coupon_id}", tags=["Coupon Application"])
def apply_coupon(customer_id: str, coupon_id: str):
    """Apply a coupon to a customer's cart and calculate final price"""
    customer = customers_collection.find_one({"_id": ObjectId(customer_id)})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    coupon = coupons_collection.find_one({"coupon_id": coupon_id})
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    
    # Verify coupon is active and valid
    now = datetime.now()
    if not coupon["is_active"] or coupon["valid_from"] > now:
        raise HTTPException(status_code=400, detail="Coupon is not active or not yet valid")
    
    if coupon.get("valid_until") and coupon["valid_until"] < now:
        raise HTTPException(status_code=400, detail="Coupon has expired")
    
    # Check if customer's tier is eligible for this coupon
    customer_tier = customer.get("tier", "Basic")
    if customer_tier not in coupon.get("user_tiers", ["Basic"]):
        raise HTTPException(status_code=400, detail=f"This coupon is not valid for {customer_tier} tier")
    
    # Check if the customer has a cart
    if "cart" not in customer or not customer["cart"]:
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    # Recalculate the discount to ensure it's correct
    cart = customer["cart"]
    cart_items = list(cart.values())
    cart_total = sum(item["subtotal"] for item in cart_items)
    discount = 0
    
    # Apply discount based on coupon type
    if coupon["type"] == "cart-wise":
        if cart_total >= coupon["details"]["threshold"]:
            discount = min(
                cart_total * (coupon["details"]["discount_percentage"] / 100),
                coupon["details"].get("max_discount", float('inf'))
            )
    
    elif coupon["type"] == "product-wise":
        for product_id in coupon["details"]["product_ids"]:
            if product_id in cart and cart[product_id]["quantity"] >= coupon["details"].get("min_quantity", 1):
                product_subtotal = cart[product_id]["subtotal"]
                discount += product_subtotal * (coupon["details"]["discount_percentage"] / 100)
    
    elif coupon["type"] == "bxgy":
        # BxGy logic (similar to the get_applicable_coupons function)
        eligible_buy_products = {}
        eligible_get_products = {}
        
        # Count eligible products for "buy" part
        for product_id in coupon["details"]["buy_products"]:
            if product_id in cart:
                eligible_buy_products[product_id] = cart[product_id]["quantity"]
        
        # Count eligible products for "get" part
        for product_id in coupon["details"]["get_products"]:
            if product_id in cart:
                eligible_get_products[product_id] = {
                    "quantity": cart[product_id]["quantity"],
                    "price": cart[product_id]["price"]
                }
        
        if eligible_buy_products and eligible_get_products:
            # Calculate how many "buy" units we have
            total_buy_quantity = sum(eligible_buy_products.values())
            buy_units = total_buy_quantity // coupon["details"]["buy_quantity"]
            
            # Apply repetition limit if set
            if coupon["details"].get("repetition_limit"):
                buy_units = min(buy_units, coupon["details"]["repetition_limit"])
            
            if buy_units > 0:
                # Calculate how many "get" items can be discounted
                total_get_units = buy_units * coupon["details"]["get_quantity"]
                
                # Sort eligible "get" products by price (lowest first for maximum discount)
                sorted_get_products = sorted(
                    [(pid, data["price"]) for pid, data in eligible_get_products.items()],
                    key=lambda x: x[1]
                )
                
                # Calculate discount
                units_discounted = 0
                
                for pid, price in sorted_get_products:
                    available_units = eligible_get_products[pid]["quantity"]
                    units_to_discount = min(available_units, total_get_units - units_discounted)
                    
                    if units_to_discount > 0:
                        discount += units_to_discount * price * (coupon["details"]["discount_percentage"] / 100)
                        units_discounted += units_to_discount
                        
                        if units_discounted >= total_get_units:
                            break
    
    if discount <= 0:
        raise HTTPException(status_code=400, detail="Coupon is not applicable to your cart")
    
    # Calculate final price
    final_price = cart_total - discount
    
    # Check if customer has exclusive coupons for this coupon id
    exclusive_coupons = customer.get("exclusive_coupons", {})
    if coupon_id in exclusive_coupons:
        usage_limit = exclusive_coupons[coupon_id]
        if usage_limit <= 0:
            raise HTTPException(status_code=400, detail="You have used all your exclusive coupons of this type")
        # Decrement usage limit
        customers_collection.update_one(
            {"_id": ObjectId(customer_id)},
            {"$set": {f"exclusive_coupons.{coupon_id}": usage_limit - 1}}
        )
    
    # Create a discount summary
    discount_summary = {
        "coupon_id": coupon_id,
        "coupon_type": coupon["type"],
        "discount_amount": discount,
        "original_total": cart_total,
        "final_total": final_price,
        "applied_at": datetime.now()
    }
    
    # Add to customer's applied coupons history
    customers_collection.update_one(
        {"_id": ObjectId(customer_id)},
        {"$push": {"coupon_history": discount_summary}}
    )
    
    return {
        "message": "Coupon applied successfully",
        "discount_amount": discount,
        "original_total": cart_total,
        "final_total": final_price
    }
