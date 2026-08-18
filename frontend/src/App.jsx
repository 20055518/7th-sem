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
        <Link className="brand" to="/">CarePath<span>+</span></Link>
        <Link className="nav-link" to="/login">Staff sign in</Link>
      </nav>
      <section className="hero">
        <p className="eyebrow">SMART PATIENT JOURNEY</p>
        <h1>Know where you are. Know when to go.</h1>
        <p className="hero-copy">Secure QR queue access and live waiting-time updates for a calmer hospital visit.</p>
        <div className="hero-actions">
          <Link className="button primary" to="/queue-access">Access my queue</Link>
          <Link className="button secondary" to="/about">How it works</Link>
        </div>
      </section>
      <section className="feature-grid" aria-label="Platform features">
        <article><strong>QR access</strong><span>Private, token-based queue verification.</span></article>
        <article><strong>Live status</strong><span>Updates without refreshing the page.</span></article>
        <article><strong>Clear guidance</strong><span>Notifications and route instructions when it is your turn.</span></article>
      </section>
      <p className="api-status" role="status">Backend status: {apiStatus}</p>
    </main>
  );
}

function PlaceholderPage({ title }) {
  return <main className="placeholder"><Link to="/">CarePath+</Link><h1>{title}</h1><p>This route is reserved for a later implementation phase.</p></main>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/about" element={<PlaceholderPage title="About CarePath" />} />
      <Route path="/login" element={<PlaceholderPage title="Staff sign in" />} />
      <Route path="/queue-access" element={<PlaceholderPage title="QR Queue Access" />} />
      <Route path="*" element={<PlaceholderPage title="Page not found" />} />
    </Routes>
  );
}
