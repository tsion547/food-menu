# TastyBite - Hotel Menu System (SQLite + JWT Admin Auth)

Ethiopian restaurant menu & ordering site. Customers order without an account;
admins log in and manage orders/menu behind a JWT-protected API.

## Setup

```bash
python -m venv venv
source venv/bin/activate   # venv\Scripts\activate on Windows
pip install -r requirements.txt
python app.py
```

Visit `http://127.0.0.1:5000/`. `orders.db` is created automatically on first
run, along with a default admin account and the starter menu (both printed to
the console on first launch).

**Default admin login:** `admin` / `Admin@123` — printed to the console the
first time the app runs. Override before deploying with environment
variables:

```bash
export SECRET_KEY="something-long-and-random"
export ADMIN_USERNAME="your_admin"
export ADMIN_PASSWORD="a-strong-password"
```

## How auth works

- Passwords are hashed with Werkzeug's `generate_password_hash` /
  `check_password_hash` (PBKDF2) — never stored in plain text.
- On login, the server issues a **JWT** (via `PyJWT`) containing the admin's
  `admin_id` and `role`, signed with `SECRET_KEY` and expiring after 2 hours
  (`JWT_EXP_HOURS` in `app.py`).
- The admin dashboard stores this token in `localStorage` and sends it as
  `Authorization: Bearer <token>` on every admin API call (`static/js/admin.js`).
- Every `/api/admin/*` route is wrapped in the `@admin_required` decorator
  (`auth.py`), which returns:
  - **401** if the token is missing, malformed, or expired
  - **403** if the token is valid but its role isn't `admin`

## Routes

**Public (no login)**
- `GET /` — homepage, menu, cart, order tracking
- `GET /api/menu` — menu items (JSON)
- `POST /api/orders` — place an order
- `GET /api/orders/<id>` — look up an order by ID (customer receipt lookup)
- `GET /admin/login` — admin login page
- `POST /api/admin/login` — exchanges username/password for a JWT

**Admin (JWT required)**
- `GET /admin/dashboard` — dashboard shell (orders / add order / menu tabs); guarded client-side, all real data comes from the protected endpoints below
- `GET /api/admin/orders` — list all orders
- `POST /api/admin/orders` — create an order manually
- `PUT /api/admin/orders/<id>` — update an order (status, items, etc.)
- `DELETE /api/admin/orders/<id>` — delete an order
- `GET /api/admin/menu` — list menu items (admin view)
- `POST /api/admin/menu` — add a menu item
- `PUT /api/admin/menu/<id>` — update a menu item
- `DELETE /api/admin/menu/<id>` — delete a menu item
- `POST /api/admin/upload` — upload a dish photo (multipart file), returns its saved path

## Notes

- `orders.db` and `venv/` are excluded via `.gitignore`.
- Menu items now live in the database (`MenuItem` table) instead of being
  hardcoded, so the admin dashboard's "Manage Menu Items" tab actually
  changes what customers see on the homepage.
