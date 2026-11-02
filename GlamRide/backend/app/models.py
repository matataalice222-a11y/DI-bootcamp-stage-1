from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utc_now():
    return datetime.now(timezone.utc)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(16), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="customer")
    phone_verified = db.Column(db.Boolean, nullable=False, default=False)
    onboarding_status = db.Column(db.String(30), nullable=False, default="draft")
    onboarding_data = db.Column(db.JSON, nullable=False, default=dict)
    review_note = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    stylist_profile = db.relationship(
        "StylistProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class OTPCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    code_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    resends = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    user = db.relationship("User")


class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    category = db.Column(db.String(60), nullable=False)
    description = db.Column(db.String(240), nullable=False)
    starting_price_kes = db.Column(db.Integer, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String(500), nullable=False)


class StylistProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    display_name = db.Column(db.String(80), nullable=False)
    bio = db.Column(db.String(500), nullable=False, default="")
    gender = db.Column(db.String(20), nullable=True)
    years_experience = db.Column(db.Integer, nullable=False, default=0)
    languages = db.Column(db.JSON, nullable=False, default=list)
    work_type = db.Column(db.String(30), nullable=False, default="home")
    base_area = db.Column(db.String(120), nullable=False, default="Nairobi")
    base_lat = db.Column(db.Float, nullable=True)
    base_lng = db.Column(db.Float, nullable=True)
    service_radius_km = db.Column(db.Float, nullable=False, default=15)
    rating = db.Column(db.Float, nullable=False, default=5.0)
    review_count = db.Column(db.Integer, nullable=False, default=0)
    completed_jobs = db.Column(db.Integer, nullable=False, default=0)
    available = db.Column(db.Boolean, nullable=False, default=True)
    status = db.Column(db.String(30), nullable=False, default="draft")

    user = db.relationship("User", back_populates="stylist_profile")
    services = db.relationship(
        "StylistService", back_populates="stylist", cascade="all, delete-orphan"
    )


class StylistService(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stylist_id = db.Column(db.Integer, db.ForeignKey("stylist_profile.id"), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=False)
    price_kes = db.Column(db.Integer, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    specialties = db.Column(db.JSON, nullable=False, default=list)

    stylist = db.relationship("StylistProfile", back_populates="services")
    service = db.relationship("Service")
    __table_args__ = (
        db.UniqueConstraint("stylist_id", "service_id", name="uq_stylist_service"),
    )


class Upload(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(80), unique=True, nullable=False)
    mime_type = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    user = db.relationship("User")


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    stylist_id = db.Column(db.Integer, db.ForeignKey("stylist_profile.id"), nullable=False, index=True)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=False)
    scheduled_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    duration_minutes = db.Column(db.Integer, nullable=False)
    service_price_kes = db.Column(db.Integer, nullable=False)
    travel_fee_kes = db.Column(db.Integer, nullable=False, default=0)
    service_location = db.Column(db.String(20), nullable=False, default="home")
    address = db.Column(db.String(180), nullable=False)
    landmark = db.Column(db.String(180), nullable=False, default="")
    directions_note = db.Column(db.String(300), nullable=False, default="")
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="requested", index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    customer = db.relationship("User", foreign_keys=[customer_id])
    stylist = db.relationship("StylistProfile")
    service = db.relationship("Service")
    review = db.relationship("Review", back_populates="booking", uselist=False)


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("booking.id"), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    stylist_id = db.Column(db.Integer, db.ForeignKey("stylist_profile.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.String(500), nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    booking = db.relationship("Booking", back_populates="review")
    customer = db.relationship("User")
    stylist = db.relationship("StylistProfile")


class AdminReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    stylist_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    decision = db.Column(db.String(30), nullable=False)
    note = db.Column(db.String(500), nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    admin = db.relationship("User", foreign_keys=[admin_id])
    stylist_user = db.relationship("User", foreign_keys=[stylist_user_id])
