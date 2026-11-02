import os
import re
from datetime import datetime
from functools import wraps
from math import asin, cos, radians, sin, sqrt

import click
from flask import Flask, jsonify, request, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, inspect, text
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

BOOKING_STATUSES = {"pending", "accepted", "in_progress", "completed", "cancelled"}
PAYMENT_METHODS = {"mpesa", "cash"}
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_GPS_RADIUS_KM = 100


class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    icon = db.Column(db.String(10), nullable=False, default="✨")
    base_price = db.Column(db.Integer, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)


class Stylist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(150), nullable=False)
    rating = db.Column(db.Float, nullable=False, default=0)
    total_reviews = db.Column(db.Integer, nullable=False, default=0)
    specialties = db.Column(db.String(300), nullable=False)
    bio = db.Column(db.Text, nullable=False)
    offers_home_visit = db.Column(db.Boolean, nullable=False, default=True)
    offers_salon = db.Column(db.Boolean, nullable=False, default=True)
    is_approved = db.Column(db.Boolean, nullable=False, default=True)
    is_available = db.Column(db.Boolean, nullable=False, default=True)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)


class StylistAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stylist_id = db.Column(db.Integer, db.ForeignKey("stylist.id"), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    stylist = db.relationship("Stylist", backref=db.backref("account", uselist=False))


class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)


