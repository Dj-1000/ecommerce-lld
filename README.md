# LLD FastAPI E-Commerce

Initial implementation of the e-commerce LLD.

## Current scope

Implemented as the first architectural foundation:

- FastAPI application
- PostgreSQL-ready async SQLAlchemy setup
- Core domain models:
  - User
  - Product
  - ProductVariant
  - Cart / CartItem
  - Address
  - Inventory / InventoryReservation
  - Order / OrderItem
  - Payment
- Order state machine vocabulary:
  - PENDING_PAYMENT
  - PAYMENT_SUCCEEDED
  - PAYMENT_FAILED
  - CANCELLED
- Delivery address snapshot is stored on the order and is intended to be immutable after order creation.
- No fulfillment/shipping/delivery states are modeled.

## Deliberately not implemented yet

- Checkout service
- Payment gateway integration
- Inventory locking/reservation service
- Cancellation/refund service
- Authentication
- CRUD APIs
- React frontend
- Alembic migrations

Those will be implemented one business operation at a time after validating the domain model.
