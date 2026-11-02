from werkzeug.security import generate_password_hash

from app import create_app
from app.models import Service, StylistProfile, StylistService, User, db

SERVICES = [
    {
        "name": "Knotless braids",
        "category": "Braids",
        "description": "Lightweight, protective braids styled by a pro.",
        "starting_price_kes": 4000,
        "duration_minutes": 240,
        "image_url": "https://images.unsplash.com/photo-1605497788044-5a32c7078486?auto=format&fit=crop&w=900&q=85",
    },
    {
        "name": "Makeup",
        "category": "Makeup",
        "description": "Camera-ready makeup for celebrations and everyday.",
        "starting_price_kes": 3500,
        "duration_minutes": 90,
        "image_url": "https://images.unsplash.com/photo-1487412947147-5cebf100ffc2?auto=format&fit=crop&w=900&q=85",
    },
    {
        "name": "Gel manicure",
        "category": "Nails",
        "description": "A polished, long-lasting manicure in your space.",
        "starting_price_kes": 2500,
        "duration_minutes": 75,
        "image_url": "https://images.unsplash.com/photo-1610992015732-2449b76344bc?auto=format&fit=crop&w=900&q=85",
    },
    {
        "name": "Signature facial",
        "category": "Skincare",
        "description": "A soothing cleanse, exfoliation and hydration ritual.",
        "starting_price_kes": 5500,
        "duration_minutes": 75,
        "image_url": "https://images.unsplash.com/photo-1570172619644-dfd03ed5d881?auto=format&fit=crop&w=900&q=85",
    },
    {
        "name": "Silk press",
        "category": "Hair",
        "description": "A smooth, heat-styled finish with expert care.",
        "starting_price_kes": 3000,
        "duration_minutes": 120,
        "image_url": "https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9?auto=format&fit=crop&w=900&q=85",
    },
]

STYLISTS = [
    {
        "name": "Akinyi Wanjiru",
        "handle": "Akinyi",
        "gender": "female",
        "bio": "Protective styles with a gentle touch. I specialize in knotless and natural-looking braids.",
        "area": "Westlands",
        "rating": 4.98,
        "reviews": 86,
        "jobs": 128,
        "lat": -1.267,
        "lng": 36.811,
        "services": {1: (4500, 240), 5: (3800, 150)},
    },
    {
        "name": "Nia Kamau",
        "handle": "Nia",
        "gender": "female",
        "bio": "Soft glam, bridal looks, and skin-first makeup for every kind of occasion.",
        "area": "Kilimani",
        "rating": 4.96,
        "reviews": 72,
        "jobs": 109,
        "lat": -1.292,
        "lng": 36.785,
        "services": {2: (4200, 105), 4: (6000, 80)},
    },
    {
        "name": "Mumbi Njeri",
        "handle": "Mumbi",
        "gender": "female",
        "bio": "Thoughtful nail art and clean, long-wearing manicures that feel like you.",
        "area": "Lavington",
        "rating": 4.92,
        "reviews": 53,
        "jobs": 84,
        "lat": -1.278,
        "lng": 36.768,
        "services": {3: (2800, 80)},
    },
    {
        "name": "Zuri Atieno",
        "handle": "Zuri",
        "gender": "female",
        "bio": "Natural hair specialist creating healthy, beautiful styles that last.",
        "area": "Kileleshwa",
        "rating": 4.99,
        "reviews": 104,
        "jobs": 171,
        "lat": -1.282,
        "lng": 36.790,
        "services": {1: (4800, 260), 5: (3500, 135)},
    },
    {
        "name": "Wambui Muthoni",
        "handle": "Wambui",
        "gender": "female",
        "bio": "Relaxing facials and event-ready beauty, brought to your home.",
        "area": "Parklands",
        "rating": 4.89,
        "reviews": 41,
        "jobs": 63,
        "lat": -1.259,
        "lng": 36.815,
        "services": {4: (6500, 90), 2: (3800, 95)},
    },
]


def seed_demo_data():
    if Service.query.count() == 0:
        for item in SERVICES:
            db.session.add(Service(**item))
        db.session.flush()

    demo_accounts = [
        ("Customer", "0712345001", "customer@glamride.co.ke", "customer"),
        ("Stylist", "0712345002", "stylist@glamride.co.ke", "stylist"),
        ("Admin", "0712345003", "admin@glamride.co.ke", "admin"),
    ]
    for name, phone, email, role in demo_accounts:
        if not User.query.filter_by(phone=f"+254{phone[1:]}").first():
            user = User(
                full_name=name,
                phone=f"+254{phone[1:]}",
                email=email,
                password_hash=generate_password_hash("Demo123!"),
                role=role,
                phone_verified=True,
                onboarding_status="active" if role == "customer" else "verified",
                onboarding_data={"current_step": 6, "completed_steps": [1, 2, 3, 4, 5, 6]},
            )
            db.session.add(user)
            db.session.flush()
            if role == "stylist":
                db.session.add(
                    StylistProfile(
                        user_id=user.id,
                        display_name="Demo Stylist",
                        bio="A friendly stylist ready to show you around GlamRide.",
                        years_experience=4,
                        languages=["English", "Kiswahili"],
                        work_type="both",
                        base_area="Kilimani",
                        base_lat=-1.292,
                        base_lng=36.785,
                        status="verified",
                    )
                )
                db.session.flush()
                for service in Service.query.limit(3).all():
                    db.session.add(
                        StylistService(
                            stylist_id=user.stylist_profile.id,
                            service_id=service.id,
                            price_kes=service.starting_price_kes,
                            duration_minutes=service.duration_minutes,
                        )
                    )

    db.session.flush()
    for index, item in enumerate(STYLISTS, start=1):
        email = f"{item['handle'].lower()}@glamride.co.ke"
        phone = f"+254710000{index:03d}"
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(
                full_name=item["name"],
                phone=phone,
                email=email,
                password_hash=generate_password_hash("Demo123!"),
                role="stylist",
                phone_verified=True,
                onboarding_status="verified",
                onboarding_data={
                    "current_step": 6,
                    "completed_steps": [1, 2, 3, 4, 5, 6],
                    "portfolio_upload_ids": [],
                    "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
                    "work_start": "08:00",
                    "work_end": "18:00",
                },
            )
            db.session.add(user)
            db.session.flush()
            profile = StylistProfile(
                user_id=user.id,
                display_name=item["handle"],
                bio=item["bio"],
                gender=item["gender"],
                years_experience=5,
                languages=["English", "Kiswahili"],
                work_type="home",
                base_area=item["area"],
                base_lat=item["lat"],
                base_lng=item["lng"],
                rating=item["rating"],
                review_count=item["reviews"],
                completed_jobs=item["jobs"],
                status="verified",
                available=True,
            )
            db.session.add(profile)
            db.session.flush()
            for service_id, (price, duration) in item["services"].items():
                service = db.session.get(Service, service_id)
                if service:
                    db.session.add(
                        StylistService(
                            stylist_id=profile.id,
                            service_id=service_id,
                            price_kes=price,
                            duration_minutes=duration,
                        )
                    )
    db.session.commit()


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed_demo_data()
    print("GlamRide demo data is ready.")
