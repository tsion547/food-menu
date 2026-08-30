import json
import os
import uuid

from flask import Flask, render_template, jsonify, request

from models import db, Order, MenuItem, Admin
from auth import generate_token, admin_required

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# In production, set SECRET_KEY, ADMIN_USERNAME and ADMIN_PASSWORD as real
# environment variables instead of relying on the defaults below.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'tastybite-secret-key-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'orders.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_EXP_HOURS'] = 2

# ----- Menu image uploads -----
# Uploaded dish photos are stored under static/images/uploads so they are
# served the same way as the seeded images (via url_for('static', ...)).
UPLOAD_SUBDIR = 'images/uploads'
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', UPLOAD_SUBDIR)
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB upload limit

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db.init_app(app)


def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def delete_uploaded_image(image_path):
    """Remove a previously uploaded dish photo from disk (best-effort).

    Only files that live inside our own uploads folder are ever touched -
    the seeded/default images (images/doro.jpg etc.) are left alone.
    """
    if not image_path or not image_path.startswith(UPLOAD_SUBDIR + '/'):
        return
    full_path = os.path.join(BASE_DIR, 'static', image_path)
    try:
        if os.path.isfile(full_path):
            os.remove(full_path)
    except OSError:
        pass


@app.errorhandler(413)
def handle_file_too_large(_error):
    return jsonify({"error": "image is too large (max 5MB)"}), 413

DEFAULT_MENU = [
    {"name": "Doro Wat", "description": "Spicy chicken stew cooked in berbere sauce and butter.", "price": 120, "image": "images/doro.jpg"},
    {"name": "Shiro Wat", "description": "Chickpea stew simmered with spices and berbere.", "price": 100, "image": "images/shiro.jpg"},
    {"name": "Kitfo", "description": "Minced raw beef seasoned with mitmita and spices.", "price": 150, "image": "images/kitfo.jpg"},
    {"name": "Tibs", "description": "Stir-fried beef with onions, peppers and spices.", "price": 230, "image": "images/tibs.jpg"},
    {"name": "Veggie Combo", "description": "A combination of our delicious vegetarian dishes.", "price": 90, "image": "images/veggie.jpg"},
]


def seed_menu():
    if MenuItem.query.count() == 0:
        for item in DEFAULT_MENU:
            db.session.add(MenuItem(**item))
        db.session.commit()


def seed_admin():
    if Admin.query.count() == 0:
        username = os.environ.get('ADMIN_USERNAME', 'admin')
        password = os.environ.get('ADMIN_PASSWORD', 'Admin@123')
        admin = Admin(username=username, role='admin')
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print('=' * 60)
        print(f'Created default admin account -> username: "{username}"  password: "{password}"')
        print('Change this password / set ADMIN_USERNAME & ADMIN_PASSWORD env vars in production.')
        print('=' * 60)


with app.app_context():
    db.create_all()
    seed_menu()
    seed_admin()


# ======================================================================
# Public site (no login required)
# ======================================================================

@app.route('/')
def index():
    menu = MenuItem.query.order_by(MenuItem.id).all()
    return render_template('index.html', menu=menu)


@app.route('/admin/login')
def admin_login_page():
    return render_template('admin_login.html')


@app.route('/admin/dashboard')
def admin_dashboard_page():
    return render_template('admin_dashboard.html')


# ======================================================================
# Public customer API (no login required)
# ======================================================================

@app.route('/api/menu', methods=['GET'])
def api_get_menu():
    items = MenuItem.query.order_by(MenuItem.id).all()
    return jsonify([i.to_dict() for i in items])


@app.route('/api/orders', methods=['POST'])
def api_add_order():
    """Customers can place an order without logging in."""
    data = request.get_json()

    if not data or 'items' not in data or len(data['items']) < 1:
        return jsonify({"error": "order needs at least one item"}), 400

    customer = (data.get('customer') or '').strip() or 'Walk-in Customer'
    items = data['items']
    quantity = sum(int(item.get('qty', 0)) for item in items)
    total_price = float(data.get('total', 0))

    order = Order(
        customer=customer,
        items=json.dumps(items),
        quantity=quantity,
        total_price=total_price,
        status='Pending'
    )
    db.session.add(order)
    db.session.commit()

    return jsonify({"message": "order saved", "order": order.to_dict()}), 201


@app.route('/api/orders/<int:order_id>', methods=['GET'])
def api_get_order_by_id(order_id):
    """Customers can look up their own order using just its ID - no login needed."""
    order = Order.query.get(order_id)
    if not order:
        return jsonify({"error": "order not found"}), 404
    return jsonify(order.to_dict())


# ======================================================================
# Admin authentication
# ======================================================================

