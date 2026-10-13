import { useState, useEffect } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { createPortal } from "react-dom";

import { logout, getMyQueue } from "../api";

import "./AppNav.css";


/* ============================================================
   CARE+
   APPLICATION NAVIGATION
   ============================================================ */

export default function AppNav() {

  const navigate = useNavigate();
  const location = useLocation();

  const isLoginPage = location.pathname === "/login";
  const isSignupPage = location.pathname === "/signup";

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [hasActiveQueue, setHasActiveQueue] = useState(false);

  const role = sessionStorage.getItem("user_role");
  const loggedIn = Boolean(
    sessionStorage.getItem("access_token")
  );


  /* ==========================================================
     CLOSE MOBILE MENU WHEN ROUTE CHANGES
     ========================================================== */

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
  let cancelled = false;

  async function checkPatientQueue() {
    if (!loggedIn || role !== "patient") {
      if (!cancelled) {
        setHasActiveQueue(false);
      }
      return;
    }

    try {
      const queue = await getMyQueue();

      if (cancelled) {
        return;
      }

      const active =
        Boolean(queue) &&
        String(queue?.status || "").toLowerCase() !== "completed";

      setHasActiveQueue(active);
    } catch (error) {
      if (!cancelled) {
        console.error(
          "Unable to check patient queue:",
          error
        );
        setHasActiveQueue(false);
      }
    }
  }

  checkPatientQueue();

  return () => {
    cancelled = true;
  };
}, [loggedIn, role, location.pathname]);


  /* ==========================================================
     LOGOUT
     ========================================================== */

  function handleLogout() {

    setMobileMenuOpen(false);

    logout();

    navigate("/login");
  }


  /* ==========================================================
     MOBILE MENU
     ========================================================== */

  const mobileMenu = (
    <>
      {/* ====================================================
          BACKDROP
          ==================================================== */}

      <div
        className="nav-backdrop"
        onClick={() => setMobileMenuOpen(false)}
        aria-hidden="true"
      />


      {/* ====================================================
          MOBILE MENU
          ==================================================== */}

      <div
        className="mobile-nav-menu"
        role="navigation"
        aria-label="Mobile Navigation"
      >

        {/* ==================================================
            GUEST (NOT LOGGED IN)
            ================================================== */}

        {!loggedIn && (
          <>
            <Link
              className="nav-link"
              to="/"
              onClick={() => setMobileMenuOpen(false)}
            >
              Home
            </Link>

            <Link
              className="nav-link"
              to="/about"
              onClick={() => setMobileMenuOpen(false)}
            >
              About
            </Link>

            {isLoginPage && (
              <Link
                className="nav-link"
                to="/signup"
                onClick={() => setMobileMenuOpen(false)}
              >
                Sign Up
              </Link>
            )}

            {isSignupPage && (
              <Link
                className="nav-link"
                to="/login"
                onClick={() => setMobileMenuOpen(false)}
              >
                Sign In
              </Link>
            )}

            {!isLoginPage && !isSignupPage && (
              <>
                <Link
                  className="nav-link"
                  to="/login"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Sign In
                </Link>

                <Link
                  className="nav-link"
                  to="/signup"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Sign Up
                </Link>
              </>
            )}
          </>
        )}


        {/* ==================================================
            PATIENT
            ================================================== */}

        {loggedIn && role === "patient" && (
          <>
            <Link
              className="nav-link"
              to="/patient-dashboard"
              onClick={() => setMobileMenuOpen(false)}
            >
              My Queue
            </Link>
          
          {!hasActiveQueue && (
            <Link
              className="nav-link"
              to="/patient-qr"
              onClick={() => setMobileMenuOpen(false)}
            >
              QR
            </Link>
          )}
          </>
        )}
          {/* ==================================================
            DOCTOR
            ================================================== */}

        {loggedIn && role === "doctor" && (
          <Link
            className="nav-link"
            to="/doctor-dashboard"
            onClick={() => setMobileMenuOpen(false)}
          >
            Doctor Queue
          </Link>
        )}


        {/* ==================================================
            NURSE
            ================================================== */}

        {loggedIn && role === "nurse" && (
          <Link
            className="nav-link"
            to="/nurse-dashboard"
            onClick={() => setMobileMenuOpen(false)}
          >
            Nurse Dashboard
          </Link>
        )}


        {/* ==================================================
            RECEPTION
            ================================================== */}

        {loggedIn && role === "reception" && (
          <Link
            className="nav-link"
            to="/reception-dashboard"
            onClick={() => setMobileMenuOpen(false)}
          >
            Reception
          </Link>
        )}


        {/* ==================================================
            ADMIN
            ================================================== */}

        {loggedIn && role === "admin" && (
          <Link
            className="nav-link"
            to="/admin-dashboard"
            onClick={() => setMobileMenuOpen(false)}
          >
            Admin
          </Link>
        )}


        {/* ==================================================
            LOGOUT (ONLY WHEN LOGGED IN)
            ================================================== */}

        {loggedIn && (
          <button
            type="button"
            className="nav-button"
            onClick={handleLogout}
          >
            Logout
          </button>
        )}

      </div>
    </>
  );


  /* ==========================================================
     MAIN NAVIGATION
     ========================================================== */

  return (
    <>
      <nav className="app-nav">

        {/* ==================================================
            BRAND
            ================================================== */}

        <Link
          className="brand"
          to="/"
          onClick={() => setMobileMenuOpen(false)}
        >
          Care<span>+</span>
        </Link>


        {/* ==================================================
            MOBILE HAMBURGER (ALWAYS ON MOBILE)
            ================================================== */}

        <button
          type="button"
          className={`nav-mobile-toggle ${
            mobileMenuOpen ? "open" : ""
          }`}
          onClick={() =>
            setMobileMenuOpen((prev) => !prev)
          }
          aria-expanded={mobileMenuOpen}
          aria-label={
            mobileMenuOpen
              ? "Close navigation menu"
              : "Open navigation menu"
          }
        >
          <span className="toggle-bar"></span>
          <span className="toggle-bar"></span>
          <span className="toggle-bar"></span>
        </button>


        {/* ==================================================
            SIGN IN (DESKTOP ONLY)
            ================================================== */}

          {!loggedIn && (
  <div className="nav-auth-actions">

    {isLoginPage && (
      <Link
        className="nav-signup"
        to="/signup"
      >
        Sign Up
      </Link>
    )}

    {isSignupPage && (
      <Link
        className="nav-signin"
        to="/login"
      >
        Sign In
      </Link>
    )}

    {!isLoginPage && !isSignupPage && (
            <>
              <Link
                className="nav-signin"
                to="/login"
              >
                Sign In
              </Link>

              <Link
                className="nav-signup"
                to="/signup"
              >
                Sign Up
              </Link>
            </>
          )}

        </div>
      )}

        {/* ==================================================
            DESKTOP NAVIGATION
            ================================================== */}

        <div className="nav-actions">

          {loggedIn && (
            <>

              {/* PATIENT */}

              {role === "patient" && (
                <>
                  <Link
                    className="nav-link"
                    to="/patient-dashboard"
                  >
                    My Queue
                  </Link>

                  {!hasActiveQueue && (
                    <Link
                      className="nav-link"
                      to="/patient-qr"
                    >
                      QR
                    </Link>
                  )}
                </>
              )}


              {/* DOCTOR */}

              {role === "doctor" && (
                <Link
                  className="nav-link"
                  to="/doctor-dashboard"
                >
                  Doctor Queue
                </Link>
              )}


              {/* NURSE */}

              {role === "nurse" && (
                <Link
                  className="nav-link"
                  to="/nurse-dashboard"
                >
                  Nurse Dashboard
                </Link>
              )}


              {/* RECEPTION */}

              {role === "reception" && (
                <Link
                  className="nav-link"
                  to="/reception-dashboard"
                >
                  Reception
                </Link>
              )}


              {/* ADMIN */}

              {role === "admin" && (
                <Link
                  className="nav-link"
                  to="/admin-dashboard"
                >
                  Admin
                </Link>
              )}


              {/* LOGOUT */}

              <button
                type="button"
                className="nav-button"
                onClick={handleLogout}
              >
                Logout
              </button>

            </>
          )}

        </div>

      </nav>


      {/* ====================================================
          MOBILE MENU PORTAL
          ==================================================== */}

      {mobileMenuOpen &&
        createPortal(
          mobileMenu,
          document.body
        )}

    </>
  );
}