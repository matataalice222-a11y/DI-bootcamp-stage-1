import math
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Blueprint, current_app, g, jsonify, request, send_file
from sqlalchemy import or_
from werkzeug.security import check_password_hash, generate_password_hash

from .models import (
    Booking,
    AdminReview,
    OTPCode,
    Review,
    Service,
    StylistProfile,
    StylistService,
    Upload,
    User,
    db,
    utc_now,
)
from .security import authenticate, issue_token

api = Blueprint("api", __name__)

CUSTOMER_FIELDS = {
    3: {"address_label", "address", "landmark", "address_note", "latitude", "longitude"},
    4: {"favorite_services", "hair_type", "stylist_gender_preference", "allergies", "service_location"},
    5: {"emergency_contact_name", "emergency_contact_phone", "emergency_contact_relationship", "share_location_consent"},
    6: {"policy_accepted"},
}
STYLIST_FIELDS = {
    3: {"display_name", "bio", "years_experience", "languages", "gender"},
    4: {"services"},
    5: {"portfolio_upload_ids"},
    6: {"work_type", "base_area", "base_latitude", "base_longitude", "service_radius_km", "working_days", "work_start", "work_end", "travel_buffer_minutes"},
}
ACTIVE_BOOKING_STATUSES = {"requested", "confirmed", "on_the_way", "arrived", "in_progress"}
BOOKING_TRANSITIONS = {
    "requested": {"confirmed", "cancelled"},
    "confirmed": {"on_the_way", "cancelled"},
    "on_the_way": {"arrived", "cancelled"},
    "arrived": {"in_progress", "cancelled"},
    "in_progress": {"completed"},
}
KENYAN_PHONE = re.compile(r"^(?:\+?254|0)(?:7|1)\d{8}$")
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify(error="Send a valid JSON object."), 400)
    return data, None


def _phone(value):
    normalized = re.sub(r"[\s()-]", "", str(value or ""))
    if normalized.startswith("0"):
        normalized = "+254" + normalized[1:]
    elif normalized.startswith("254"):
        normalized = "+" + normalized
    return normalized if KENYAN_PHONE.fullmatch(normalized) else None


def _safe_user(user):
    data = {
        "id": user.id,
        "full_name": user.full_name,
        "role": user.role,
        "email": user.email,
        "phone_verified": user.phone_verified,
        "onboarding_status": user.onboarding_status,
    }
    if user.role == "stylist" and user.stylist_profile:
        data["stylist_status"] = user.stylist_profile.status
        data["stylist_available"] = user.stylist_profile.available
    return data


def _progress(user):
    flow_steps = 6 if user.role in {"customer", "stylist"} else 0
    onboarding = user.onboarding_data or {}
    return {
        "role": user.role,
        "status": user.onboarding_status,
        "current_step": onboarding.get("current_step", 1),
        "total_steps": flow_steps,
        "completed_steps": onboarding.get("completed_steps", []),
        "data": {key: value for key, value in onboarding.items() if key not in {"current_step", "completed_steps"}},
        "review_note": user.review_note,
    }


def _otp_for(user, resend=False):
    if not current_app.config["DEMO_OTP_ENABLED"]:
        return None, (jsonify(error="SMS verification is not configured for this deployment."), 503)
    existing = OTPCode.query.filter_by(user_id=user.id).first()
    resends = 0
    if resend:
        if not existing:
            return None, (jsonify(error="Request a verification code by registering again."), 404)
        if utc_now() < _aware(existing.created_at) + timedelta(seconds=30):
            return None, (jsonify(error="Wait 30 seconds before requesting another code."), 429)
        if existing.resends >= 3:
            return None, (jsonify(error="You’ve requested the maximum number of codes. Try again later."), 429)
        resends = existing.resends + 1
        db.session.delete(existing)
        db.session.flush()
    code = f"{secrets.randbelow(900000) + 100000:06d}"
    db.session.add(
        OTPCode(
            user_id=user.id,
            code_hash=generate_password_hash(code),
            expires_at=utc_now() + timedelta(seconds=current_app.config["OTP_TTL_SECONDS"]),
            resends=resends,
        )
    )
    db.session.commit()
    return code, None


def _datetime(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("Africa/Nairobi"))
    return parsed.astimezone(timezone.utc)


def _aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _km_between(lat1, lng1, lat2, lng2):
    radius = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    haversine = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lng / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))


def _service_card(service):
    return {
        "id": service.id,
        "name": service.name,
        "category": service.category,
        "description": service.description,
        "starting_price_kes": service.starting_price_kes,
        "duration_minutes": service.duration_minutes,
        "image_url": service.image_url,
    }


