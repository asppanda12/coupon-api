# Coupon Management System - Architecture Documentation

## 1. System Overview

The Coupon Management System is a RESTful API built with FastAPI that enables e-commerce platforms to create, manage, and apply various types of discount coupons. The system supports complex coupon logic, customer cart management, and discount calculations based on various business rules.

## 2. Architecture Components

### 2.1 Core Components

#### 2.1.1 Data Layer
- **Database**: MongoDB NoSQL database
- **Collections**:
  - `customers` - Stores customer information, cart data, and coupon usage history
  - `products` - Stores product information
  - `coupons` - Stores coupon definitions and rules

#### 2.1.2 Application Layer
- **FastAPI Framework** - Provides the REST API endpoints, request validation, and response handling
- **Business Logic Layer** - Contains the core domain logic for coupon application and validation
- **Data Access Layer** - Handles interactions with MongoDB collections

#### 2.1.3 API Layer
- RESTful endpoints organized by domain functionality
- OpenAPI documentation provided through Swagger UI

### 2.2 Component Interactions

```
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│  Client Apps  │◄────┤   FastAPI     │◄────┤   MongoDB     │
│  (Web/Mobile) │     │   Backend     │     │  Database     │
└───────────────┘     └───────────────┘     └───────────────┘
                             │
                     ┌───────┴───────┐
                     │  Business     │
                     │  Logic        │
                     └───────────────┘
```

## 3. Data Models

### 3.1 Pydantic Models (API Schema)

#### 3.1.1 Base Models
- **ProductItem** - Represents a product in a customer's cart
  - `product_id`: String (Product identifier)
  - `quantity`: Integer (Number of items)
  - `price`: Float (Unit price)

#### 3.1.2 Coupon Models
- **CartBasedCoupon** - Percentage discount on cart total
  - `threshold`: Float (Minimum cart value)
  - `discount_percentage`: Float (Discount percentage)
  - `max_discount`: Optional[Float] (Maximum discount cap)

- **ProductBasedCoupon** - Percentage discount on specific products
  - `product_ids`: List[String] (Products eligible for discount)
  - `discount_percentage`: Float (Discount percentage)
  - `min_quantity`: Optional[Integer] (Minimum quantity required)

- **BxGyCoupon** - Buy X Get Y discount structure
  - `buy_products`: List[String] (Products for the "buy" part)
  - `buy_quantity`: Integer (Required quantity to buy)
  - `get_products`: List[String] (Products for the "get" part)
  - `get_quantity`: Integer (Quantity to get discounted)
  - `discount_percentage`: Float (Discount on "get" products)
  - `repetition_limit`: Optional[Integer] (Max repetitions of offer)

- **CouponCreate** - Main model for coupon creation
  - `coupon_id`: String (Unique identifier)
  - `type`: String (Coupon type)
  - `details`: Union[CartBasedCoupon, ProductBasedCoupon, BxGyCoupon, Dict]
  - `is_active`: Boolean (Default: True)
  - `valid_from`: Datetime (Start date)
  - `valid_until`: Optional[Datetime] (End date)
  - `user_tiers`: Optional[List[String]] (Eligible customer tiers)
  - `description`: String (Human-readable description)

### 3.2 MongoDB Schema

#### 3.2.1 Customers Collection
```javascript
{
  "_id": ObjectId,
  "name": String,
  "email": String,
  "tier": String, // "Basic", "Silver", "Gold", "Platinum"
  "cart": {
    "product_id": {
      "product_id": String,
      "quantity": Integer,
      "price": Float,
      "subtotal": Float
    },
    // Additional products...
  },
  "exclusive_coupons": {
    "coupon_id": Integer, // remaining uses
    // Additional exclusive coupons...
  },
  "coupon_history": [
    {
      "coupon_id": String,
      "coupon_type": String,
      "discount_amount": Float,
      "original_total": Float,
      "final_total": Float,
      "applied_at": DateTime
    },
    // Additional history entries...
  ]
}
```

#### 3.2.2 Products Collection
```javascript
{
  "_id": ObjectId,
  "product_id": String,
  "name": String,
  "price": Float,
  "stock": Integer
  // Additional product fields...
}
```

#### 3.2.3 Coupons Collection
```javascript
{
  "_id": ObjectId,
  "coupon_id": String,
  "type": String, // "cart-wise", "product-wise", "bxgy"
  "details": {
    // Specific fields based on coupon type
    // For cart-wise:
    "threshold": Float,
    "discount_percentage": Float,
    "max_discount": Float,
    
    // For product-wise:
    "product_ids": [String],
    "discount_percentage": Float,
    "min_quantity": Integer,
    
    // For bxgy:
    "buy_products": [String],
    "buy_quantity": Integer,
    "get_products": [String],
    "get_quantity": Integer,
    "discount_percentage": Float,
    "repetition_limit": Integer
  },
  "is_active": Boolean,
  "valid_from": DateTime,
  "valid_until": DateTime,
  "user_tiers": [String],
  "description": String
}
```

## 4. API Endpoints

### 4.1 Coupon Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/coupons` | POST | Create a new coupon |
| `/coupons` | GET | Retrieve all coupons |
| `/coupons/{coupon_id}` | GET | Retrieve a specific coupon by ID |
| `/coupons/{coupon_id}` | PUT | Update an existing coupon |
| `/coupons/{coupon_id}` | DELETE | Delete a coupon |

### 4.2 Cart Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/customers/{customer_id}/cart` | POST | Add a product to customer cart |
| `/customers/{customer_id}/cart` | GET | Get customer's current cart |
| `/customers/{customer_id}/cart/{product_id}` | DELETE | Remove a product from cart |
| `/customers/{customer_id}/cart/{product_id}` | PUT | Update the quantity of a product in cart |

