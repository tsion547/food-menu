from datetime import datetime
import json

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    customer = db.Column(db.String(120), nullable=False)
    items = db.Column(db.Text, nullable=False)          # JSON-encoded list of {name, price, qty}
    quantity = db.Column(db.Integer, nullable=False, default=0)
    total_price = db.Column(db.Float, nullable=False, default=0)
    date_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Pending')

    def get_items(self):
        """Decode the stored JSON items string back into a Python list."""
        try:
            return json.loads(self.items)
        except (TypeError, ValueError):
            return []

    def to_dict(self):
        return {
            "id": self.id,
            "customer": self.customer,
            "items": self.get_items(),
            "quantity": self.quantity,
            "total_price": self.total_price,
            "date_time": self.date_time.strftime('%Y-%m-%d %H:%M:%S'),
            "status": self.status,
        }


class MenuItem(db.Model):
    __tablename__ = 'menu_items'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.String(300), default='')
    price = db.Column(db.Float, nullable=False)
    image = db.Column(db.String(200), default='')

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "image": self.image,
        }


class Admin(db.Model):
    __tablename__ = 'admins'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='admin')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {"id": self.id, "username": self.username, "role": self.role}
