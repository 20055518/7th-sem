import { lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import Footer from "./components/Footer";
import { useLocation } from "react-router-dom";

// ============================================================
// LAZY-LOADED PAGE MODULES
// Reduces bundle size and loads role dashboards on demand
// ============================================================

const LandingPage = lazy(() => import("./pages/LandingPage"));
const Login = lazy(() => import("./pages/Login"));
const Signup = lazy(() => import("./pages/Signup"));

const PatientDashboard = lazy(() => import("./pages/PatientDashboard"));
const JoinQueue = lazy(() => import("./pages/JoinQueue"));
const PatientQR = lazy(() => import("./pages/PatientQR"));
const QueueAccess = lazy(() => import("./pages/QueueAccess"));

const DoctorDashboard = lazy(() => import("./pages/DoctorDashboard"));
const NurseDashboard = lazy(() => import("./pages/NurseDashboard"));
const ReceptionDashboard = lazy(() => import("./pages/ReceptionDashboard"));
const AdminDashboard = lazy(() => import("./pages/AdminDashboard"));

const About = lazy(() => import("./pages/About"));

// ============================================================
// FALLBACK SPINNER
// ============================================================

function LoadingFallback() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        minHeight: "100vh",
        background: "#f8fafc",
        color: "#0284c7",
        fontFamily: "system-ui, -apple-system, sans-serif",
        gap: "1rem",
      }}
    >
      <div
        style={{
          width: "48px",
          height: "48px",
          border: "4px solid #e2e8f0",
          borderTop: "4px solid #0284c7",
          borderRadius: "50%",
          animation: "carePlusSpin 0.8s linear infinite",
        }}
      />
      <span style={{ fontWeight: 600, fontSize: "1.1rem", color: "#334155" }}>
        Loading Care+...
      </span>
      <style>{`
        @keyframes carePlusSpin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

// ============================================================
// APPLICATION ROUTES
// ============================================================

export default function App() {
   const location = useLocation();

  const hideFooter =
    location.pathname === "/login" ||
    location.pathname === "/signup";

  return (
    <Suspense fallback={<LoadingFallback />}>
      <Routes>
        {/* Public Landing & Info */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/about" element={<About />} />

        {/* Authentication */}
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />

        {/* Patient Experience */}
        <Route path="/patient-dashboard" element={<PatientDashboard />} />
        <Route path="/join-queue" element={<JoinQueue />} />
        <Route path="/patient-qr" element={<PatientQR />} />
        <Route path="/queue-access" element={<QueueAccess />} />

        {/* Clinical & Staff Workspaces */}
        <Route path="/doctor-dashboard" element={<DoctorDashboard />} />
        <Route path="/nurse-dashboard" element={<NurseDashboard />} />
        <Route path="/reception-dashboard" element={<ReceptionDashboard />} />

        {/* System Administration */}
        <Route path="/admin-dashboard" element={<AdminDashboard />} />

        {/* Fallback */}
        <Route path="*" element={<LandingPage />} />
      </Routes>

      {!hideFooter && <Footer />}
    </Suspense>
  );
}