def _stylist_card(profile, customer_lat=None, customer_lng=None):
    service_rows = []
    for offered in profile.services:
        if offered.service:
            service_rows.append(
                {
                    "id": offered.service_id,
                    "name": offered.service.name,
                    "price_kes": offered.price_kes,
                    "duration_minutes": offered.duration_minutes,
                    "specialties": offered.specialties or [],
                }
            )
    distance = None
    travel_fee = 250
    if (
        customer_lat is not None
        and customer_lng is not None
        and profile.base_lat is not None
        and profile.base_lng is not None
    ):
        distance = round(_km_between(customer_lat, customer_lng, profile.base_lat, profile.base_lng), 1)
        travel_fee = min(1500, 100 + int(distance * 20))
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "display_name": profile.display_name,
        "bio": profile.bio,
        "years_experience": profile.years_experience,
        "languages": profile.languages or [],
        "work_type": profile.work_type,
        "base_area": profile.base_area,
        "rating": profile.rating,
        "review_count": profile.review_count,
        "completed_jobs": profile.completed_jobs,
        "distance_km": distance,
        "estimated_travel_fee_kes": travel_fee,
        "services": service_rows,
        "available": profile.available,
    }


def _booking_card(booking):
    return {
        "id": booking.id,
        "status": booking.status,
        "scheduled_at": _aware(booking.scheduled_at).isoformat(),
        "duration_minutes": booking.duration_minutes,
        "service_price_kes": booking.service_price_kes,
        "travel_fee_kes": booking.travel_fee_kes,
        "total_kes": booking.service_price_kes + booking.travel_fee_kes,
        "service_location": booking.service_location,
        "address": booking.address,
        "landmark": booking.landmark,
        "directions_note": booking.directions_note,
        "latitude": booking.latitude,
        "longitude": booking.longitude,
        "service": _service_card(booking.service),
        "customer": {"id": booking.customer.id, "full_name": booking.customer.full_name},
        "stylist": {
            "id": booking.stylist.id,
            "display_name": booking.stylist.display_name,
            "base_area": booking.stylist.base_area,
        },
        "has_review": booking.review is not None,
    }


@api.get("/health")
def health():
    return jsonify(status="ok", service="GlamRide API")


@api.get("/services")
def list_services():
    services = Service.query.order_by(Service.category, Service.name).all()
    return jsonify(services=[_service_card(service) for service in services])


@api.post("/auth/register")
def register():
    data, error = _body()
    if error:
        return error
    if not current_app.config["DEMO_OTP_ENABLED"]:
        return jsonify(error="SMS verification is not configured for this deployment. Registration is currently unavailable."), 503

    full_name = str(data.get("full_name", "")).strip()
    phone = _phone(data.get("phone"))
    email = str(data.get("email", "")).strip().lower() or None
    password = str(data.get("password", ""))
    role = data.get("role", "customer")
    if len(full_name) < 2:
        return jsonify(error="Enter your full name."), 400
    if not phone:
        return jsonify(error="Enter a valid Kenyan mobile number, such as 0712 345 678."), 400
    if role not in {"customer", "stylist"}:
        return jsonify(error="Choose customer or stylist registration."), 400
    if len(password) < 8:
        return jsonify(error="Use a password with at least 8 characters."), 400
    if email and (len(email) > 255 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)):
        return jsonify(error="Enter a valid email address."), 400
    if User.query.filter(or_(User.phone == phone, User.email == email) if email else User.phone == phone).first():
        return jsonify(error="An account already uses that phone number or email."), 409

    user = User(
        full_name=full_name,
        phone=phone,
        email=email,
        password_hash=generate_password_hash(password),
        role=role,
        onboarding_status="draft",
        onboarding_data={"current_step": 2, "completed_steps": [1]},
    )
    db.session.add(user)
    db.session.flush()
    if role == "stylist":
        db.session.add(
            StylistProfile(
                user_id=user.id,
                display_name=full_name,
                status="draft",
            )
        )
    db.session.commit()

    code, error = _otp_for(user)
    if error:
        return error
    response = {"message": "We sent a verification code to your phone.", "user": _safe_user(user)}
    if current_app.config["DEMO_OTP_ENABLED"]:
        response["demo_otp"] = code
    return jsonify(response), 201


