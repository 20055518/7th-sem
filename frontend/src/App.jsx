import { useEffect, useState } from "react";
import { Link, Route, Routes, useNavigate } from "react-router-dom";
import QRScanner from "./QRScanner";
import { generateQueueQr, loginPatient } from "./api";

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

function QueueAccessPage() {
  const [scanned, setScanned] = useState(false);

  return (
    <main className="placeholder">
      <Link to="/">CarePath+</Link>

      <h1>Scan Your Queue QR Code</h1>
      <p>Allow camera access and scan the QR code provided by reception.</p>

      <QRScanner onScan={() => setScanned(true)} />

      {scanned && (
        <p role="status">
          QR code scanned successfully.
        </p>
      )}

      <Link className="button secondary" to="/">
        Return home
      </Link>
    </main>
  );
}

function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("patient1@example.com");
  const [password, setPassword] = useState("TestPassword123!");
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    try {
      await loginPatient(email, password);
      navigate("/patient-qr");
    } catch (loginError) {
      setError(loginError.message);
    }
  }

  return (
    <main className="placeholder">
      <Link to="/">CarePath+</Link>
      <h1>Patient Login</h1>

      <form onSubmit={handleSubmit}>
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="Email"
          required
        />

        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="Password"
          required
        />

        <button className="button primary" type="submit">
          Login
        </button>
      </form>

      {error && <p role="alert">{error}</p>}
    </main>
  );
}

function PatientQRPage() {
  const [department, setDepartment] = useState("Cardiology");
  const [tokenNumber, setTokenNumber] = useState("1");
  const [qrImageData, setQrImageData] = useState("");
  const [error, setError] = useState("");

  async function handleGenerateQr(event) {
    event.preventDefault();
    setError("");

    try {
      const data = await generateQueueQr(
        department,
        Number(tokenNumber),
      );

      setQrImageData(data.qr_image_data);
    } catch (qrError) {
      setError(qrError.message);
    }
  }

  return (
    <main className="placeholder">
      <Link to="/">CarePath+</Link>

      <h1>My Queue QR Code</h1>

      <form onSubmit={handleGenerateQr}>
        <input
          value={department}
          onChange={(event) => setDepartment(event.target.value)}
          placeholder="Department"
          required
        />

        <input
          type="number"
          value={tokenNumber}
          onChange={(event) => setTokenNumber(event.target.value)}
          placeholder="Token number"
          min="1"
          required
        />

        <button className="button primary" type="submit">
          Generate QR
        </button>
      </form>

      {error && <p role="alert">{error}</p>}

      {qrImageData && (
        <img
          src={qrImageData}
          alt="Patient queue QR code"
          width="300"
        />
      )}
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
        element={<LoginPage />}
      />

      <Route
        path="/queue-access"
        element={<QueueAccessPage />}
      />

      <Route
        path="/patient-qr"
        element={<PatientQRPage />}
      />

      <Route
        path="*"
        element={<PlaceholderPage title="Page Not Found" />}
      />
    </Routes>

  );
}