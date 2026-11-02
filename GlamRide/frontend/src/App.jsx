import { useEffect, useMemo, useState } from "react";

const categories = [
  "All services",
  "Braids",
  "Wig styling",
  "Hair care",
  "Makeup & nails",
  "Makeup",
  "Nails",
  "Brows & lashes",
  "Skin & spa",
];
const stylistPortraits = [
  "/images/stylist-one.jpg",
  "/images/stylist-two.jpg",
  "/images/stylist-three.jpg",
  "/images/stylist-four.jpg",
];

function servicePhoto(service) {
  const name = service.name.toLowerCase();
  if (name.includes("braid") || name.includes("loc") || name.includes("cornrow") || name.includes("wig")) {
    return "/images/service-braids.jpg";
  }
  if (name.includes("nail") || name.includes("manicure") || name.includes("pedicure") || name.includes("acrylic")) {
    return "/images/service-nails.jpg";
  }
  if (name.includes("facial") || name.includes("skin") || name.includes("wax")) {
    return "/images/service-facial.jpg";
  }
  if (name.includes("makeup") || name.includes("lash") || name.includes("brow")) {
    return "/images/service-beauty.jpg";
  }
  return "/images/service-hair.jpg";
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(result.error || `Request failed (${response.status}).`);
  }
  return result;
}

function formatPrice(price) {
  return `KSh ${Number(price).toLocaleString("en-KE")}`;
}

function localDateTimeMinimum() {
  const date = new Date(Date.now() + 60 * 60 * 1000);
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

function getDeviceLocation() {
  if (!navigator.geolocation) {
    throw new Error("This browser does not support GPS location.");
  }
  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(
      resolve,
      (error) => {
        const messages = {
          1: "Location permission was denied. Allow location access in your browser settings, or search by neighbourhood.",
          2: "Your location could not be determined. Try again or search by neighbourhood.",
          3: "Getting your location timed out. Try again when you have a clearer signal.",
        };
        reject(new Error(messages[error.code] || "Could not get your location."));
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
    );
  });
}

function ServiceCard({ service, onBook }) {
  return (
    <article className="service-card">
      <img className="service-photo" src={servicePhoto(service)} alt={`${service.name} at a beauty salon`} loading="lazy" />
      <span className="service-category">{service.category}</span>
      <h3>{service.name}</h3>
      <p>{service.description}</p>
      <div className="service-card__bottom">
        <div><strong>{formatPrice(service.base_price)}</strong><span>{service.duration_minutes} min</span></div>
        <button className="icon-button" onClick={() => onBook(service)} aria-label={`Book ${service.name}`}>↗</button>
      </div>
    </article>
  );
}

function StylistCard({ stylist, onSelect, onBook }) {
  return (
    <article className="stylist-card">
      <div className={`stylist-avatar stylist-avatar--${(stylist.id % 4) + 1}`} aria-hidden="true">
        <img src={stylistPortraits[(stylist.id - 1) % stylistPortraits.length]} alt="" loading="lazy" />
        <span className="available-dot" />
      </div>
      <div className="stylist-card__body">
        <div className="stylist-card__heading">
          <h3>{stylist.name}</h3>
          <span className="rating"><span aria-hidden="true">★</span> {stylist.rating.toFixed(1)}</span>
        </div>
        <p className="stylist-specialty">{stylist.specialties}</p>
        <p className="stylist-location"><span aria-hidden="true">⌖</span> {stylist.location}</p>
        {stylist.distance_km != null && <p className="stylist-distance">{stylist.distance_km < 1 ? "Less than 1 km away" : `${stylist.distance_km} km away`}</p>}
        <div className="stylist-card__footer">
          <span>{stylist.total_reviews} reviews</span>
          <div className="card-actions">
            <button className="text-button" onClick={() => onSelect(stylist)}>Profile</button>
            <button className="text-button" onClick={() => onBook(stylist)}>Book <span aria-hidden="true">→</span></button>
          </div>
        </div>
      </div>
    </article>
  );
}

function StatusBadge({ value }) {
  return <span className={`status-badge status-${value.replaceAll("_", "-")}`}>{value.replaceAll("_", " ")}</span>;
}

