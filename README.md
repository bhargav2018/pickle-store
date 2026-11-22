# Pickle Store – Homemade Pickles & Snacks

A Django-based e-commerce web application for selling homemade pickles and snacks. Customers can browse products, manage a shopping cart, place orders, and view their order history.

Built using Python, Django, MySQL, HTML, CSS, and JavaScript.

## Features

### Customer Features
- User registration, login, and logout.
- Secure password hashing using Django authentication.
- Product catalogue with product images, descriptions, prices, categories, and stock availability.
- Search and filter products.
- Add products to a session-based shopping cart.
- Update product quantities and remove items from the cart.
- Checkout with customer and delivery information.
- Multiple products in a single order.
- Select from available payment methods.
- View order confirmation and personal order history.

### Product and Order Management
- Manage products through Django Admin.
- Track product stock.
- Prevent customers from ordering unavailable quantities.
- Recheck stock during checkout.
- Use database transactions to protect order creation and stock updates.
- Preserve the product price at the time of purchase.
- Manage order statuses through Django Admin.

### Security
- Django's built-in authentication system.
- Password hashing and password validation.
- Environment-based configuration using `.env`.
- Production settings for secure session and CSRF cookies.
- Configurable allowed hosts and trusted CSRF origins