### 4.3 Coupon Application

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/customers/{customer_id}/applicable-coupons` | GET | Get all coupons applicable to a customer's cart |
| `/customers/{customer_id}/apply-coupon/{coupon_id}` | POST | Apply a coupon to a customer's cart |

## 5. Business Logic

### 5.1 Coupon Types and Logic

#### 5.1.1 Cart-Based Coupons
- Applied to the entire cart total
- Requires cart total to meet a threshold value
- Applies percentage discount with optional maximum discount cap
- Example: "20% off on orders above $100, maximum discount $50"

#### 5.1.2 Product-Based Coupons
- Applied to specific products only
- Can require minimum quantity of eligible products
- Applies percentage discount to eligible products
- Example: "15% off on selected products when you buy 2 or more"

#### 5.1.3 Buy X Get Y (BxGy) Coupons
- Complex discount structure
- Requires purchasing specified quantity of eligible "buy" products
- Offers discount on specified "get" products
- Can have repetition limits
- Example: "Buy 2 shirts, get 1 tie free"

### 5.2 Discount Calculation Logic

#### 5.2.1 Cart-Based Discount
```python
if cart_total >= threshold:
    discount = min(
        cart_total * (discount_percentage / 100),
        max_discount  # If specified
    )
```

#### 5.2.2 Product-Based Discount
```python
discount = 0
for eligible_product in eligible_products:
    if quantity >= min_quantity:
        product_subtotal = quantity * price
        discount += product_subtotal * (discount_percentage / 100)
```

#### 5.2.3 BxGy Discount
```python
# Count eligible buy products
buy_units = total_buy_quantity // required_buy_quantity

# Apply repetition limit
buy_units = min(buy_units, repetition_limit)

# Calculate discountable get units
total_get_units = buy_units * get_quantity

# Apply discount to lowest-priced eligible get products first
# Sort get products by price (ascending)
# Apply discount up to total_get_units
```

### 5.3 Validation Rules

- Coupon must be active (`is_active = True`)
- Current date must be within validity period (`valid_from` ≤ current date ≤ `valid_until`)
- Customer's tier must be in eligible tiers list
- Cart must meet coupon's conditions (threshold, product presence, quantities)
- Exclusive coupons must have remaining uses

## 6. Technical Implementation Details

### 6.1 MongoDB Integration

- Direct connection to MongoDB using PyMongo
- Collections accessed through global client reference
- No ORM layer, using direct collection operations
- ObjectId handling for proper serialization

### 6.2 FastAPI Configuration

- OpenAPI documentation enabled
- Request validation through Pydantic models
- Exception handling for proper HTTP status codes
- JSON serialization with custom handler for ObjectId

### 6.3 Data Serialization Strategies

- Custom JSON serializer for MongoDB ObjectId
- Datetime handling for coupon validity periods
- Type conversion between API models and database documents

## 7. Testing Strategy

### 7.1 Unit Tests

- Test each API endpoint individually
- Mock MongoDB connections to avoid actual database operations
- Test happy paths and edge cases for each endpoint
- Verify calculation logic for different coupon types

### 7.2 Integration Tests

- Test API endpoints with actual MongoDB instance (test database)
- Verify end-to-end coupon application workflows
- Test interactions between different components

## 8. Deployment Architecture

### 8.1 Recommended Deployment Stack

- **Web Server**: Uvicorn/Gunicorn for ASGI serving
- **Database**: MongoDB (replica set recommended for production)
- **Container**: Docker for application containerization
- **Orchestration**: Kubernetes or Docker Compose
- **API Gateway**: Optional, for rate limiting and authentication
- **Monitoring**: Prometheus/Grafana for metrics

### 8.2 Deployment Diagram

```
┌─────────────────┐         ┌─────────────────┐
│                 │         │                 │
│  Load Balancer  │────────▶│   API Gateway   │
│                 │         │                 │
└─────────────────┘         └────────┬────────┘
                                    │
                                    ▼
                           ┌─────────────────┐
                           │                 │
                           │  FastAPI App    │◀──┐
                           │  (Containers)   │   │
                           │                 │   │ Scaling
                           └────────┬────────┘   │
                                    │            │
                                    ▼            │
                           ┌─────────────────┐   │
                           │                 │   │
                           │    MongoDB      │───┘
                           │                 │
                           └─────────────────┘
```

## 9. Security Considerations

### 9.1 Data Protection
- Implement proper authentication and authorization (not in current implementation)
- Consider encrypting sensitive customer data
- Implement rate limiting to prevent abuse

### 9.2 Input Validation
- All API inputs validated through Pydantic models
- Proper error handling for invalid inputs
- Protection against NoSQL injection (handled by PyMongo)

### 9.3 API Security
- Consider implementing JWT authentication
- Add role-based access control for admin endpoints
- Use HTTPS in production environments

## 10. Future Extensions

### 10.1 Additional Coupon Types
- Time-based coupons (happy hour, weekend specials)
- Bundled product discounts
- Tiered discounts based on purchase history
- First-time user coupons

### 10.2 Advanced Features
- Coupon analytics and performance tracking
- A/B testing for coupon effectiveness
- Automated coupon generation based on business rules
- Personalized coupon recommendations
- Integration with marketing platforms

### 10.3 Performance Improvements
- Implement caching for frequently accessed coupons
- Database indexing strategy for optimized queries
- Background tasks for analytics processing
- Horizontal scaling for high-volume scenarios

## 11. Conclusion

The Coupon Management System provides a flexible and robust framework for implementing complex discount strategies in e-commerce applications. Its modular architecture allows for easy extension and integration with existing systems while providing powerful discount calculation capabilities.