class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False)
    stylist_id = db.Column(db.Integer, db.ForeignKey("stylist.id"), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=False)
    scheduled_date = db.Column(db.DateTime, nullable=False)
    booking_type = db.Column(db.String(20), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    notes = db.Column(db.Text, nullable=False, default="")
    service_price = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    payment_method = db.Column(db.String(20), nullable=False)
    payment_status = db.Column(db.String(20), nullable=False, default="unpaid")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    customer = db.relationship("Customer")
    stylist = db.relationship("Stylist")
    service = db.relationship("Service")


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("booking.id"), unique=True, nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.String(1000), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    booking = db.relationship("Booking", backref=db.backref("review", uselist=False))


def _service_json(service):
    return {
        "id": service.id,
        "name": service.name,
        "category": service.category,
        "description": service.description,
        "icon": service.icon,
        "base_price": service.base_price,
        "duration_minutes": service.duration_minutes,
    }


def _stylist_json(stylist):
    return {
        "id": stylist.id,
        "name": stylist.name,
        "location": stylist.location,
        "rating": stylist.rating,
        "total_reviews": stylist.total_reviews,
        "specialties": stylist.specialties,
        "bio": stylist.bio,
        "offers_home_visit": stylist.offers_home_visit,
        "offers_salon": stylist.offers_salon,
        "has_gps_location": stylist.latitude is not None and stylist.longitude is not None,
    }


def _coordinates(data):
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    if latitude is None and longitude is None:
        return None, None, None
    if isinstance(latitude, bool) or isinstance(longitude, bool):
        return None, None, "GPS coordinates must be numbers."
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return None, None, "GPS coordinates must be numbers."
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None, None, "GPS coordinates are outside the valid range."
    return latitude, longitude, None


def _distance_km(latitude, longitude, other_latitude, other_longitude):
    latitude_delta = radians(other_latitude - latitude)
    longitude_delta = radians(other_longitude - longitude)
    distance = (
        sin(latitude_delta / 2) ** 2
        + cos(radians(latitude))
        * cos(radians(other_latitude))
        * sin(longitude_delta / 2) ** 2
    )
    return 6371 * 2 * asin(sqrt(distance))


def _booking_json(booking):
    return {
        "id": booking.id,
        "customer_id": booking.customer_id,
        "customer_name": booking.customer.name,
        "stylist_id": booking.stylist_id,
        "stylist_name": booking.stylist.name,
        "service_id": booking.service_id,
        "service_name": booking.service.name,
        "scheduled_date": booking.scheduled_date.isoformat(timespec="minutes"),
        "booking_type": booking.booking_type,
        "location": booking.location,
        "latitude": booking.latitude,
        "longitude": booking.longitude,
        "notes": booking.notes,
        "service_price": booking.service_price,
        "status": booking.status,
        "payment_method": booking.payment_method,
        "payment_status": booking.payment_status,
        "created_at": booking.created_at.isoformat(timespec="minutes"),
        "review": _review_json(booking.review) if booking.review else None,
    }


def _review_json(review):
    return {
        "id": review.id,
        "booking_id": review.booking_id,
        "rating": review.rating,
        "comment": review.comment,
        "customer_name": review.booking.customer.name,
        "created_at": review.created_at.isoformat(timespec="minutes"),
    }


def _error(message, status=400):
    return jsonify({"error": message}), status


def _payload():
    if not request.is_json:
        return None, _error("Send request data as JSON.")
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, _error("Request body must be a JSON object.")
    return data, None


def _required_text(data, field, label, maximum=200):
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        return None, f"{label} is required."
    value = value.strip()
    if len(value) > maximum:
        return None, f"{label} must be {maximum} characters or fewer."
    return value, None


def _valid_email(value):
    return isinstance(value, str) and len(value) <= 120 and EMAIL_PATTERN.fullmatch(value.strip()) is not None


def _password(data):
    value = data.get("password")
    if not isinstance(value, str) or not 8 <= len(value) <= 128:
        return None, "Password must be between 8 and 128 characters."
    return value, None


def _current_role_id(role):
    return session.get(f"{role}_id") if session.get("role") == role else None


def _login_required(role):
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user_id = _current_role_id(role)
            if user_id is None:
                return _error("Please sign in to continue.", 401)
            return view(user_id, *args, **kwargs)

        return wrapped

    return decorate


def _admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        admin_id = _current_role_id("admin")
        if admin_id is None:
            return _error("Administrator access is required.", 401)
        return view(admin_id, *args, **kwargs)

    return wrapped


def seed_database():
    services = [
        Service(name="Knotless braids", category="Braids", description="Lightweight, natural-looking braids with a flawless finish.", icon="✨", base_price=2500, duration_minutes=240),
        Service(name="Classic box braids", category="Braids", description="A timeless protective style, tailored to your preferred length.", icon="🪮", base_price=1800, duration_minutes=210),
        Service(name="Cornrows", category="Braids", description="Clean, detailed cornrows for everyday wear or a special occasion.", icon="〰️", base_price=1200, duration_minutes=120),
        Service(name="Goddess braids", category="Braids", description="Soft, flowing goddess braids with curls for a statement protective style.", icon="✨", base_price=2800, duration_minutes=240),
        Service(name="Crochet braids", category="Braids", description="A versatile crochet protective style, fitted and shaped to your preference.", icon="🪮", base_price=2000, duration_minutes=180),
        Service(name="Faux locs", category="Braids", description="Beautiful loc-inspired extensions, installed with care and attention to comfort.", icon="✨", base_price=3500, duration_minutes=300),
        Service(name="Wig installation", category="Wig styling", description="A secure, seamless install styled to complement your look.", icon="💇🏾‍♀️", base_price=1800, duration_minutes=90),
        Service(name="Wig styling", category="Wig styling", description="Custom shaping, curls, or a sleek finish for your favourite unit.", icon="💫", base_price=1200, duration_minutes=60),
        Service(name="Wig wash & revamp", category="Wig styling", description="Cleanse, condition, and restyle your wig to bring it back to life.", icon="💇🏾‍♀️", base_price=2200, duration_minutes=120),
        Service(name="Wash & treatment", category="Hair care", description="A refreshing wash and nourishing treatment for healthy hair.", icon="🧴", base_price=900, duration_minutes=60),
        Service(name="Blow-dry & style", category="Hair care", description="A smooth, bouncy blow-dry finished just the way you like it.", icon="🌬️", base_price=1000, duration_minutes=60),
        Service(name="Hair colouring", category="Hair care", description="Refresh your colour with a consultation and a considered finish.", icon="🎨", base_price=3000, duration_minutes=150),
        Service(name="Silk press", category="Hair care", description="A smooth, lightweight silk press finished with heat-protective care.", icon="✨", base_price=2200, duration_minutes=120),
        Service(name="Hair trim", category="Hair care", description="A consultation-led trim to tidy ends and help maintain healthy hair.", icon="✂️", base_price=800, duration_minutes=45),
        Service(name="Scalp treatment", category="Hair care", description="A soothing scalp cleanse and conditioning treatment for a fresh start.", icon="🧴", base_price=1200, duration_minutes=60),
        Service(name="Makeup application", category="Makeup & nails", description="Soft glam or full glam, expertly applied for your occasion.", icon="💄", base_price=2200, duration_minutes=75),
        Service(name="Bridal makeup", category="Makeup", description="A personalised bridal makeup look, planned to last through your celebration.", icon="💄", base_price=5000, duration_minutes=150),
        Service(name="Event makeup", category="Makeup", description="Professional makeup for celebrations, photos, and special occasions.", icon="💄", base_price=3000, duration_minutes=90),
        Service(name="Manicure", category="Nails", description="A tidy, relaxing manicure with your choice of polish.", icon="💅🏾", base_price=1200, duration_minutes=60),
        Service(name="Gel manicure", category="Nails", description="A carefully shaped manicure with a durable gel-polish finish.", icon="💅🏾", base_price=1800, duration_minutes=75),
        Service(name="Spa pedicure", category="Nails", description="A relaxing foot soak, nail tidy, and moisturising pedicure.", icon="💅🏾", base_price=1800, duration_minutes=75),
        Service(name="Acrylic nail extensions", category="Nails", description="Custom-length acrylic extensions, shaped and finished in your chosen style.", icon="💅🏾", base_price=2500, duration_minutes=120),
        Service(name="Lash extensions", category="Brows & lashes", description="A lightweight lash set designed to bring out your eyes.", icon="👁️", base_price=1800, duration_minutes=90),
        Service(name="Lash lift & tint", category="Brows & lashes", description="A lifted, defined lash look using your natural lashes.", icon="👁️", base_price=2200, duration_minutes=60),
        Service(name="Brow shaping", category="Brows & lashes", description="A brow consultation and shaping service tailored to your features.", icon="✦", base_price=800, duration_minutes=30),
        Service(name="Brow tint", category="Brows & lashes", description="A consultation-led tint to define your natural brow shape.", icon="✦", base_price=1000, duration_minutes=30),
        Service(name="Express facial", category="Skin & spa", description="A gentle cleanse, exfoliation, and hydration tailored to your skin.", icon="🧖🏾‍♀️", base_price=2500, duration_minutes=60),
        Service(name="Relaxing facial", category="Skin & spa", description="A longer facial with a skin consultation and soothing treatment.", icon="🧖🏾‍♀️", base_price=3500, duration_minutes=90),
        Service(name="Face waxing", category="Skin & spa", description="Professional facial waxing for brows, upper lip, or chin.", icon="✨", base_price=1200, duration_minutes=30),
    ]
    existing_service_names = {service.name for service in Service.query.all()}
    db.session.add_all(
        service for service in services if service.name not in existing_service_names
    )

    if Stylist.query.count() == 0:
        db.session.add_all(
            [
                Stylist(name="Nia Wanjiku", location="Westlands, Nairobi", rating=4.9, total_reviews=128, specialties="Knotless braids · Natural hair", bio="I create protective styles that feel as good as they look. Every appointment starts with listening to what you want.", offers_home_visit=True, offers_salon=True),
                Stylist(name="Amani Otieno", location="Kilimani, Nairobi", rating=4.8, total_reviews=96, specialties="Wig installs · Colour", bio="Detail-focused stylist helping you find a look that fits your day, your style, and your hair.", offers_home_visit=True, offers_salon=True),
                Stylist(name="Zuri Kamau", location="Lavington, Nairobi", rating=4.9, total_reviews=84, specialties="Makeup · Bridal glam", bio="From soft glam to your big-day look, I make getting ready feel calm, personal, and fun.", offers_home_visit=True, offers_salon=False),
                Stylist(name="Imani Achieng", location="Parklands, Nairobi", rating=4.7, total_reviews=73, specialties="Cornrows · Hair care", bio="Healthy hair and thoughtful, long-lasting styles are at the heart of every service I offer.", offers_home_visit=False, offers_salon=True),
            ]
        )

    admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    if bool(admin_email) != bool(admin_password):
        raise RuntimeError("Set both ADMIN_EMAIL and ADMIN_PASSWORD, or neither.")
    if admin_email and (not _valid_email(admin_email) or not 8 <= len(admin_password) <= 128):
        raise ValueError("Seed admin credentials must use a valid email and an 8–128 character password.")
    if admin_email and admin_password and Admin.query.filter_by(email=admin_email).first() is None:
        admin = Admin(name=os.environ.get("ADMIN_NAME", "GlamRide Admin"), email=admin_email)
        admin.password_hash = generate_password_hash(admin_password)
        db.session.add(admin)
    db.session.commit()


def upgrade_schema():
    additions = {
        "stylist": {
            "latitude": "FLOAT",
            "longitude": "FLOAT",
        },
        "booking": {
            "latitude": "FLOAT",
            "longitude": "FLOAT",
        },
    }
    inspector = inspect(db.engine)
    for table, columns in additions.items():
        if not inspector.has_table(table):
            continue
        existing = {column["name"] for column in inspector.get_columns(table)}
        for column, column_type in columns.items():
            if column not in existing:
                db.session.execute(
                    text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {column_type}')
                )
    db.session.commit()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or os.urandom(32),
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", "sqlite:///glamride.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE") == "1",
    )
    if test_config:
        app.config.update(test_config)
    db.init_app(app)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api/services")
    def services():
        query = Service.query
        category = request.args.get("category", "").strip()
        if category and category.lower() != "all":
            query = query.filter(func.lower(Service.category) == category.lower())
        return jsonify([_service_json(service) for service in query.order_by(Service.name.asc()).all()])

    @app.get("/api/stylists")
    def stylists():
        query = Stylist.query.filter_by(is_approved=True, is_available=True)
        location = request.args.get("location", "").strip()
        latitude_arg = request.args.get("latitude")
        longitude_arg = request.args.get("longitude")
        radius_arg = request.args.get("radius_km", "25")
        if (latitude_arg is None) != (longitude_arg is None):
            return _error("Share both GPS coordinates to search nearby.")
        if latitude_arg is not None:
            latitude, longitude, error_message = _coordinates(
                {"latitude": latitude_arg, "longitude": longitude_arg}
            )
            if error_message:
                return _error(error_message)
            try:
                radius_km = float(radius_arg)
            except (TypeError, ValueError):
                return _error("Search radius must be a number from 1 to 100 km.")
            if not 1 <= radius_km <= MAX_GPS_RADIUS_KM:
                return _error("Search radius must be from 1 to 100 km.")
        else:
            latitude = longitude = radius_km = None
        if location:
            query = query.filter(Stylist.location.ilike(f"%{location}%"))
        results = []
        for stylist in query.order_by(Stylist.rating.desc(), Stylist.name.asc()).all():
            item = _stylist_json(stylist)
            if latitude is not None and stylist.latitude is not None and stylist.longitude is not None:
                distance = _distance_km(latitude, longitude, stylist.latitude, stylist.longitude)
                if distance <= radius_km:
                    item["distance_km"] = round(distance, 1)
                    results.append(item)
            elif latitude is None:
                results.append(item)
        if latitude is not None:
            results.sort(key=lambda item: (item.get("distance_km", float("inf")), -item["rating"]))
        return jsonify(results)

    @app.get("/api/stylists/<int:stylist_id>")
    def stylist_detail(stylist_id):
        stylist = db.session.get(Stylist, stylist_id)
        if stylist is None or not stylist.is_approved:
            return _error("Stylist not found.", 404)
        return jsonify(_stylist_json(stylist))

    @app.get("/api/stylists/<int:stylist_id>/reviews")
    def stylist_reviews(stylist_id):
        stylist = db.session.get(Stylist, stylist_id)
        if stylist is None or not stylist.is_approved:
            return _error("Stylist not found.", 404)
        reviews = (
            Review.query.join(Booking)
            .filter(Booking.stylist_id == stylist_id)
            .order_by(Review.created_at.desc())
            .limit(50)
            .all()
        )
        return jsonify([_review_json(review) for review in reviews])

    @app.post("/api/register")
    def register_customer():
        data, error = _payload()
        if error:
            return error
        name, error_message = _required_text(data, "name", "Name", 100)
        if error_message:
            return _error(error_message)
        email = data.get("email", "")
        if not _valid_email(email):
            return _error("Enter a valid email address.")
        email = email.strip().lower()
        phone, error_message = _required_text(data, "phone", "Phone number", 30)
        if error_message:
            return _error(error_message)
        password, error_message = _password(data)
        if error_message:
            return _error(error_message)
        if Customer.query.filter_by(email=email).first() or StylistAccount.query.filter_by(email=email).first() or Admin.query.filter_by(email=email).first():
            return _error("An account with that email already exists.", 409)
        customer = Customer(name=name, email=email, phone=phone, password_hash=generate_password_hash(password))
        db.session.add(customer)
        db.session.commit()
        session.clear()
        session.update(role="customer", customer_id=customer.id)
        return jsonify({"role": "customer", "name": customer.name, "email": customer.email}), 201

    @app.post("/api/stylist/register")
    def register_stylist():
        data, error = _payload()
        if error:
            return error
        name, error_message = _required_text(data, "name", "Name", 100)
        if error_message:
            return _error(error_message)
        email = data.get("email", "")
        if not _valid_email(email):
            return _error("Enter a valid email address.")
        email = email.strip().lower()
        phone, error_message = _required_text(data, "phone", "Phone number", 30)
        if error_message:
            return _error(error_message)
        password, error_message = _password(data)
        if error_message:
            return _error(error_message)
        location, error_message = _required_text(data, "location", "Location", 150)
        if error_message:
            return _error(error_message)
        specialties, error_message = _required_text(data, "specialties", "Specialties", 300)
        if error_message:
            return _error(error_message)
        bio, error_message = _required_text(data, "bio", "Bio", 1500)
        if error_message:
            return _error(error_message)
        latitude, longitude, error_message = _coordinates(data)
        if error_message:
            return _error(error_message)
        if (latitude is None) != (longitude is None):
            return _error("Share both GPS coordinates to set your location.")
        offers_home_visit = data.get("offers_home_visit", True)
        offers_salon = data.get("offers_salon", True)
        if not isinstance(offers_home_visit, bool) or not isinstance(offers_salon, bool):
            return _error("Choose valid appointment options.")
        if not offers_home_visit and not offers_salon:
            return _error("Offer home visits, salon appointments, or both.")
        if Customer.query.filter_by(email=email).first() or StylistAccount.query.filter_by(email=email).first() or Admin.query.filter_by(email=email).first():
            return _error("An account with that email already exists.", 409)
        stylist = Stylist(
            name=name,
            location=location,
            specialties=specialties,
            bio=bio,
            is_approved=False,
            is_available=False,
            offers_home_visit=offers_home_visit,
            offers_salon=offers_salon,
            latitude=latitude,
            longitude=longitude,
        )
        db.session.add(stylist)
        db.session.flush()
        account = StylistAccount(
            stylist_id=stylist.id,
            email=email,
            phone=phone,
            password_hash=generate_password_hash(password),
        )
        db.session.add(account)
        db.session.commit()
        session.clear()
        session.update(role="stylist", stylist_id=stylist.id)
        return jsonify({"role": "stylist", "name": stylist.name, "email": account.email, "is_approved": False}), 201

    @app.post("/api/login")
    def login():
        data, error = _payload()
        if error:
            return error
        email = data.get("email", "")
        password = data.get("password", "")
        role = data.get("role", "customer")
        if not _valid_email(email) or not isinstance(password, str) or not password or role not in {"customer", "stylist", "admin"}:
            return _error("Enter a valid email, password, and account type.")
        email = email.strip().lower()
        account = None
        if role == "customer":
            account = Customer.query.filter_by(email=email).first()
        elif role == "stylist":
            account = StylistAccount.query.filter_by(email=email).first()
        else:
            account = Admin.query.filter_by(email=email).first()
        if account is None or not check_password_hash(account.password_hash, password):
            return _error("Email or password is incorrect.", 401)
        session.clear()
        if role == "stylist":
            session.update(role=role, stylist_id=account.stylist_id)
            name = account.stylist.name
        else:
            session.update(role=role, **{f"{role}_id": account.id})
            name = account.name
        return jsonify({"role": role, "name": name, "email": account.email})

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify({"message": "Signed out."})

    @app.get("/api/me")
    def me():
        role = session.get("role")
        if role == "customer":
            user = db.session.get(Customer, session.get("customer_id"))
            if user:
                return jsonify({"role": role, "name": user.name, "email": user.email, "id": user.id})
        elif role == "stylist":
            stylist = db.session.get(Stylist, session.get("stylist_id"))
            if stylist and stylist.account:
                return jsonify({"role": role, "name": stylist.name, "email": stylist.account.email, "id": stylist.id, "is_approved": stylist.is_approved, "is_available": stylist.is_available})
        elif role == "admin":
            admin = db.session.get(Admin, session.get("admin_id"))
            if admin:
                return jsonify({"role": role, "name": admin.name, "email": admin.email, "id": admin.id})
        session.clear()
        return _error("Not signed in.", 401)

    @app.post("/api/bookings")
    @_login_required("customer")
    def create_booking(customer_id):
        data, error = _payload()
        if error:
            return error
        try:
            service_id = int(data.get("service_id"))
            stylist_id = int(data.get("stylist_id"))
        except (TypeError, ValueError):
            return _error("Choose a service and stylist.")
        service = db.session.get(Service, service_id)
        stylist = db.session.get(Stylist, stylist_id)
        if service is None:
            return _error("That service could not be found.")
        if stylist is None or not stylist.is_approved or not stylist.is_available:
            return _error("That stylist is not available for bookings.")
        try:
            scheduled_date = datetime.fromisoformat(data.get("scheduled_date", ""))
        except (TypeError, ValueError):
            return _error("Choose a valid appointment date and time.")
        if scheduled_date.tzinfo is not None:
            scheduled_date = scheduled_date.astimezone().replace(tzinfo=None)
        if scheduled_date <= datetime.now():
            return _error("Appointment time must be in the future.")
        booking_type = data.get("booking_type")
        if booking_type not in {"home", "salon"}:
            return _error("Choose a home visit or salon appointment.")
        if booking_type == "home" and not stylist.offers_home_visit:
            return _error("This stylist does not offer home visits.")
        if booking_type == "salon" and not stylist.offers_salon:
            return _error("This stylist does not offer salon appointments.")
        latitude, longitude, error_message = _coordinates(data)
        if error_message:
            return _error(error_message)
        if (latitude is None) != (longitude is None):
            return _error("Share both GPS coordinates for the appointment location.")
        location, error_message = _required_text(data, "location", "Appointment address", 200)
        if error_message and latitude is None:
            return _error(error_message)
        if error_message:
            location = "Customer-shared GPS location"
        notes = data.get("notes", "")
        if not isinstance(notes, str) or len(notes) > 1000:
            return _error("Notes must be 1000 characters or fewer.")
        payment_method = data.get("payment_method")
        if payment_method not in PAYMENT_METHODS:
            return _error("Choose M-Pesa or cash as your preferred payment method.")
        booking = Booking(
            customer_id=customer_id,
            stylist_id=stylist.id,
            service_id=service.id,
            scheduled_date=scheduled_date,
            booking_type=booking_type,
            location=location,
            latitude=latitude,
            longitude=longitude,
            notes=notes.strip(),
            service_price=service.base_price,
            payment_method=payment_method,
        )
        db.session.add(booking)
        db.session.commit()
        return jsonify(_booking_json(booking)), 201

    @app.get("/api/bookings")
    def list_bookings():
        role = session.get("role")
        if role == "customer":
            bookings = Booking.query.filter_by(customer_id=session.get("customer_id")).order_by(Booking.scheduled_date.desc()).all()
        elif role == "stylist":
            bookings = Booking.query.filter_by(stylist_id=session.get("stylist_id")).order_by(Booking.scheduled_date.desc()).all()
        elif role == "admin" and _current_role_id("admin"):
            bookings = Booking.query.order_by(Booking.scheduled_date.desc()).all()
        else:
            return _error("Please sign in to continue.", 401)
        return jsonify([_booking_json(booking) for booking in bookings])

    @app.patch("/api/bookings/<int:booking_id>/status")
    def update_booking_status(booking_id):
        data, error = _payload()
        if error:
            return error
        status = data.get("status")
        if status not in BOOKING_STATUSES:
            return _error("Choose a valid booking status.")
        role = session.get("role")
        if role not in {"customer", "stylist", "admin"} or _current_role_id(role) is None:
            return _error("Please sign in to continue.", 401)
        booking = db.session.get(Booking, booking_id)
        if booking is None:
            return _error("Booking not found.", 404)
        if role == "customer" and booking.customer_id == session.get("customer_id"):
            if status != "cancelled" or booking.status not in {"pending", "accepted"}:
                return _error("You can only cancel a pending or accepted booking.")
        elif role == "stylist" and booking.stylist_id == session.get("stylist_id"):
            if not booking.stylist.is_approved:
                return _error("Your stylist account is awaiting approval.", 403)
            transitions = {
                "pending": {"accepted", "cancelled"},
                "accepted": {"in_progress", "cancelled"},
                "in_progress": {"completed"},
            }
            if status not in transitions.get(booking.status, set()):
                return _error("That booking status change is not allowed.")
        elif role == "admin" and _current_role_id("admin"):
            pass
        else:
            return _error("You cannot update this booking.", 403)
        booking.status = status
        db.session.commit()
        return jsonify(_booking_json(booking))

    @app.post("/api/bookings/<int:booking_id>/demo-payment")
    @_login_required("customer")
    def demo_payment(customer_id, booking_id):
        booking = db.session.get(Booking, booking_id)
        if booking is None or booking.customer_id != customer_id:
            return _error("Booking not found.", 404)
        if booking.status == "cancelled":
            return _error("Cancelled bookings cannot be paid.")
        if booking.payment_status == "demo_paid":
            return _error("Demo payment was already recorded.")
        booking.payment_status = "demo_paid"
        db.session.commit()
        return jsonify({
            "booking": _booking_json(booking),
            "message": "Demo payment recorded. No money was charged.",
        })

    @app.post("/api/bookings/<int:booking_id>/reviews")
    @_login_required("customer")
    def create_review(customer_id, booking_id):
        data, error = _payload()
        if error:
            return error
        booking = db.session.get(Booking, booking_id)
        if booking is None or booking.customer_id != customer_id:
            return _error("Booking not found.", 404)
        if booking.status != "completed":
            return _error("You can review a booking after it is completed.")
        if Review.query.filter_by(booking_id=booking_id).first():
            return _error("This booking already has a review.", 409)
        try:
            rating = int(data.get("rating"))
        except (TypeError, ValueError):
            return _error("Choose a rating from 1 to 5.")
        if rating < 1 or rating > 5:
            return _error("Choose a rating from 1 to 5.")
        comment = data.get("comment", "")
        if not isinstance(comment, str) or len(comment) > 1000:
            return _error("Review must be 1000 characters or fewer.")
        review = Review(booking_id=booking_id, rating=rating, comment=comment.strip())
        db.session.add(review)
        stylist = booking.stylist
        new_count = stylist.total_reviews + 1
        stylist.rating = round(((stylist.rating * stylist.total_reviews) + rating) / new_count, 1)
        stylist.total_reviews = new_count
        db.session.commit()
        return jsonify(_review_json(review)), 201

    @app.get("/api/stylist/dashboard")
    @_login_required("stylist")
    def stylist_dashboard(stylist_id):
        stylist = db.session.get(Stylist, stylist_id)
        bookings = Booking.query.filter_by(stylist_id=stylist_id).order_by(Booking.scheduled_date.desc()).all()
        return jsonify({"stylist": _stylist_json(stylist), "is_approved": stylist.is_approved, "is_available": stylist.is_available, "bookings": [_booking_json(booking) for booking in bookings]})

    @app.patch("/api/stylist/availability")
    @_login_required("stylist")
    def stylist_availability(stylist_id):
        data, error = _payload()
        if error:
            return error
        if not isinstance(data.get("is_available"), bool):
            return _error("Availability must be true or false.")
        stylist = db.session.get(Stylist, stylist_id)
        if not stylist.is_approved:
            return _error("Your account is awaiting administrator approval.", 403)
        stylist.is_available = data["is_available"]
        db.session.commit()
        return jsonify({"is_available": stylist.is_available})

    @app.patch("/api/stylist/location")
    @_login_required("stylist")
    def update_stylist_location(stylist_id):
        data, error = _payload()
        if error:
            return error
        latitude, longitude, error_message = _coordinates(data)
        if error_message:
            return _error(error_message)
        if latitude is None or longitude is None:
            return _error("Share your GPS location to update your artist location.")
        stylist = db.session.get(Stylist, stylist_id)
        if not stylist.is_approved:
            return _error("Your account is awaiting administrator approval.", 403)
        stylist.latitude = latitude
        stylist.longitude = longitude
        db.session.commit()
        return jsonify({"has_gps_location": True, "location": stylist.location})

    @app.get("/api/admin/dashboard")
    @_admin_required
    def admin_dashboard(admin_id):
        pending_stylists = Stylist.query.filter_by(is_approved=False).order_by(Stylist.id.asc()).all()
        bookings = Booking.query.order_by(Booking.scheduled_date.desc()).all()
        return jsonify({
            "stats": {
                "customers": Customer.query.count(),
                "stylists": Stylist.query.filter_by(is_approved=True).count(),
                "pending_stylists": len(pending_stylists),
                "bookings": Booking.query.count(),
                "revenue": db.session.query(func.coalesce(func.sum(Booking.service_price), 0)).filter(Booking.payment_status == "demo_paid").scalar(),
            },
            "pending_stylists": [
                {**_stylist_json(stylist), "email": stylist.account.email, "phone": stylist.account.phone}
                for stylist in pending_stylists if stylist.account
            ],
            "bookings": [_booking_json(booking) for booking in bookings],
        })

    @app.patch("/api/admin/stylists/<int:stylist_id>")
    @_admin_required
    def admin_stylist_approval(admin_id, stylist_id):
        data, error = _payload()
        if error:
            return error
        approved = data.get("is_approved")
        if not isinstance(approved, bool):
            return _error("Approval must be true or false.")
        stylist = db.session.get(Stylist, stylist_id)
        if stylist is None:
            return _error("Stylist not found.", 404)
        stylist.is_approved = approved
        stylist.is_available = approved
        db.session.commit()
        return jsonify({**_stylist_json(stylist), "is_approved": stylist.is_approved})

    @app.cli.command("create-admin")
    def create_admin_command():
        """Create an administrator account interactively."""
        email = click.prompt("Administrator email").strip().lower()
        if not _valid_email(email):
            raise click.ClickException("Enter a valid email address.")
        if Customer.query.filter_by(email=email).first() or StylistAccount.query.filter_by(email=email).first() or Admin.query.filter_by(email=email).first():
            raise click.ClickException("An account with that email already exists.")
        name = click.prompt("Administrator name")
        password = click.prompt("Password (at least 8 characters)", hide_input=True, confirmation_prompt=True)
        if not 8 <= len(password) <= 128:
            raise click.ClickException("Password must be between 8 and 128 characters.")
        db.session.add(Admin(name=name.strip(), email=email, password_hash=generate_password_hash(password)))
        db.session.commit()
        click.echo("Administrator account created.")

    with app.app_context():
        db.create_all()
        upgrade_schema()
        seed_database()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
