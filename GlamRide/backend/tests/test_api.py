import io
import tempfile
import unittest
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app import create_app
from app.models import OTPCode, Service, StylistProfile, StylistService, Upload, User, db, utc_now
from seed import SERVICES
from werkzeug.security import generate_password_hash


class MarketplaceApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-key",
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "UPLOAD_FOLDER": str(Path(self.temp_dir.name, "private")),
                "DEMO_OTP_ENABLED": True,
                "DEMO_SEED": False,
            }
        )
        self.client = self.app.test_client()
        with self.app.app_context():
            for item in SERVICES:
                db.session.add(Service(**item))
            self.customer = User(
                full_name="Test Customer",
                phone="+254712345678",
                password_hash=generate_password_hash("Customer123!"),
                role="customer",
                phone_verified=True,
                onboarding_status="active",
                onboarding_data={"current_step": 6, "completed_steps": [1, 2, 3, 4, 5, 6]},
            )
            self.stylist_user = User(
                full_name="Test Stylist",
                phone="+254712345679",
                password_hash=generate_password_hash("Stylist123!"),
                role="stylist",
                phone_verified=True,
                onboarding_status="verified",
                onboarding_data={
                    "current_step": 6,
                    "completed_steps": [1, 2, 3, 4, 5, 6],
                    "portfolio_upload_ids": [],
                },
            )
            self.admin = User(
                full_name="Test Admin",
                phone="+254712345670",
                password_hash=generate_password_hash("Admin123!"),
                role="admin",
                phone_verified=True,
                onboarding_status="verified",
            )
            db.session.add_all([self.customer, self.stylist_user, self.admin])
            db.session.flush()
            self.profile = StylistProfile(
                user_id=self.stylist_user.id,
                display_name="Test Stylist",
                bio="A trusted Nairobi beauty professional.",
                gender="female",
                status="verified",
                base_area="Kilimani",
                base_lat=-1.292,
                base_lng=36.785,
            )
            db.session.add(self.profile)
            db.session.flush()
            db.session.add(
                StylistService(
                    stylist_id=self.profile.id,
                    service_id=1,
                    price_kes=4000,
                    duration_minutes=60,
                )
            )
            portfolio_ids = []
            for index in range(5):
                upload = Upload(
                    id=f"test-upload-{index}",
                    user_id=self.stylist_user.id,
                    original_name=f"portfolio-{index}.jpg",
                    stored_name=f"portfolio-{index}.jpg",
                    mime_type="image/jpeg",
                )
                db.session.add(upload)
                portfolio_ids.append(upload.id)
            self.stylist_user.onboarding_data = {
                **self.stylist_user.onboarding_data,
                "portfolio_upload_ids": portfolio_ids,
            }
            db.session.commit()
            self.customer_id = self.customer.id
            self.stylist_user_id = self.stylist_user.id
            self.profile_id = self.profile.id
        self.customer_token = self._login("0712345678", "Customer123!")
        self.stylist_token = self._login("0712345679", "Stylist123!")
        self.admin_token = self._login("0712345670", "Admin123!")

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def _login(self, phone, password):
        response = self.client.post("/api/auth/login", json={"phone": phone, "password": password})
        self.assertEqual(response.status_code, 200, response.json)
        return response.json["token"]

    @staticmethod
    def _auth(token):
        return {"Authorization": f"Bearer {token}"}

    def test_registration_verifies_kenyan_phone_and_issues_session(self):
        response = self.client.post(
            "/api/auth/register",
            json={
                "full_name": "New Customer",
                "phone": "0712 345 681",
                "password": "StrongPass123",
                "role": "customer",
            },
        )
        self.assertEqual(response.status_code, 201, response.json)
        verify = self.client.post(
            "/api/auth/verify-otp",
            json={"phone": "+254712345681", "code": response.json["demo_otp"]},
        )
        self.assertEqual(verify.status_code, 200, verify.json)
        self.assertEqual(verify.json["user"]["role"], "customer")
        self.assertEqual(verify.json["onboarding"]["current_step"], 3)
        location = self.client.put(
            "/api/onboarding/step/3",
            headers=self._auth(verify.json["token"]),
            json={"address": "Kilimani, Nairobi", "latitude": None, "longitude": None},
        )
        self.assertEqual(location.status_code, 200, location.json)
        self.assertEqual(location.json["progress"]["status"], "active")

    def test_unverified_stylists_are_not_listed(self):
        response = self.client.get("/api/stylists?service_id=1&lat=-1.29&lng=36.78")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["display_name"] for item in response.json["stylists"]], ["Test Stylist"])
        self.assertIsNotNone(response.json["stylists"][0]["distance_km"])

    def test_customer_can_book_and_stylist_can_progress_booking(self):
        scheduled = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        payload = {
            "stylist_id": self.profile_id,
            "service_id": 1,
            "scheduled_at": scheduled,
            "address": "Kilimani, Nairobi",
            "landmark": "Near Yaya Centre",
            "latitude": -1.29,
            "longitude": 36.78,
            "directions_note": "Call when you reach the gate.",
            "policy_accepted": True,
        }
        no_consent = dict(payload)
        no_consent.pop("policy_accepted")
        blocked = self.client.post(
            "/api/bookings",
            headers=self._auth(self.customer_token),
            json=no_consent,
        )
        self.assertEqual(blocked.status_code, 400)
        response = self.client.post(
            "/api/bookings",
            headers=self._auth(self.customer_token),
            json=payload,
        )
        self.assertEqual(response.status_code, 201, response.json)
        self.assertEqual(response.json["booking"]["status"], "requested")
        self.assertEqual(response.json["booking"]["directions_note"], "Call when you reach the gate.")
        booking_id = response.json["booking"]["id"]
        for status in ("confirmed", "on_the_way", "arrived", "in_progress", "completed"):
            result = self.client.patch(
                f"/api/bookings/{booking_id}/status",
                headers=self._auth(self.stylist_token),
                json={"status": status},
            )
            self.assertEqual(result.status_code, 200, result.json)
        review = self.client.post(
            f"/api/bookings/{booking_id}/reviews",
            headers=self._auth(self.customer_token),
            json={"rating": 5, "comment": "Wonderful service."},
        )
        self.assertEqual(review.status_code, 201, review.json)

    def test_overlapping_booking_is_rejected(self):
        scheduled = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        payload = {
            "stylist_id": self.profile_id,
            "service_id": 1,
            "scheduled_at": scheduled,
            "address": "Kilimani, Nairobi",
            "policy_accepted": True,
        }
        first = self.client.post("/api/bookings", headers=self._auth(self.customer_token), json=payload)
        second = self.client.post("/api/bookings", headers=self._auth(self.customer_token), json=payload)
        self.assertEqual(first.status_code, 201, first.json)
        self.assertEqual(second.status_code, 409, second.json)

    def test_admin_can_only_approve_complete_applications(self):
        response = self.client.post(
            f"/api/admin/stylists/{self.stylist_user_id}/review",
            headers=self._auth(self.admin_token),
            json={"decision": "verified"},
        )
        self.assertEqual(response.status_code, 200, response.json)
        forbidden = self.client.get("/api/admin/summary", headers=self._auth(self.customer_token))
        self.assertEqual(forbidden.status_code, 403)
        history = self.client.get("/api/admin/reviews", headers=self._auth(self.admin_token))
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json["reviews"][0]["decision"], "verified")

    def test_customer_gender_preference_filters_public_stylist_search(self):
        matching = self.client.get("/api/stylists?gender_preference=female")
        excluded = self.client.get("/api/stylists?gender_preference=male")
        self.assertEqual([item["display_name"] for item in matching.json["stylists"]], ["Test Stylist"])
        self.assertEqual(excluded.json["stylists"], [])

    def test_otp_can_be_resent_after_cooldown(self):
        registration = self.client.post(
            "/api/auth/register",
            json={
                "full_name": "Resend Customer",
                "phone": "0712 345 682",
                "password": "StrongPass123",
                "role": "customer",
            },
        )
        self.assertEqual(registration.status_code, 201)
        immediate = self.client.post("/api/auth/resend-otp", json={"phone": "0712 345 682"})
        self.assertEqual(immediate.status_code, 429)
        with self.app.app_context():
            pending_user = User.query.filter_by(phone="+254712345682").first()
            pending_code = OTPCode.query.filter_by(user_id=pending_user.id).first()
            pending_code.created_at = utc_now() - timedelta(seconds=31)
            db.session.commit()
        resent = self.client.post("/api/auth/resend-otp", json={"phone": "0712 345 682"})
        self.assertEqual(resent.status_code, 200, resent.json)
        verified = self.client.post(
            "/api/auth/verify-otp",
            json={"phone": "0712 345 682", "code": resent.json["demo_otp"]},
        )
        self.assertEqual(verified.status_code, 200, verified.json)

    def test_stylist_onboarding_upload_submit_and_approval_flow(self):
        registration = self.client.post(
            "/api/auth/register",
            json={
                "full_name": "New Beauty Pro",
                "phone": "0712 345 683",
                "password": "StrongPass123",
                "role": "stylist",
            },
        )
        self.assertEqual(registration.status_code, 201, registration.json)
        verification = self.client.post(
            "/api/auth/verify-otp",
            json={"phone": "0712 345 683", "code": registration.json["demo_otp"]},
        )
        self.assertEqual(verification.status_code, 200, verification.json)
        token = verification.json["token"]
        headers = self._auth(token)
        profile = self.client.put(
            "/api/onboarding/step/3",
            headers=headers,
            json={
                "display_name": "New Pro",
                "bio": "Thoughtful beauty services, with a personal touch.",
                "years_experience": 4,
                "languages": ["English", "Kiswahili"],
                "gender": "female",
            },
        )
        self.assertEqual(profile.status_code, 200, profile.json)
        service_result = self.client.put(
            "/api/onboarding/step/4",
            headers=headers,
            json={"services": [{"service_id": 1, "price_kes": 4200, "duration_minutes": 180}]},
        )
        self.assertEqual(service_result.status_code, 200, service_result.json)
        upload_ids = []
        for index in range(5):
            upload = self.client.post(
                "/api/uploads",
                headers=headers,
                data={"file": (io.BytesIO(b"\x89PNG\r\n\x1a\nportfolio"), f"work-{index}.png")},
                content_type="multipart/form-data",
            )
            self.assertEqual(upload.status_code, 201, upload.json)
            upload_ids.append(upload.json["upload"]["id"])
        portfolio = self.client.put(
            "/api/onboarding/step/5",
            headers=headers,
            json={"portfolio_upload_ids": upload_ids},
        )
        self.assertEqual(portfolio.status_code, 200, portfolio.json)
        work = self.client.put(
            "/api/onboarding/step/6",
            headers=headers,
            json={
                "work_type": "home",
                "base_area": "Kilimani",
                "service_radius_km": 15,
                "working_days": ["Monday", "Tuesday"],
                "work_start": "08:00",
                "work_end": "18:00",
                "travel_buffer_minutes": 30,
            },
        )
        self.assertEqual(work.status_code, 200, work.json)
        submission = self.client.post("/api/stylists/submit", headers=headers, json={})
        self.assertEqual(submission.status_code, 200, submission.json)
        user_id = registration.json["user"]["id"]
        approval = self.client.post(
            f"/api/admin/stylists/{user_id}/review",
            headers=self._auth(self.admin_token),
            json={"decision": "verified"},
        )
        self.assertEqual(approval.status_code, 200, approval.json)
        matches = self.client.get("/api/stylists?service_id=1&gender_preference=female")
        self.assertIn("New Pro", [item["display_name"] for item in matches.json["stylists"]])

    def test_portfolio_files_are_private_to_the_owner_and_admin(self):
        upload = self.client.post(
            "/api/uploads",
            headers=self._auth(self.stylist_token),
            data={"file": (io.BytesIO(b"\xff\xd8\xffprivate-image"), "portfolio.jpg")},
            content_type="multipart/form-data",
        )
        self.assertEqual(upload.status_code, 201, upload.json)
        upload_id = upload.json["upload"]["id"]
        customer_access = self.client.get(
            f"/api/uploads/{upload_id}",
            headers=self._auth(self.customer_token),
        )
        admin_access = self.client.get(
            f"/api/admin/uploads/{upload_id}",
            headers=self._auth(self.admin_token),
        )
        self.assertEqual(customer_access.status_code, 403)
        self.assertEqual(admin_access.status_code, 200)
        admin_access.close()

    def test_scheduling_respects_working_hours_days_and_travel_buffer(self):
        with self.app.app_context():
            stylist_user = db.session.get(User, self.stylist_user_id)
            stylist_user.onboarding_data = {
                "current_step": 6,
                "completed_steps": [1, 2, 3, 4, 5, 6],
                "working_days": ["Monday"],
                "work_start": "08:00",
                "work_end": "18:00",
                "travel_buffer_minutes": 30,
            }
            db.session.commit()
        today = datetime.now(ZoneInfo("Africa/Nairobi")).date()
        days_until_monday = (7 - today.weekday()) % 7 or 7
        monday = today + timedelta(days=days_until_monday)

        def book_at(hour, minute):
            slot = datetime.combine(monday, time(hour, minute), tzinfo=ZoneInfo("Africa/Nairobi"))
            return self.client.post(
                "/api/bookings",
                headers=self._auth(self.customer_token),
                json={
                    "stylist_id": self.profile_id,
                    "service_id": 1,
                    "scheduled_at": slot.isoformat(),
                    "address": "Kilimani, Nairobi",
                    "policy_accepted": True,
                },
            )

        evening = book_at(17, 30)
        outside_day = book_at(10, 0)
        self.assertEqual(evening.status_code, 409)
        self.assertEqual(outside_day.status_code, 201, outside_day.json)
        buffer_conflict = book_at(11, 15)
        self.assertEqual(buffer_conflict.status_code, 409)


if __name__ == "__main__":
    unittest.main()