@app.route('/api/admin/login', methods=['POST'])
def api_admin_login():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    admin = Admin.query.filter_by(username=username).first()

    if not admin or not admin.check_password(password):
        return jsonify({"error": "invalid username or password"}), 401

    token = generate_token(admin, expires_in_hours=app.config['JWT_EXP_HOURS'])
    return jsonify({
        "message": "login successful",
        "token": token,
        "admin": admin.to_dict(),
        "expires_in_hours": app.config['JWT_EXP_HOURS'],
    })


# ======================================================================
# Admin API - every route below requires a valid admin JWT
#   401 -> missing / invalid / expired token
#   403 -> valid token but not an admin role
# ======================================================================

@app.route('/api/admin/orders', methods=['GET'])
@admin_required
def api_admin_list_orders():
    orders = Order.query.order_by(Order.date_time.desc()).all()
    return jsonify([o.to_dict() for o in orders])


@app.route('/api/admin/orders', methods=['POST'])
@admin_required
def api_admin_add_order():
    data = request.get_json() or {}
    customer = (data.get('customer') or '').strip()
    items = data.get('items') or []
    total_price = data.get('total_price')

    if not customer or not items or total_price is None:
        return jsonify({"error": "customer, items and total_price are required"}), 400

    quantity = sum(int(item.get('qty', 1)) for item in items)

    order = Order(
        customer=customer,
        items=json.dumps(items),
        quantity=quantity,
        total_price=float(total_price),
        status=data.get('status', 'Pending')
    )
    db.session.add(order)
    db.session.commit()
    return jsonify({"message": "order created", "order": order.to_dict()}), 201


@app.route('/api/admin/orders/<int:order_id>', methods=['PUT'])
@admin_required
def api_admin_update_order(order_id):
    order = Order.query.get_or_404(order_id)
    data = request.get_json() or {}

    if 'status' in data:
        order.status = data['status']
    if 'customer' in data:
        order.customer = data['customer']
    if 'items' in data:
        order.items = json.dumps(data['items'])
        order.quantity = sum(int(i.get('qty', 1)) for i in data['items'])
    if 'total_price' in data:
        order.total_price = float(data['total_price'])

    db.session.commit()
    return jsonify({"message": "order updated", "order": order.to_dict()})


@app.route('/api/admin/orders/<int:order_id>', methods=['DELETE'])
@admin_required
def api_admin_delete_order(order_id):
    order = Order.query.get_or_404(order_id)
    db.session.delete(order)
    db.session.commit()
    return jsonify({"message": "order deleted"})


@app.route('/api/admin/upload', methods=['POST'])
@admin_required
def api_admin_upload_image():
    """Accepts a single image file (multipart/form-data, field name 'image')
    and stores it under static/images/uploads with a random filename so an
    admin never has to know or type a file path by hand.
    """
    if 'image' not in request.files:
        return jsonify({"error": "no image file provided"}), 400

    file = request.files['image']

    if not file or file.filename == '':
        return jsonify({"error": "no file selected"}), 400

    if not allowed_image_file(file.filename):
        return jsonify({"error": "unsupported file type - use PNG, JPG, GIF or WEBP"}), 400

    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(UPLOAD_FOLDER, filename))

    image_path = f"{UPLOAD_SUBDIR}/{filename}"
    return jsonify({"message": "image uploaded", "path": image_path}), 201


@app.route('/api/admin/menu', methods=['GET'])
@admin_required
def api_admin_list_menu():
    items = MenuItem.query.order_by(MenuItem.id).all()
    return jsonify([i.to_dict() for i in items])


@app.route('/api/admin/menu', methods=['POST'])
@admin_required
def api_admin_add_menu_item():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    price = data.get('price')

    if not name or price is None:
        return jsonify({"error": "name and price are required"}), 400

    if MenuItem.query.filter_by(name=name).first():
        return jsonify({"error": "a menu item with that name already exists"}), 400

    item = MenuItem(
        name=name,
        description=data.get('description', ''),
        price=float(price),
        image=data.get('image', '')
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({"message": "menu item added", "item": item.to_dict()}), 201


@app.route('/api/admin/menu/<int:item_id>', methods=['PUT'])
@admin_required
def api_admin_update_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    data = request.get_json() or {}

    if 'name' in data:
        item.name = data['name'].strip()
    if 'description' in data:
        item.description = data['description']
    if 'price' in data:
        item.price = float(data['price'])
    if 'image' in data and data['image'] != item.image:
        old_image = item.image
        item.image = data['image']
        delete_uploaded_image(old_image)

    db.session.commit()
    return jsonify({"message": "menu item updated", "item": item.to_dict()})


@app.route('/api/admin/menu/<int:item_id>', methods=['DELETE'])
@admin_required
def api_admin_delete_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    delete_uploaded_image(item.image)
    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "menu item deleted"})


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