@api.post("/auth/verify-otp")
def verify_otp():
    data, error = _body()
    if error:
        return error
    phone = _phone(data.get("phone"))
    code = str(data.get("code", "")).strip()
    if not phone or not re.fullmatch(r"\d{6}", code):
        return jsonify(error="Enter your phone number and the 6-digit code."), 400
    user = User.query.filter_by(phone=phone).first()
    otp = OTPCode.query.filter_by(user_id=user.id).first() if user else None
    if not user or not otp:
        return jsonify(error="That verification code is no longer available. Request a new one."), 400
    if otp.attempts >= current_app.config["OTP_MAX_ATTEMPTS"]:
        return jsonify(error="Too many incorrect attempts. Please request a new code."), 429
    otp.attempts += 1
    expires_at = _aware(otp.expires_at)
    if expires_at <= utc_now():
        db.session.commit()
        return jsonify(error="That code expired. Request a new one."), 400
    if not check_password_hash(otp.code_hash, code):
        db.session.commit()
        return jsonify(error="That code does not match. Check it and try again."), 400

    user.phone_verified = True
    user.onboarding_data = {
        **(user.onboarding_data or {}),
        "current_step": 3,
        "completed_steps": sorted(set((user.onboarding_data or {}).get("completed_steps", []) + [2])),
    }
    if user.role == "customer":
        user.onboarding_status = "phone_verified"
    db.session.delete(otp)
    db.session.commit()
    return jsonify(token=issue_token(user), user=_safe_user(user), onboarding=_progress(user))


@api.post("/auth/resend-otp")
def resend_otp():
    data, error = _body()
    if error:
        return error
    phone = _phone(data.get("phone"))
    user = User.query.filter_by(phone=phone).first() if phone else None
    if not user or user.phone_verified:
        return jsonify(error="No account needs phone verification for that number."), 404
    code, error = _otp_for(user, resend=True)
    if error:
        return error
    response = {"message": "A new verification code is ready."}
    if current_app.config["DEMO_OTP_ENABLED"]:
        response["demo_otp"] = code
    return jsonify(response)


@api.post("/auth/login")
def login():
    data, error = _body()
    if error:
        return error
    phone = _phone(data.get("phone"))
    password = str(data.get("password", ""))
    user = User.query.filter_by(phone=phone).first() if phone else None
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify(error="The phone number or password is incorrect."), 401
    if not user.phone_verified:
        return jsonify(error="Verify your phone number before signing in."), 403
    return jsonify(token=issue_token(user), user=_safe_user(user), onboarding=_progress(user))


@api.get("/onboarding/progress")
@authenticate(roles={"customer", "stylist"})
def onboarding_progress():
    return jsonify(progress=_progress(g.current_user), user=_safe_user(g.current_user))