function BookingCard({ booking, role, onStatus, onPayment, onReview }) {
  const [rating, setRating] = useState("5");
  const [comment, setComment] = useState("");
  const [reviewOpen, setReviewOpen] = useState(false);
  const date = new Date(booking.scheduled_date);
  const stylistActions = {
    pending: [["accepted", "Accept"], ["cancelled", "Decline"]],
    accepted: [["in_progress", "Start service"], ["cancelled", "Cancel"]],
    in_progress: [["completed", "Complete service"]],
  };
  const adminActions = ["pending", "accepted", "in_progress", "completed", "cancelled"]
    .filter((status) => status !== booking.status);

  return (
    <article className="booking-card">
      <div className="booking-card__head">
        <div>
          <span className="booking-ref">BOOKING #{booking.id}</span>
          <h3>{booking.service_name}</h3>
        </div>
        <StatusBadge value={booking.status} />
      </div>
      <div className="booking-details">
        <span><b>With</b> {role === "stylist" ? booking.customer_name : booking.stylist_name}</span>
        <span><b>When</b> {date.toLocaleString("en-KE", { dateStyle: "medium", timeStyle: "short" })}</span>
        <span><b>Where</b> {booking.booking_type === "home" ? "Home visit" : "Salon"} · {booking.location}</span>
        <span><b>Price</b> {formatPrice(booking.service_price)}</span>
        {booking.notes && <span className="booking-notes"><b>Notes</b> {booking.notes}</span>}
      </div>
      {role === "stylist" && booking.latitude != null && booking.longitude != null && (
        <div className="booking-directions">
          <a
            className="small-button"
            href={`https://www.google.com/maps/dir/?api=1&destination=${booking.latitude},${booking.longitude}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open directions to customer ↗
          </a>
          <span>The customer shared their pin for this appointment.</span>
        </div>
      )}
      {role === "customer" && booking.latitude != null && booking.longitude != null && (
        <div className="booking-directions">
          <a
            className="text-button"
            href={`https://www.google.com/maps/search/?api=1&query=${booking.latitude},${booking.longitude}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            View the pin you shared ↗
          </a>
        </div>
      )}
      <div className="booking-payment">
        <span>Payment: {booking.payment_method === "mpesa" ? "M-Pesa" : "Cash"} · {booking.payment_status.replaceAll("_", " ")}</span>
        {role === "customer" && booking.payment_status !== "demo_paid" && booking.status !== "cancelled" && (
          <button className="small-button small-button--soft" onClick={() => onPayment(booking.id)}>Simulate demo payment</button>
        )}
        {booking.payment_status === "demo_paid" && <span className="demo-caption">Demo only — no charge</span>}
      </div>
      {role === "stylist" && (
        <div className="booking-actions">
          {(stylistActions[booking.status] || []).map(([status, label]) => (
            <button key={status} className={status === "cancelled" ? "small-button small-button--outline" : "small-button"} onClick={() => onStatus(booking.id, status)}>{label}</button>
          ))}
        </div>
      )}
      {role === "admin" && (
        <div className="booking-actions">
          <label className="sr-only" htmlFor={`booking-status-${booking.id}`}>Update booking #{booking.id}</label>
          <select id={`booking-status-${booking.id}`} value={booking.status} onChange={(event) => onStatus(booking.id, event.target.value)}>
            {[booking.status, ...adminActions].map((status) => <option key={status} value={status}>{status.replaceAll("_", " ")}</option>)}
          </select>
        </div>
      )}
      {role === "customer" && ["pending", "accepted"].includes(booking.status) && (
        <div className="booking-actions"><button className="small-button small-button--outline" onClick={() => onStatus(booking.id, "cancelled")}>Cancel booking</button></div>
      )}
      {role === "customer" && booking.status === "completed" && !booking.review && (
        <div className="review-area">
          {reviewOpen ? (
            <form className="review-form" onSubmit={(event) => { event.preventDefault(); onReview(booking.id, Number(rating), comment); }}>
              <label>Rating <select value={rating} onChange={(event) => setRating(event.target.value)}>{[5, 4, 3, 2, 1].map((score) => <option key={score} value={score}>{score} / 5</option>)}</select></label>
              <label>Your review <textarea value={comment} onChange={(event) => setComment(event.target.value)} maxLength={1000} rows="2" placeholder="Share a little about your experience" /></label>
              <button className="small-button" type="submit">Post review</button>
            </form>
          ) : <button className="text-button" onClick={() => setReviewOpen(true)}>Leave a review →</button>}
        </div>
      )}
      {booking.review && (
        <div className="posted-review"><span className="rating">{"★".repeat(booking.review.rating)}</span> {booking.review.comment}</div>
      )}
    </article>
  );
}

function App() {
  const [services, setServices] = useState([]);
  const [stylists, setStylists] = useState([]);
  const [nearbyStylists, setNearbyStylists] = useState(null);
  const [nearbyRadius, setNearbyRadius] = useState("25");
  const [nearbyBusy, setNearbyBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [page, setPage] = useState("home");
  const [category, setCategory] = useState("All services");
  const [location, setLocation] = useState("");
  const [locationInput, setLocationInput] = useState("");
  const [selectedStylist, setSelectedStylist] = useState(null);
  const [selectedService, setSelectedService] = useState(null);
  const [user, setUser] = useState(null);
  const [authRole, setAuthRole] = useState("customer");
  const [authMode, setAuthMode] = useState("login");
  const [returnPage, setReturnPage] = useState("dashboard");
  const [dashboard, setDashboard] = useState(null);
  const [working, setWorking] = useState(false);
  const [stylistGps, setStylistGps] = useState(null);
  const [bookingForm, setBookingForm] = useState({
    service_id: "", stylist_id: "", scheduled_date: "", booking_type: "home",
    location: "", latitude: null, longitude: null, notes: "", payment_method: "mpesa",
  });

  async function loadPublicData() {
    setLoading(true);
    setError("");
    try {
      const [serviceData, stylistData] = await Promise.all([
        api("/api/services"),
        api("/api/stylists"),
      ]);
      setServices(serviceData);
      setStylists(stylistData);
    } catch (loadError) {
      setError(loadError.message || "Could not load GlamRide.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPublicData();
    api("/api/me").then(setUser).catch(() => setUser(null));
  }, []);

  useEffect(() => {
    if (!user || !["dashboard", "stylist-dashboard", "admin-dashboard"].includes(page)) {
      return;
    }
    let active = true;
    const endpoint = user.role === "admin" ? "/api/admin/dashboard"
      : user.role === "stylist" ? "/api/stylist/dashboard" : "/api/bookings";
    api(endpoint)
      .then((result) => { if (active) setDashboard(result); })
      .catch((loadError) => { if (active) setError(loadError.message); });
    return () => { active = false; };
  }, [page, user]);

  const visibleServices = useMemo(
    () => category === "All services" ? services : services.filter((service) => service.category === category),
    [category, services],
  );
  const filteredStylists = useMemo(() => {
    const term = location.trim().toLowerCase();
    if (nearbyStylists !== null) return nearbyStylists;
    return term ? stylists.filter((stylist) => stylist.location.toLowerCase().includes(term)) : stylists;
  }, [location, nearbyStylists, stylists]);
  const bookingStylist = stylists.find((stylist) => String(stylist.id) === bookingForm.stylist_id);

  function navigate(nextPage) {
    setPage(nextPage);
    setError("");
    setNotice("");
    window.scrollTo(0, 0);
  }

  function goToBooking(service = null, stylist = null) {
    setSelectedService(service);
    setSelectedStylist(stylist);
    setBookingForm((current) => ({
      ...current,
      service_id: service ? String(service.id) : current.service_id,
      stylist_id: stylist ? String(stylist.id) : current.stylist_id,
      location: stylist?.location || current.location,
      booking_type: stylist?.offers_home_visit ? "home" : "salon",
    }));
    if (!user) {
      setReturnPage("book");
      setAuthRole("customer");
      setAuthMode("login");
      navigate("auth");
      return;
    }
    if (user.role !== "customer") {
      setError("Sign in with a customer account to book a service.");
      return;
    }
    navigate("book");
  }

  function searchStylists(event) {
    event.preventDefault();
    setNearbyStylists(null);
    setLocation(locationInput);
    navigate("stylists");
  }

  async function findNearbyStylists() {
    setNearbyBusy(true);
    setError("");
    try {
      const position = await getDeviceLocation();
      const { latitude, longitude } = position.coords;
      const results = await api(
        `/api/stylists?latitude=${encodeURIComponent(latitude)}&longitude=${encodeURIComponent(longitude)}&radius_km=${encodeURIComponent(nearbyRadius)}`,
      );
      setNearbyStylists(results);
      setLocation("");
      setLocationInput("");
      navigate("stylists");
      if (!results.length) {
        setNotice("No artists with a shared GPS location were found in that radius. Try a larger radius or search by neighbourhood.");
      } else {
        setNotice(`Showing ${results.length} nearby artist${results.length === 1 ? "" : "s"}, closest first.`);
      }
    } catch (locationError) {
      setError(locationError.message);
    } finally {
      setNearbyBusy(false);
    }
  }

  async function setStylistGpsLocation() {
    setError("");
    try {
      const position = await getDeviceLocation();
      setStylistGps({
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
      });
    } catch (locationError) {
      setError(locationError.message);
    }
  }

  async function setBookingGpsLocation() {
    setError("");
    try {
      const position = await getDeviceLocation();
      setBookingForm((current) => ({
        ...current,
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        location: "Customer-shared GPS location",
      }));
    } catch (locationError) {
      setError(locationError.message);
    }
  }

  function clearBookingGpsLocation() {
    setBookingForm((current) => ({
      ...current,
      latitude: null,
      longitude: null,
      location: "",
    }));
  }

  async function submitAuth(event) {
    event.preventDefault();
    setWorking(true);
    setError("");
    try {
      const form = new FormData(event.currentTarget);
      const payload = Object.fromEntries(form.entries());
      let nextUser;
      if (authMode === "register-stylist") {
        payload.offers_home_visit = form.has("offers_home_visit");
        payload.offers_salon = form.has("offers_salon");
        if (stylistGps) Object.assign(payload, stylistGps);
        nextUser = await api("/api/stylist/register", { method: "POST", body: JSON.stringify(payload) });
      } else if (authMode === "register") {
        nextUser = await api("/api/register", { method: "POST", body: JSON.stringify(payload) });
      } else {
        nextUser = await api("/api/login", {
          method: "POST",
          body: JSON.stringify({ ...payload, role: authRole }),
        });
      }
      const completeUser = await api("/api/me");
      setUser(completeUser);
      setNotice(authMode === "register-stylist" ? "Your profile is submitted. An administrator must approve it before it appears to customers." : "You are signed in.");
      setStylistGps(null);
      navigate(completeUser.role === "admin" ? "admin-dashboard"
        : completeUser.role === "stylist" ? "stylist-dashboard"
          : returnPage === "book" ? "book" : "dashboard");
      if (nextUser.role === "stylist") setDashboard(null);
    } catch (authError) {
      setError(authError.message);
    } finally {
      setWorking(false);
    }
  }

  async function signOut() {
    try {
      await api("/api/logout", { method: "POST" });
      setUser(null);
      setDashboard(null);
      setNotice("You have signed out.");
      navigate("home");
    } catch (signOutError) {
      setError(signOutError.message);
    }
  }

  async function submitBooking(event) {
    event.preventDefault();
    setWorking(true);
    setError("");
    try {
      await api("/api/bookings", { method: "POST", body: JSON.stringify(bookingForm) });
      setNotice("Booking request sent. Your stylist can now accept or decline it.");
      setDashboard(null);
      navigate("dashboard");
    } catch (bookingError) {
      setError(bookingError.message);
    } finally {
      setWorking(false);
    }
  }

  async function updateBooking(bookingId, status) {
    try {
      await api(`/api/bookings/${bookingId}/status`, { method: "PATCH", body: JSON.stringify({ status }) });
      setDashboard(null);
      setNotice(`Booking #${bookingId} updated.`);
      const endpoint = user.role === "admin" ? "/api/admin/dashboard"
        : user.role === "stylist" ? "/api/stylist/dashboard" : "/api/bookings";
      setDashboard(await api(endpoint));
    } catch (actionError) {
      setError(actionError.message);
    }
  }

  async function recordDemoPayment(bookingId) {
    try {
      const result = await api(`/api/bookings/${bookingId}/demo-payment`, { method: "POST" });
      setNotice(result.message);
      setDashboard(await api("/api/bookings"));
    } catch (paymentError) {
      setError(paymentError.message);
    }
  }

  async function submitReview(bookingId, rating, comment) {
    try {
      await api(`/api/bookings/${bookingId}/reviews`, {
        method: "POST",
        body: JSON.stringify({ rating, comment }),
      });
      setNotice("Thanks for sharing your review.");
      setDashboard(await api("/api/bookings"));
      setStylists(await api("/api/stylists"));
    } catch (reviewError) {
      setError(reviewError.message);
    }
  }

  async function setAvailability(isAvailable) {
    try {
      await api("/api/stylist/availability", {
        method: "PATCH",
        body: JSON.stringify({ is_available: isAvailable }),
      });
      setDashboard(await api("/api/stylist/dashboard"));
      setStylists(await api("/api/stylists"));
      setNotice(isAvailable ? "You are listed as available." : "You are temporarily unavailable.");
    } catch (availabilityError) {
      setError(availabilityError.message);
    }
  }

  async function saveStylistGpsLocation() {
    setError("");
    try {
      const position = await getDeviceLocation();
      await api("/api/stylist/location", {
        method: "PATCH",
        body: JSON.stringify({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        }),
      });
      setDashboard(await api("/api/stylist/dashboard"));
      setStylists(await api("/api/stylists"));
      setNotice("Your private GPS pin is saved for nearby searches.");
    } catch (locationError) {
      setError(locationError.message);
    }
  }

  async function approveStylist(stylistId, isApproved) {
    try {
      await api(`/api/admin/stylists/${stylistId}`, {
        method: "PATCH",
        body: JSON.stringify({ is_approved: isApproved }),
      });
      setDashboard(await api("/api/admin/dashboard"));
      setStylists(await api("/api/stylists"));
      setNotice(isApproved ? "Stylist approved." : "Stylist declined.");
    } catch (approvalError) {
      setError(approvalError.message);
    }
  }

  const dashboardPage = user?.role === "admin" ? "admin-dashboard"
    : user?.role === "stylist" ? "stylist-dashboard" : "dashboard";

  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="#home" onClick={(event) => { event.preventDefault(); navigate("home"); }}>
          <span className="brand-mark" aria-hidden="true">g</span>
          <span>glamride<span className="brand-dot">.</span></span>
        </a>
        <nav className="main-nav" aria-label="Main navigation">
          <button className={page === "home" ? "nav-link is-active" : "nav-link"} onClick={() => navigate("home")}>Home</button>
          <button className={page === "services" ? "nav-link is-active" : "nav-link"} onClick={() => navigate("services")}>Services</button>
          <button className={page === "stylists" ? "nav-link is-active" : "nav-link"} onClick={() => navigate("stylists")}>Our artists</button>
        </nav>
        <div className="header-account">
          {user ? (
            <>
              <button className="header-account__name" onClick={() => navigate(dashboardPage)}>{user.name}</button>
              <button className="header-cta" onClick={signOut}>Sign out</button>
            </>
          ) : <button className="header-cta" onClick={() => { setAuthRole("customer"); setAuthMode("login"); navigate("auth"); }}>Sign in</button>}
        </div>
      </header>

      <main>
        {error && <div className="error-banner" role="alert"><span>{error}</span><button onClick={() => setError("")}>Dismiss</button></div>}
        {notice && <div className="notice-banner" role="status"><span>{notice}</span><button onClick={() => setNotice("")}>Dismiss</button></div>}

        {selectedStylist && page === "profile" ? (
          <ProfilePage stylist={selectedStylist} onBack={() => { setSelectedStylist(null); navigate("stylists"); }} onBook={() => goToBooking(null, selectedStylist)} />
        ) : page === "auth" ? (
          <section className="auth-page page-width">
            <div className="auth-panel">
              <span className="eyebrow">{authMode === "register-stylist" ? "JOIN OUR ARTIST COMMUNITY" : "WELCOME TO GLAMRIDE"}</span>
              <h1>{authMode === "login" ? "Lovely to see you." : authMode === "register-stylist" ? "Share your talent." : "Make time for you."}</h1>
              <p>{authMode === "login" ? "Sign in to manage your appointments and bookings." : authMode === "register-stylist" ? "Create your stylist profile. It will go live after an administrator approves it." : "Create an account to find and book your beauty artist."}</p>
              {authMode === "login" && (
                <label className="field-label">I’m signing in as
                  <select value={authRole} onChange={(event) => setAuthRole(event.target.value)}>
                    <option value="customer">Customer</option><option value="stylist">Stylist</option><option value="admin">Administrator</option>
                  </select>
                </label>
              )}
              <form className="form-stack" onSubmit={submitAuth}>
                {authMode !== "login" && <label className="field-label">Full name<input name="name" required maxLength={100} autoComplete="name" /></label>}
                <label className="field-label">Email address<input type="email" name="email" required maxLength={120} autoComplete="email" /></label>
                {authMode !== "login" && <label className="field-label">Phone number<input name="phone" required maxLength={30} autoComplete="tel" /></label>}
                {authMode === "register-stylist" && <>
                  <label className="field-label">Neighbourhood / location<input name="location" required maxLength={150} placeholder="e.g. Westlands, Nairobi" /></label>
                  <label className="field-label">Your specialties<input name="specialties" required maxLength={300} placeholder="e.g. Braids · Natural hair" /></label>
                  <label className="field-label">About your work<textarea name="bio" required maxLength={1500} rows="3" /></label>
                  <div className="gps-share">
                    <button className="small-button small-button--soft" type="button" onClick={setStylistGpsLocation}>
                      {stylistGps ? "Update my GPS pin" : "Share my GPS location"}
                    </button>
                    <span>{stylistGps ? "GPS pin added. It stays private and is used only to calculate nearby search results." : "Optional: customers can find you by distance. Your exact pin is kept private."}</span>
                  </div>
                  <div className="checkbox-row">
                    <label><input type="checkbox" name="offers_home_visit" defaultChecked /> I offer home visits</label>
                    <label><input type="checkbox" name="offers_salon" defaultChecked /> I have a salon</label>
                  </div>
                </>}
                {authMode !== "login" && authRole !== "admin" && <label className="field-label">Password<input type="password" name="password" required minLength={8} maxLength={128} autoComplete="new-password" /></label>}
                {authMode === "login" && <label className="field-label">Password<input type="password" name="password" required maxLength={128} autoComplete="current-password" /></label>}
                <button className="primary-button form-submit" type="submit" disabled={working}>{working ? "One moment…" : authMode === "login" ? "Sign in" : "Create account"} <span aria-hidden="true">→</span></button>
              </form>
              <div className="auth-switches">
                {authMode === "login" ? <>
                  <span>New to GlamRide? <button onClick={() => { setAuthRole("customer"); setAuthMode("register"); }}>Create a customer account</button></span>
                  <span>A beauty professional? <button onClick={() => { setAuthRole("stylist"); setAuthMode("register-stylist"); }}>Join as a stylist</button></span>
                </> : <span>Already have an account? <button onClick={() => { setAuthMode("login"); setAuthRole("customer"); }}>Sign in</button></span>}
              </div>
            </div>
          </section>
        ) : page === "book" ? (
          <section className="section page-width booking-page">
            <div className="listing-intro">
              <span className="eyebrow">YOUR LITTLE MOMENT</span><h1>Make it <em>yours.</em></h1>
              <p>Request a time with an artist. They’ll confirm your appointment.</p>
            </div>
            <form className="booking-form form-stack" onSubmit={submitBooking}>
              <label className="field-label">Choose a service
                <select required value={bookingForm.service_id || selectedService?.id || ""} onChange={(event) => setBookingForm({ ...bookingForm, service_id: event.target.value })}>
                  <option value="">Select a service</option>{services.map((service) => <option key={service.id} value={service.id}>{service.name} · {formatPrice(service.base_price)}</option>)}
                </select>
              </label>
              <label className="field-label">Choose your artist
                <select required value={bookingForm.stylist_id || selectedStylist?.id || ""} onChange={(event) => {
                  const stylist = stylists.find((item) => String(item.id) === event.target.value);
                  setBookingForm({ ...bookingForm, stylist_id: event.target.value, location: stylist?.location || "", booking_type: stylist?.offers_home_visit ? "home" : "salon" });
                }}>
                  <option value="">Select an available artist</option>{stylists.map((stylist) => <option key={stylist.id} value={stylist.id}>{stylist.name} · {stylist.location}</option>)}
                </select>
              </label>
              <label className="field-label">Appointment date and time<input type="datetime-local" required min={localDateTimeMinimum()} value={bookingForm.scheduled_date} onChange={(event) => setBookingForm({ ...bookingForm, scheduled_date: event.target.value })} /></label>
              <fieldset className="booking-type">
                <legend>Where would you like your service?</legend>
                <label><input type="radio" name="booking_type" value="home" disabled={bookingStylist && !bookingStylist.offers_home_visit} checked={bookingForm.booking_type === "home"} onChange={(event) => setBookingForm({ ...bookingForm, booking_type: event.target.value })} /> Home visit</label>
                <label><input type="radio" name="booking_type" value="salon" disabled={bookingStylist && !bookingStylist.offers_salon} checked={bookingForm.booking_type === "salon"} onChange={(event) => setBookingForm({ ...bookingForm, booking_type: event.target.value })} /> Salon</label>
              </fieldset>
              <div className="gps-share gps-share--booking">
                <button className="small-button small-button--soft" type="button" onClick={setBookingGpsLocation}>
                  {bookingForm.latitude != null ? "Update shared GPS pin" : "Use my current location"}
                </button>
                <span>{bookingForm.latitude != null ? "Your exact pin will be shared only with your selected stylist and the platform admin for this booking." : "Optional: share a map pin so your stylist can navigate to you. You can also enter an address instead."}</span>
              </div>
              {bookingForm.latitude != null && <button className="clear-gps-button" type="button" onClick={clearBookingGpsLocation}>Remove GPS pin</button>}
              <label className="field-label">Appointment address / salon location<input required maxLength={200} value={bookingForm.location} onChange={(event) => setBookingForm({ ...bookingForm, location: event.target.value })} placeholder="Your neighbourhood or address" /></label>
              <label className="field-label">Anything your artist should know?<textarea maxLength={1000} rows="3" value={bookingForm.notes} onChange={(event) => setBookingForm({ ...bookingForm, notes: event.target.value })} placeholder="Optional notes" /></label>
              <label className="field-label">Preferred payment method
                <select value={bookingForm.payment_method} onChange={(event) => setBookingForm({ ...bookingForm, payment_method: event.target.value })}><option value="mpesa">M-Pesa</option><option value="cash">Cash</option></select>
              </label>
              <p className="demo-notice"><b>Demo checkout:</b> selecting a payment method does not charge you. You can simulate payment from your booking dashboard.</p>
              <button className="primary-button form-submit" disabled={working}>{working ? "Sending request…" : "Request this appointment"} <span aria-hidden="true">→</span></button>
            </form>
          </section>
        ) : page === "dashboard" ? (
          <section className="section page-width dashboard-page">
            <div className="dashboard-heading"><div><span className="eyebrow">YOUR GLAMRIDE</span><h1>Your appointments.</h1><p>Hi {user?.name}, here’s how everything is looking.</p></div><button className="primary-button" onClick={() => goToBooking()}>Book a service <span>→</span></button></div>
            {dashboard ? dashboard.length ? <div className="booking-list">{dashboard.map((booking) => <BookingCard key={booking.id} booking={booking} role="customer" onStatus={updateBooking} onPayment={recordDemoPayment} onReview={submitReview} />)}</div> : <EmptyState title="Nothing booked just yet." text="Your next lovely appointment is only a few clicks away." action="Find a service" onClick={() => navigate("services")} /> : <div className="loading-state">Finding your appointments…</div>}
          </section>
        ) : page === "stylist-dashboard" ? (
          <section className="section page-width dashboard-page">
            <div className="dashboard-heading"><div><span className="eyebrow">ARTIST STUDIO</span><h1>Your studio.</h1><p>Welcome, {user?.name}.</p></div>
              {dashboard?.is_approved && <button className="primary-button" onClick={() => setAvailability(!dashboard.is_available)}>{dashboard.is_available ? "Pause availability" : "Set available"} <span>↗</span></button>}
            </div>
            {dashboard && !dashboard.is_approved && <div className="pending-banner"><strong>Your profile is awaiting approval.</strong><span>An administrator will review your profile before it appears in search and accepts bookings.</span></div>}
            {dashboard?.is_approved && <div className="stylist-gps-controls">
              <p className="availability-note">Your profile is currently <StatusBadge value={dashboard.is_available ? "available" : "unavailable"} /> to customers.</p>
              <div className="gps-share">
                <button className="small-button small-button--soft" onClick={saveStylistGpsLocation}>Share / update my GPS location</button>
                <span>{dashboard.stylist.has_gps_location ? "A private GPS pin is set for nearby customer searches." : "Add a private GPS pin to appear in nearby searches."}</span>
              </div>
            </div>}
            {dashboard ? dashboard.bookings.length ? <div className="booking-list">{dashboard.bookings.map((booking) => <BookingCard key={booking.id} booking={booking} role="stylist" onStatus={updateBooking} />)}</div> : <EmptyState title="No appointments yet." text="New customer requests will appear here." /> : <div className="loading-state">Opening your studio…</div>}
          </section>
        ) : page === "admin-dashboard" ? (
          <section className="section page-width dashboard-page">
            <div className="dashboard-heading"><div><span className="eyebrow">GLAMRIDE CONTROL ROOM</span><h1>Platform overview.</h1><p>Review artist applications and keep bookings on track.</p></div></div>
            {dashboard ? <>
              <div className="stats-grid">
                {Object.entries({ "Customers": dashboard.stats.customers, "Approved artists": dashboard.stats.stylists, "Awaiting review": dashboard.stats.pending_stylists, "Bookings": dashboard.stats.bookings, "Demo payments": formatPrice(dashboard.stats.revenue) }).map(([label, value]) => <div className="stat-card" key={label}><strong>{value}</strong><span>{label}</span></div>)}
              </div>
              <div className="admin-section"><div className="section-heading"><div><span className="eyebrow">NEW TO THE COMMUNITY</span><h2>Artist applications</h2></div></div>
                {dashboard.pending_stylists.length ? <div className="application-grid">{dashboard.pending_stylists.map((stylist) => <article className="application-card" key={stylist.id}><span className="eyebrow">{stylist.location}</span><h3>{stylist.name}</h3><p>{stylist.specialties}</p><p>{stylist.bio}</p><p>{stylist.email} · {stylist.phone}</p><div className="booking-actions"><button className="small-button" onClick={() => approveStylist(stylist.id, true)}>Approve artist</button><button className="small-button small-button--outline" onClick={() => approveStylist(stylist.id, false)}>Decline</button></div></article>)}</div> : <p className="empty-state">No artist applications to review.</p>}
              </div>
              <div className="admin-section"><div className="section-heading"><div><span className="eyebrow">PLATFORM ACTIVITY</span><h2>All bookings</h2></div></div>
                {dashboard.bookings.length ? <div className="booking-list">{dashboard.bookings.map((booking) => <BookingCard key={booking.id} booking={booking} role="admin" onStatus={updateBooking} />)}</div> : <p className="empty-state">No bookings have been made yet.</p>}
              </div>
            </> : <div className="loading-state">Loading platform overview…</div>}
          </section>
        ) : page === "home" ? (
          <>
            <section className="hero">
              <div className="hero-content">
                <div className="eyebrow">YOUR BEAUTY, YOUR WAY</div>
                <h1>Feel like <em>yourself.</em><br />Only more radiant.</h1>
                <p className="hero-description">Meet Nairobi’s independent beauty artists and find the right person for your next look.</p>
                <form className="search-bar" onSubmit={searchStylists}><span className="search-pin" aria-hidden="true">⌖</span><label className="sr-only" htmlFor="location-search">Your neighbourhood</label><input id="location-search" value={locationInput} onChange={(event) => setLocationInput(event.target.value)} placeholder="Where are you? Try Westlands" /><button type="submit">Find my artist <span>→</span></button></form>
                <button className="gps-search-button" onClick={findNearbyStylists} disabled={nearbyBusy}>{nearbyBusy ? "Finding your location…" : "⌖ Use my location to find nearby artists"}</button>
                <div className="hero-note">Independent beauty professionals across Nairobi</div>
              </div>
              <div className="hero-photo-wrap"><img className="hero-photo" src="/images/hero-stylist.jpg" alt="A hairstylist caring for a client's hair in a salon" fetchPriority="high" /></div>
            </section>
            <section className="trust-strip" aria-label="GlamRide highlights"><span>Curated local artists</span><span>Appointments that fit your schedule</span><span>At home or in salon</span><span>Transparent service prices</span></section>
            <section className="section page-width"><div className="section-heading"><div><span className="eyebrow">A LITTLE SOMETHING FOR YOU</span><h2>Find your next <em>favourite.</em></h2></div><button className="text-button" onClick={() => navigate("services")}>All services <span>↗</span></button></div>
              {loading ? <div className="loading-state">Finding the lovely things…</div> : <div className="service-grid">{services.slice(0, 4).map((service) => <ServiceCard key={service.id} service={service} onBook={(item) => goToBooking(item)} />)}</div>}
            </section>
            <section className="artist-section"><div className="page-width"><div className="section-heading"><div><span className="eyebrow">GOOD HANDS, GOOD ENERGY</span><h2>Meet the <em>artists.</em></h2></div><button className="text-button" onClick={() => navigate("stylists")}>Meet everyone <span>↗</span></button></div>
              {loading ? <div className="loading-state">Finding your artists…</div> : <div className="stylist-grid">{stylists.slice(0, 3).map((stylist) => <StylistCard key={stylist.id} stylist={stylist} onSelect={(item) => { setSelectedStylist(item); navigate("profile"); }} onBook={(item) => goToBooking(null, item)} />)}</div>}
            </div></section>
            <section className="closing-cta page-width"><span className="eyebrow">A LITTLE TIME FOR YOU</span><h2>Your next great<br /><em>hair day starts here.</em></h2><button className="primary-button" onClick={() => navigate("services")}>Find your artist <span>→</span></button></section>
          </>
        ) : page === "services" ? (
          <section className="section page-width listing-page"><div className="listing-intro"><span className="eyebrow">THE GOOD STUFF</span><h1>Little rituals.<br /><em>Lovely results.</em></h1><p>From protective styles to soft glam, find the service that feels like you.</p></div>
            <div className="filter-row" aria-label="Filter by service category">{categories.map((item) => <button key={item} className={category === item ? "filter-chip is-selected" : "filter-chip"} onClick={() => setCategory(item)}>{item}</button>)}</div>
            {loading ? <div className="loading-state">Finding the lovely things…</div> : visibleServices.length ? <div className="service-grid service-grid--listing">{visibleServices.map((service) => <ServiceCard key={service.id} service={service} onBook={(item) => goToBooking(item)} />)}</div> : <p className="empty-state">No services in this category just yet. Try another one.</p>}
          </section>
        ) : (
          <section className="section page-width listing-page"><div className="listing-intro"><span className="eyebrow">GOOD HANDS, GOOD ENERGY</span><h1>Your people.<br /><em>Your kind of beauty.</em></h1><p>Meet independent professionals who love what they do—and care about how you feel.</p></div>
            <form className="artist-search" onSubmit={searchStylists}><label className="sr-only" htmlFor="artist-location">Search by neighbourhood</label><span>⌖</span><input id="artist-location" value={locationInput} onChange={(event) => setLocationInput(event.target.value)} placeholder="Search a neighbourhood, e.g. Kilimani" /><button type="submit">Search</button>{(location || nearbyStylists !== null) && <button className="clear-filter" type="button" onClick={() => { setLocation(""); setLocationInput(""); setNearbyStylists(null); }}>Clear</button>}</form>
            <div className="nearby-tools">
              <label>Search radius
                <select value={nearbyRadius} onChange={(event) => setNearbyRadius(event.target.value)}>
                  <option value="5">5 km</option><option value="10">10 km</option><option value="25">25 km</option><option value="50">50 km</option><option value="100">100 km</option>
                </select>
              </label>
              <button className="small-button small-button--soft" onClick={findNearbyStylists} disabled={nearbyBusy}>{nearbyBusy ? "Finding nearby…" : "⌖ Find artists near me"}</button>
              {nearbyStylists !== null && <span>Closest first · only artists who opted in to location are shown</span>}
            </div>
            {loading ? <div className="loading-state">Finding your artists…</div> : filteredStylists.length ? <div className="stylist-grid stylist-grid--listing">{filteredStylists.map((stylist) => <StylistCard key={stylist.id} stylist={stylist} onSelect={(item) => { setSelectedStylist(item); navigate("profile"); }} onBook={(item) => goToBooking(null, item)} />)}</div> : <p className="empty-state">{nearbyStylists !== null ? `No artists with a shared GPS pin were found within ${nearbyRadius} km. Try a larger radius or search by neighbourhood.` : `No artists found${location ? ` near “${location}”` : ""}. Try a different neighbourhood.`}</p>}
          </section>
        )}
      </main>

      <footer className="site-footer">
        <a className="brand footer-brand" href="#home" onClick={(event) => { event.preventDefault(); navigate("home"); }}><span className="brand-mark" aria-hidden="true">g</span><span>glamride<span className="brand-dot">.</span></span></a>
        <p>Beauty, made personal. <span>♡</span></p><span className="footer-location">NAIROBI, KENYA · EST. 2026</span>
      </footer>
    </div>
  );
}

function ProfilePage({ stylist, onBack, onBook }) {
  const [reviews, setReviews] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api(`/api/stylists/${stylist.id}/reviews`)
      .then((result) => { if (active) setReviews(result); })
      .catch((loadError) => { if (active) setError(loadError.message); });
    return () => { active = false; };
  }, [stylist.id]);
  return (
    <section className="profile-page page-width">
      <button className="back-link" onClick={onBack}>← Back to artists</button>
      <div className="profile-panel">
        <img className="profile-avatar" src={stylistPortraits[(stylist.id - 1) % stylistPortraits.length]} alt={`Portrait of ${stylist.name}`} />
        <div className="profile-copy"><span className="eyebrow">GLAMRIDE ARTIST</span><h1>{stylist.name}</h1><p className="profile-meta"><span className="rating"><span>★</span> {stylist.rating.toFixed(1)}</span> · {stylist.total_reviews} reviews · {stylist.location}</p><p className="profile-bio">{stylist.bio}</p><p className="profile-specialty">{stylist.specialties}</p><div className="visit-options">{stylist.offers_home_visit && <span>⌂ Home visits</span>}{stylist.offers_salon && <span>✦ Salon appointments</span>}</div><button className="primary-button" onClick={onBook}>Book this artist <span>→</span></button></div>
      </div>
      <div className="profile-reviews"><div className="section-heading"><div><span className="eyebrow">KIND WORDS</span><h2>Client reviews</h2></div></div>{error ? <p className="empty-state">{error}</p> : reviews.length ? reviews.map((review) => <article className="review-card" key={review.id}><span className="rating">{"★".repeat(review.rating)}</span><strong>{review.customer_name}</strong><p>{review.comment || "Service completed with love."}</p></article>) : <p className="empty-state">Reviews from GlamRide bookings will appear here.</p>}</div>
    </section>
  );
}

function EmptyState({ title, text, action, onClick }) {
  return <div className="empty-panel"><h2>{title}</h2><p>{text}</p>{action && <button className="primary-button" onClick={onClick}>{action} <span>→</span></button>}</div>;
}

export default App;
