import { useEffect, useState } from "react";
import { Link, Route, Routes } from "react-router-dom";

function LandingPage() {
  const [apiStatus, setApiStatus] = useState("Checking backend...");

  useEffect(() => {
    fetch("http://127.0.0.1:8000/api/db-health")
      .then((response) => {
        if (!response.ok) {
          throw new Error("Backend request failed");
        }

        return response.json();
      })
      .then((data) => setApiStatus(data.database))
      .catch(() => setApiStatus("Backend is unavailable"));
  }, []);

  return (
    <main className="landing-shell">
      <nav className="topbar" aria-label="Primary navigation">
        <Link className="brand" to="/">
          CarePath<span>+</span>
        </Link>
        <Link className="nav-link" to="/login">
          Staff sign in
        </Link>
      </nav>

      <section className="hero">
        <p className="eyebrow">SMART PATIENT JOURNEY</p>
        <h1>Know where you are. Know when to go.</h1>
        <p className="hero-copy">
          Secure QR queue access and live waiting-time updates for a calmer
          hospital visit.
        </p>

        <div className="hero-actions">
          <Link className="button primary" to="/patient-dashboard">
            Patient dashboard
          </Link>
          <Link className="button secondary" to="/about">
            How it works
          </Link>
        </div>
      </section>

      <section className="feature-grid" aria-label="Platform features">
        <article>
          <strong>QR access</strong>
          <span>Private, token-based queue verification.</span>
        </article>

        <article>
          <strong>Live status</strong>
          <span>Updates without refreshing the page.</span>
        </article>

        <article>
          <strong>Clear guidance</strong>
          <span>Notifications and route instructions when it is your turn.</span>
        </article>
      </section>

      <section className="dashboard-links">
        <h2>Dashboard previews</h2>

        <div className="hero-actions">
          <Link className="button secondary" to="/doctor-dashboard">
            Doctor
          </Link>

          <Link className="button secondary" to="/reception-dashboard">
            Reception
          </Link>

          <Link className="button secondary" to="/admin-dashboard">
            Admin
          </Link>
        </div>
      </section>

      <p className="api-status" role="status">
        Backend status: {apiStatus}
      </p>
    </main>
  );
}

function DashboardPage({ role, title, description }) {
  return (
    <main className="placeholder">
      <Link to="/">CarePath+</Link>

      <p className="eyebrow">{role.toUpperCase()} DASHBOARD</p>
      <h1>{title}</h1>
      <p>{description}</p>

      <section className="feature-grid" aria-label={`${role} dashboard modules`}>
        <article>
          <strong>Queue status</strong>
          <span>Queue information will appear here.</span>
        </article>

        <article>
          <strong>Notifications</strong>
          <span>Important updates will appear here.</span>
        </article>

        <article>
          <strong>Statistics</strong>
          <span>Dashboard statistics will appear here.</span>
        </article>
      </section>

      <Link className="button secondary" to="/">
        Return home
      </Link>
    </main>
  );
}

function PlaceholderPage({ title }) {
  return (
    <main className="placeholder">
      <Link to="/">CarePath+</Link>
      <h1>{title}</h1>
      <p>This route is reserved for a later implementation phase.</p>
    </main>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />

      <Route
        path="/patient-dashboard"
        element={
          <DashboardPage
            role="patient"
            title="Patient Dashboard"
            description="View your token, queue position, estimated waiting time, and doctor information."
          />
        }
      />

      <Route
        path="/doctor-dashboard"
        element={
          <DashboardPage
            role="doctor"
            title="Doctor Dashboard"
            description="Manage the current queue, patient status, consultation progress, and waiting information."
          />
        }
      />

      <Route
        path="/reception-dashboard"
        element={
          <DashboardPage
            role="reception"
            title="Reception Dashboard"
            description="Register patients, generate tokens, and monitor hospital queues."
          />
        }
      />

      <Route
        path="/admin-dashboard"
        element={
          <DashboardPage
            role="admin"
            title="Admin Dashboard"
            description="Manage users, doctors, departments, rooms, queues, and system reports."
          />
        }
      />

      <Route
        path="/about"
        element={<PlaceholderPage title="About CarePath" />}
      />

      <Route
        path="/login"
        element={<PlaceholderPage title="Staff Sign In" />}
      />

      <Route
        path="/queue-access"
        element={<PlaceholderPage title="QR Queue Access" />}
      />

      <Route
        path="*"
        element={<PlaceholderPage title="Page Not Found" />}
      />
    </Routes>
  );
}