def _validate_step(role, step, data, user):
    fields = CUSTOMER_FIELDS if role == "customer" else STYLIST_FIELDS
    if step not in fields:
        return "That onboarding step does not exist."
    supplied = set(data)
    if not supplied.issubset(fields[step]):
        return "That step contains fields that cannot be changed here."

    if role == "customer":
        if step == 3:
            if len(str(data.get("address", "")).strip()) < 4:
                return "Enter your service address, estate, or neighbourhood."
            for key in ("latitude", "longitude"):
                if key in data and data[key] is not None:
                    try:
                        number = float(data[key])
                    except (TypeError, ValueError):
                        return "Map coordinates must be numbers."
                    limit = 90 if key == "latitude" else 180
                    if not -limit <= number <= limit:
                        return "Enter valid map coordinates."
        elif step == 4:
            if data.get("service_location") and data["service_location"] not in {"home", "salon", "either"}:
                return "Choose home, salon, or either."
            if data.get("stylist_gender_preference") and data["stylist_gender_preference"] not in {"any", "female", "male"}:
                return "Choose a valid stylist preference."
        elif step == 5:
            name = str(data.get("emergency_contact_name", "")).strip()
            contact_phone = _phone(data.get("emergency_contact_phone"))
            if name and not contact_phone:
                return "Enter a valid Kenyan number for your emergency contact."
            if "share_location_consent" in data and not isinstance(data["share_location_consent"], bool):
                return "Choose whether to share your location during active bookings."
        elif step == 6:
            if data.get("policy_accepted") is not True:
                return "Accept the booking and cancellation policy to continue."
    else:
        if step == 3:
            if len(str(data.get("display_name", "")).strip()) < 2:
                return "Add the name customers will see on your profile."
            if len(str(data.get("bio", "")).strip()) < 20:
                return "Tell customers a little about your work (at least 20 characters)."
            try:
                years = int(data.get("years_experience", -1))
            except (TypeError, ValueError):
                years = -1
            if not 0 <= years <= 60:
                return "Enter years of experience from 0 to 60."
            if data.get("gender") not in {None, "", "female", "male", "nonbinary", "prefer_not_say"}:
                return "Choose a valid profile preference."
        elif step == 4:
            services = data.get("services")
            if not isinstance(services, list) or not services:
                return "Choose at least one service you offer."
            valid_ids = {service.id for service in Service.query.all()}
            for item in services:
                if not isinstance(item, dict):
                    return "Each service needs a price and duration."
                try:
                    service_id = int(item.get("service_id"))
                    price = int(item.get("price_kes"))
                    duration = int(item.get("duration_minutes"))
                except (TypeError, ValueError):
                    return "Enter a valid service, price, and duration."
                if service_id not in valid_ids or not 300 <= price <= 100000:
                    return "Choose a listed service and enter a price from KES 300 to 100,000."
                if not 15 <= duration <= 600:
                    return "Service durations should be between 15 minutes and 10 hours."
        elif step == 5:
            uploads = data.get("portfolio_upload_ids")
            if not isinstance(uploads, list) or len(uploads) < 5:
                return "Upload at least five photos of your work."
            owned = {
                item.id
                for item in Upload.query.filter(
                    Upload.user_id == user.id, Upload.id.in_(uploads)
                ).all()
            }
            if len(owned) != len(set(uploads)):
                return "Portfolio photos must be uploaded to this account."
        elif step == 6:
            if data.get("work_type") not in {"home", "salon", "both"}:
                return "Choose where you offer your services."
            if len(str(data.get("base_area", "")).strip()) < 2:
                return "Enter your base neighbourhood or service area."
            try:
                radius = float(data.get("service_radius_km"))
                buffer_minutes = int(data.get("travel_buffer_minutes", 0))
            except (TypeError, ValueError):
                return "Enter a valid service radius and travel buffer."
            if not 1 <= radius <= 100 or not 0 <= buffer_minutes <= 180:
                return "Radius must be 1–100 km and travel buffer 0–180 minutes."
            days = data.get("working_days")
            if not isinstance(days, list) or not days:
                return "Select at least one working day."
            if not re.fullmatch(r"\d{2}:\d{2}", str(data.get("work_start", ""))) or not re.fullmatch(r"\d{2}:\d{2}", str(data.get("work_end", ""))):
                return "Choose your working hours."
            if data["work_start"] >= data["work_end"]:
                return "Your end time must be later than your start time."
    return None


@api.put("/onboarding/step/<int:step>")
@authenticate(roles={"customer", "stylist"})
def save_onboarding_step(step):
    data, error = _body()
    if error:
        return error
    user = g.current_user
    validation_error = _validate_step(user.role, step, data, user)
    if validation_error:
        return jsonify(error=validation_error), 400

    onboarding = dict(user.onboarding_data or {})
    completed = set(onboarding.get("completed_steps", []))
    completed.add(step)
    onboarding.update(data)
    onboarding["completed_steps"] = sorted(completed)
    onboarding["current_step"] = min(6, step + 1)
    user.onboarding_data = onboarding
    if user.role == "customer" and step in {3, 6}:
        user.onboarding_status = "active"

    if user.role == "stylist":
        profile = user.stylist_profile
        if step == 3:
            profile.display_name = data["display_name"].strip()
            profile.bio = data["bio"].strip()
            profile.years_experience = int(data["years_experience"])
            profile.languages = data.get("languages", [])
            profile.gender = data.get("gender")
        elif step == 4:
            profile.services.clear()
            for item in data["services"]:
                profile.services.append(
                    StylistService(
                        service_id=int(item["service_id"]),
                        price_kes=int(item["price_kes"]),
                        duration_minutes=int(item["duration_minutes"]),
                        specialties=item.get("specialties", []),
                    )
                )
        elif step == 6:
            profile.work_type = data["work_type"]
            profile.base_area = data["base_area"].strip()
            profile.base_lat = data.get("base_latitude")
            profile.base_lng = data.get("base_longitude")
            profile.service_radius_km = float(data["service_radius_km"])
    db.session.commit()
    return jsonify(progress=_progress(user))


