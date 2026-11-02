# GlamRide

GlamRide is a React beauty marketplace frontend backed by a Flask REST API and
a SQLite database. Customers can find artists, request and manage appointments,
choose a demo payment method, and review completed bookings. Stylists can apply,
manage their availability, and update appointment status. Administrators review
stylist applications and manage bookings.

## Run locally

### Flask API

From the project directory, create and activate a virtual environment, then run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
python backend\app.py
```

The API starts at `http://127.0.0.1:5000`. It creates and seeds
`backend\instance\glamride.db` on first run.

Set a long, unique `FLASK_SECRET_KEY` environment variable before deploying;
without one, a new random key is generated when the app starts, so existing
sessions are signed out after a restart. When deploying behind HTTPS, also set
`SESSION_COOKIE_SECURE=1`.
Create the first administrator interactively from the project directory:

```powershell
flask --app backend.app create-admin
```

The command prompts for the administrator email, name, and password. Do not
use a shared or production password for a local demo.

### React app

In a second terminal:

```powershell
Set-Location frontend
npm install
npm run dev
```

Open the local URL printed by Vite. Its development server proxies `/api`
requests to Flask.

## Features

- **Customers:** sign up, sign in, book services, track and cancel eligible
  bookings, simulate a demo payment, and review completed appointments.
- **Stylists:** apply for approval, sign in, set availability, and accept,
  decline, start, or complete their assigned bookings. Stylists can opt in to
  sharing a private GPS pin so nearby customers can find them.
- **Administrators:** approve or decline artist applications, view platform
  totals, and update booking statuses.
- **GPS and directions:** customers may opt in to browser location to search
  for opted-in artists by distance, choose a search radius, and share an exact
  appointment pin with their selected stylist. Assigned stylists can open
  customer-shared appointment pins in Google Maps for directions. GPS access
  requires permission and a secure context (HTTPS, or localhost during
  development); neighbourhood search and typed addresses remain available
  without GPS. Exact customer appointment pins are only included in responses
  visible to that customer, their assigned stylist, and administrators.
- **Payments:** M-Pesa and cash are preference labels only in this demo.
  “Simulate demo payment” records a demo status; it does not connect to a
  provider or transfer/charge money.
- **Beauty services:** braids, wig styling, hair care, makeup, nails, brows and
  lashes, and skin and spa appointments.
- **Photography:** locally stored stock photographs are illustrative and do not
  represent the sample stylist profiles or guarantee a particular service result.

## API

- `GET /api/health` — API health
- `GET /api/services` — services; optionally filter with `?category=Braids`
- `GET /api/stylists` — available, approved artists; optionally filter with `?location=Westlands`
- `GET /api/stylists?latitude=-1.28&longitude=36.82&radius_km=25` — nearby artists, closest first; only artists who opted in to a GPS pin are included
- `GET /api/stylists/<id>` — one artist profile
- `GET /api/stylists/<id>/reviews` — public reviews for an artist
- `POST /api/register`, `POST /api/login`, `POST /api/logout`, `GET /api/me` — account session
- `POST /api/stylist/register` — submit a stylist application
- `POST /api/bookings`, `GET /api/bookings`, `PATCH /api/bookings/<id>/status` — appointments
- `POST /api/bookings/<id>/demo-payment` — record a no-charge demo payment
- `POST /api/bookings/<id>/reviews` — review a completed appointment
- `GET /api/stylist/dashboard`, `PATCH /api/stylist/availability` — stylist tools
- `PATCH /api/stylist/location` — opt in to or update a private stylist GPS pin
- `GET /api/admin/dashboard`, `PATCH /api/admin/stylists/<id>` — administrator tools

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend -p "test_*.py" -v
Set-Location frontend
npm run build
```

The included names, profiles, ratings, and reviews counts are sample content
for local development. Stylist accounts created through the site stay hidden
from customers until an administrator approves them.