@api.post("/uploads")
@authenticate(roles={"stylist"})
def upload_portfolio_image():
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify(error="Choose an image to upload."), 400
    extension = Path(uploaded.filename).suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify(error="Use a JPG, PNG, or WebP image."), 400
    image = uploaded.read()
    if not image or len(image) > current_app.config["MAX_CONTENT_LENGTH"]:
        return jsonify(error="Each image must be smaller than 8 MB."), 400
    is_jpeg = extension in {".jpg", ".jpeg"} and image.startswith(b"\xff\xd8\xff")
    is_png = extension == ".png" and image.startswith(b"\x89PNG\r\n\x1a\n")
    is_webp = extension == ".webp" and len(image) >= 12 and image[:4] == b"RIFF" and image[8:12] == b"WEBP"
    if not (is_jpeg or is_png or is_webp):
        return jsonify(error="The file content does not match a supported image format."), 400

    upload_id = str(uuid.uuid4())
    stored_name = f"{upload_id}{extension}"
    folder = Path(current_app.config["UPLOAD_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / stored_name
    destination.write_bytes(image)
    record = Upload(
        id=upload_id,
        user_id=g.current_user.id,
        original_name=Path(uploaded.filename).name[:255],
        stored_name=stored_name,
        mime_type={"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}[extension.lstrip(".")],
    )
    db.session.add(record)
    db.session.commit()
    return jsonify(upload={"id": record.id, "name": record.original_name}), 201


@api.get("/uploads/<upload_id>")
@authenticate(roles={"admin", "stylist"})
def read_private_upload(upload_id):
    upload = db.get_or_404(Upload, upload_id)
    if g.current_user.role != "admin" and upload.user_id != g.current_user.id:
        return jsonify(error="You cannot access this private file."), 403
    path = Path(current_app.config["UPLOAD_FOLDER"], upload.stored_name)
    if not path.is_file():
        current_app.logger.error("Private upload record has no corresponding file: %s", upload.id)
        return jsonify(error="This file is unavailable."), 404
    return send_file(path, mimetype=upload.mime_type, as_attachment=True, download_name=upload.original_name)


@api.get("/stylists")
def list_stylists():
    preference = request.args.get("gender_preference", "any")
    if preference not in {"any", "female", "male"}:
        return jsonify(error="Choose a valid stylist preference."), 400
    try:
        service_id = int(request.args["service_id"]) if request.args.get("service_id") else None
        customer_lat = float(request.args["lat"]) if request.args.get("lat") else None
        customer_lng = float(request.args["lng"]) if request.args.get("lng") else None
    except ValueError:
        return jsonify(error="Service and location filters must be valid numbers."), 400
    if (customer_lat is None) != (customer_lng is None):
        return jsonify(error="Provide both latitude and longitude for location matching."), 400
    if customer_lat is not None and not (-90 <= customer_lat <= 90 and -180 <= customer_lng <= 180):
        return jsonify(error="Enter valid map coordinates."), 400

    query = StylistProfile.query.join(User).filter(
        User.phone_verified.is_(True),
        User.onboarding_status == "verified",
        StylistProfile.status == "verified",
        StylistProfile.available.is_(True),
    )
    if service_id:
        query = query.join(StylistService).filter(StylistService.service_id == service_id)
    if preference in {"female", "male"}:
        query = query.filter(StylistProfile.gender == preference)
    area = request.args.get("area", "").strip()
    if area:
        query = query.filter(StylistProfile.base_area.ilike(f"%{area[:80]}%"))

    profiles = query.distinct().all()
    cards = []
    for profile in profiles:
        card = _stylist_card(profile, customer_lat, customer_lng)
        if card["distance_km"] is not None and card["distance_km"] > profile.service_radius_km:
            continue
        cards.append(card)
    cards.sort(
        key=lambda item: (
            item["distance_km"] is None,
            item["distance_km"] if item["distance_km"] is not None else 0,
            -item["rating"],
            -item["completed_jobs"],
        )
    )
    return jsonify(stylists=cards)


@api.patch("/stylist/availability")
@authenticate(roles={"stylist"})
def update_availability():
    data, error = _body()
    if error:
        return error
    if not isinstance(data.get("available"), bool):
        return jsonify(error="Availability must be on or off."), 400
    if g.current_user.stylist_profile.status != "verified":
        return jsonify(error="Availability is available after your profile is approved."), 409
    g.current_user.stylist_profile.available = data["available"]
    db.session.commit()
    return jsonify(available=data["available"])


@api.post("/stylists/submit")
@authenticate(roles={"stylist"})
def submit_stylist_application():
    user = g.current_user
    completed = set((user.onboarding_data or {}).get("completed_steps", []))
    if not {1, 2, 3, 4, 5, 6}.issubset(completed):
        return jsonify(error="Finish all six onboarding steps before submitting."), 400
    profile = user.stylist_profile
    if profile is None or profile.status == "verified":
        return jsonify(error="There is no draft stylist application to submit."), 409
    user.onboarding_status = "in_review"
    user.review_note = None
    profile.status = "in_review"
    db.session.commit()
    return jsonify(message="Your profile has been submitted for review.", user=_safe_user(user), progress=_progress(user))


@api.get("/bookings")
@authenticate(roles={"customer", "stylist", "admin"})
def list_bookings():
    user = g.current_user
    query = Booking.query
    if user.role == "customer":
        query = query.filter_by(customer_id=user.id)
    elif user.role == "stylist":
        query = query.filter_by(stylist_id=user.stylist_profile.id)
    bookings = query.order_by(Booking.scheduled_at.desc()).limit(100).all()
    return jsonify(bookings=[_booking_card(item) for item in bookings])


@api.post("/bookings")
@authenticate(roles={"customer"})
def create_booking():
    data, error = _body()
    if error:
        return error
    try:
        stylist_id = int(data.get("stylist_id"))
        service_id = int(data.get("service_id"))
    except (TypeError, ValueError):
        return jsonify(error="Choose a stylist and a service."), 400
    scheduled_at = _datetime(data.get("scheduled_at"))
    address = str(data.get("address", "")).strip()
    landmark = str(data.get("landmark", "")).strip()
    directions_note = str(data.get("directions_note", "")).strip()
    service_location = data.get("service_location", "home")
    if scheduled_at is None or scheduled_at < utc_now() + timedelta(minutes=15):
        return jsonify(error="Choose a time at least 15 minutes from now."), 400
    if len(address) < 4:
        return jsonify(error="Enter the service address, estate, or salon."), 400
    onboarding = g.current_user.onboarding_data or {}
    if onboarding.get("policy_accepted") is not True and data.get("policy_accepted") is not True:
        return jsonify(error="Accept the booking policy before requesting your first appointment."), 400
    if len(directions_note) > 300:
        return jsonify(error="Directions must be 300 characters or fewer."), 400
    if service_location not in {"home", "salon"}:
        return jsonify(error="Choose a home or salon appointment."), 400

    profile = StylistProfile.query.filter_by(
        id=stylist_id, status="verified", available=True
    ).first()
    if not profile:
        return jsonify(error="That stylist is not currently taking bookings."), 404
    if not profile.user.phone_verified or profile.user.onboarding_status != "verified":
        return jsonify(error="That stylist has not completed verification."), 409
    if service_location == "home" and profile.work_type not in {"home", "both"}:
        return jsonify(error="This stylist is currently taking salon appointments only."), 409
    if service_location == "salon" and profile.work_type not in {"salon", "both"}:
        return jsonify(error="This stylist is currently taking home appointments only."), 409
    offered = StylistService.query.filter_by(stylist_id=profile.id, service_id=service_id).first()
    if not offered:
        return jsonify(error="That stylist does not offer this service."), 400
    try:
        latitude = float(data["latitude"]) if data.get("latitude") not in (None, "") else None
        longitude = float(data["longitude"]) if data.get("longitude") not in (None, "") else None
    except (TypeError, ValueError):
        return jsonify(error="Map coordinates must be numbers."), 400
    if (latitude is None) != (longitude is None):
        return jsonify(error="Provide both map coordinates, or neither."), 400
    if latitude is not None and not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return jsonify(error="Enter valid map coordinates."), 400

    appointment_end = scheduled_at + timedelta(minutes=offered.duration_minutes)
    local_appointment = scheduled_at.astimezone(ZoneInfo("Africa/Nairobi"))
    setup = profile.user.onboarding_data or {}
    working_days = setup.get("working_days", [])
    if working_days and local_appointment.strftime("%A") not in working_days:
        return jsonify(error="That stylist is not working on the selected day."), 409
    work_start = setup.get("work_start")
    work_end = setup.get("work_end")
    if work_start and work_end and (
        local_appointment.strftime("%H:%M") < work_start
        or (local_appointment + timedelta(minutes=offered.duration_minutes)).strftime("%H:%M") > work_end
    ):
        return jsonify(error="That appointment falls outside the stylist’s working hours."), 409
    try:
        travel_buffer = int(setup.get("travel_buffer_minutes", 0))
    except (TypeError, ValueError):
        travel_buffer = 0
    nearby = Booking.query.filter(
        Booking.stylist_id == profile.id,
        Booking.status.in_(ACTIVE_BOOKING_STATUSES),
        Booking.scheduled_at < appointment_end + timedelta(minutes=travel_buffer),
        Booking.scheduled_at >= scheduled_at - timedelta(hours=10, minutes=travel_buffer),
    ).all()
    for existing in nearby:
        existing_start = _aware(existing.scheduled_at)
        existing_end = existing_start + timedelta(minutes=existing.duration_minutes)
        if (
            scheduled_at - timedelta(minutes=travel_buffer) < existing_end
            and existing_start < appointment_end + timedelta(minutes=travel_buffer)
        ):
            return jsonify(error="That stylist already has a booking during this time. Try another slot."), 409

    distance = None
    if latitude is not None and profile.base_lat is not None and profile.base_lng is not None:
        distance = _km_between(latitude, longitude, profile.base_lat, profile.base_lng)
        if distance > profile.service_radius_km:
            return jsonify(error="This address is outside the stylist’s service area."), 400
    travel_fee = min(1500, 100 + int(distance * 20)) if distance is not None else 250
    if service_location == "salon":
        travel_fee = 0
    booking = Booking(
        customer_id=g.current_user.id,
        stylist_id=profile.id,
        service_id=service_id,
        scheduled_at=scheduled_at,
        duration_minutes=offered.duration_minutes,
        service_price_kes=offered.price_kes,
        travel_fee_kes=travel_fee,
        service_location=service_location,
        address=address,
        landmark=landmark,
        directions_note=directions_note,
        latitude=latitude,
        longitude=longitude,
    )
    if data.get("policy_accepted") is True and onboarding.get("policy_accepted") is not True:
        g.current_user.onboarding_data = {**onboarding, "policy_accepted": True}
    db.session.add(booking)
    db.session.commit()
    return jsonify(booking=_booking_card(booking)), 201


@api.patch("/bookings/<int:booking_id>/status")
@authenticate(roles={"customer", "stylist"})
def update_booking_status(booking_id):
    data, error = _body()
    if error:
        return error
    new_status = data.get("status")
    booking = db.get_or_404(Booking, booking_id)
    user = g.current_user
    is_customer = user.role == "customer" and booking.customer_id == user.id
    is_stylist = user.role == "stylist" and booking.stylist_id == user.stylist_profile.id
    if not (is_customer or is_stylist):
        return jsonify(error="This booking does not belong to your account."), 403
    if new_status not in BOOKING_TRANSITIONS.get(booking.status, set()):
        return jsonify(error="That booking status change is not allowed."), 409
    if new_status == "confirmed" and not is_stylist:
        return jsonify(error="Only the stylist can accept a booking."), 403
    if new_status in {"on_the_way", "arrived", "in_progress", "completed"} and not is_stylist:
        return jsonify(error="Only the stylist can update this service status."), 403
    if new_status == "cancelled" and user.role == "stylist":
        booking.stylist.available = True
    booking.status = new_status
    if new_status == "completed":
        booking.stylist.completed_jobs += 1
    db.session.commit()
    return jsonify(booking=_booking_card(booking))


@api.post("/bookings/<int:booking_id>/reviews")
@authenticate(roles={"customer"})
def review_booking(booking_id):
    data, error = _body()
    if error:
        return error
    booking = db.get_or_404(Booking, booking_id)
    if booking.customer_id != g.current_user.id:
        return jsonify(error="This booking does not belong to your account."), 403
    if booking.status != "completed":
        return jsonify(error="You can review a booking after it is complete."), 409
    if booking.review:
        return jsonify(error="You have already reviewed this booking."), 409
    try:
        rating = int(data.get("rating"))
    except (TypeError, ValueError):
        rating = 0
    if not 1 <= rating <= 5:
        return jsonify(error="Choose a rating from 1 to 5 stars."), 400
    comment = str(data.get("comment", "")).strip()[:500]
    review = Review(
        booking_id=booking.id,
        customer_id=g.current_user.id,
        stylist_id=booking.stylist_id,
        rating=rating,
        comment=comment,
    )
    db.session.add(review)
    profile = booking.stylist
    profile.rating = round((profile.rating * profile.review_count + rating) / (profile.review_count + 1), 2)
    profile.review_count += 1
    db.session.commit()
    return jsonify(message="Thank you for sharing your experience.", rating=rating), 201


@api.get("/admin/stylists")
@authenticate(roles={"admin"})
def admin_stylist_queue():
    users = User.query.filter(
        User.role == "stylist",
        User.onboarding_status.in_(["in_review", "needs_info"]),
    ).order_by(User.created_at).all()
    applications = []
    for user in users:
        progress = _progress(user)
        profile = user.stylist_profile
        services = []
        portfolio = []
        if profile:
            services = [
                {
                    "name": item.service.name,
                    "price_kes": item.price_kes,
                    "duration_minutes": item.duration_minutes,
                }
                for item in profile.services
                if item.service
            ]
            upload_ids = progress["data"].get("portfolio_upload_ids", [])
            portfolio = [
                {"id": upload.id, "name": upload.original_name}
                for upload in Upload.query.filter(Upload.id.in_(upload_ids)).all()
            ] if upload_ids else []
        applications.append(
            {
                "user": _safe_user(user),
                "progress": progress,
                "profile": _stylist_card(profile) if profile else None,
                "services": services,
                "portfolio": portfolio,
            }
        )
    return jsonify(applications=applications)


@api.post("/admin/stylists/<int:user_id>/review")
@authenticate(roles={"admin"})
def review_stylist_application(user_id):
    data, error = _body()
    if error:
        return error
    user = User.query.filter_by(id=user_id, role="stylist").first_or_404()
    decision = data.get("decision")
    note = str(data.get("note", "")).strip()[:500]
    if decision not in {"verified", "needs_info", "rejected", "suspended"}:
        return jsonify(error="Choose approve, request information, reject, or suspend."), 400
    if decision in {"needs_info", "rejected", "suspended"} and len(note) < 5:
        return jsonify(error="Add a short reason for this decision."), 400
    if decision == "verified":
        completed = set((user.onboarding_data or {}).get("completed_steps", []))
        if not {1, 2, 3, 4, 5, 6}.issubset(completed):
            return jsonify(error="This application is missing required onboarding steps."), 409
        if not user.phone_verified or not user.stylist_profile:
            return jsonify(error="Verify the stylist’s phone and profile before approval."), 409
        profile = user.stylist_profile
        if not profile.services or len((user.onboarding_data or {}).get("portfolio_upload_ids", [])) < 5:
            return jsonify(error="The application needs services and five portfolio images."), 409
        profile.status = "verified"
        profile.available = True
        user.onboarding_status = "verified"
        user.review_note = None
    else:
        user.onboarding_status = decision
        user.stylist_profile.status = decision
        user.review_note = note
    db.session.add(
        AdminReview(
            admin_id=g.current_user.id,
            stylist_user_id=user.id,
            decision=decision,
            note=note,
        )
    )
    db.session.commit()
    return jsonify(user=_safe_user(user), message="Application review saved.")


@api.get("/admin/reviews")
@authenticate(roles={"admin"})
def admin_review_history():
    rows = AdminReview.query.order_by(AdminReview.created_at.desc()).limit(100).all()
    return jsonify(
        reviews=[
            {
                "id": item.id,
                "stylist_name": item.stylist_user.full_name,
                "admin_name": item.admin.full_name,
                "decision": item.decision,
                "note": item.note,
                "created_at": _aware(item.created_at).isoformat(),
            }
            for item in rows
        ]
    )


@api.get("/admin/summary")
@authenticate(roles={"admin"})
def admin_summary():
    return jsonify(
        customers=User.query.filter_by(role="customer").count(),
        stylists=User.query.filter_by(role="stylist", onboarding_status="verified").count(),
        applications=User.query.filter(User.role == "stylist", User.onboarding_status.in_(["in_review", "needs_info"])).count(),
        bookings=Booking.query.count(),
        completed_bookings=Booking.query.filter_by(status="completed").count(),
        gross_bookings_kes=db.session.query(db.func.coalesce(db.func.sum(Booking.service_price_kes + Booking.travel_fee_kes), 0)).scalar(),
    )


@api.get("/bookings/<int:booking_id>")
@authenticate(roles={"customer", "stylist", "admin"})
def get_booking(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    user = g.current_user
    if user.role != "admin" and not (
        user.role == "customer" and booking.customer_id == user.id
    ) and not (
        user.role == "stylist" and booking.stylist_id == user.stylist_profile.id
    ):
        return jsonify(error="This booking does not belong to your account."), 403
    return jsonify(booking=_booking_card(booking))


@api.get("/admin/uploads/<upload_id>")
@authenticate(roles={"admin"})
def admin_read_upload(upload_id):
    upload = db.get_or_404(Upload, upload_id)
    path = Path(current_app.config["UPLOAD_FOLDER"], upload.stored_name)
    if not path.is_file():
        current_app.logger.error("Private upload record has no corresponding file: %s", upload.id)
        return jsonify(error="This file is unavailable."), 404
    return send_file(path, mimetype=upload.mime_type, as_attachment=True, download_name=upload.original_name)


@api.get("/auth/me")
@authenticate()
def current_user():
    return jsonify(user=_safe_user(g.current_user), onboarding=_progress(g.current_user))
