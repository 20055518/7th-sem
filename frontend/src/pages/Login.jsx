import { useState } from "react";
import {
  Link,
  useNavigate,
} from "react-router-dom";
import { useGoogleLogin } from "@react-oauth/google";

import AppNav from "../components/AppNav";

import {
  login,
  loginWithGoogle,
  getMyQueue,
} from "../api";

import "./Login.css";

import loginVideo from "../assets/login.mp4";


export default function Login() {

  const navigate = useNavigate();


  const [
    email,
    setEmail,
  ] = useState("");


  const [
    password,
    setPassword,
  ] = useState("");

  const [
  showPassword,
  setShowPassword,
] = useState(false);

  const [
    error,
    setError,
  ] = useState("");


  const [
    loading,
    setLoading,
  ] = useState(false);


  /* ==========================================================
     GOOGLE AUTHENTICATION
     ========================================================== */

  const googleLogin = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
      console.log(
        "Google OAuth success response:",
        tokenResponse
      );

      try {
        setError("");
        setLoading(true);

        if (!tokenResponse?.access_token) {
          throw new Error(
            "Google authentication completed but no access token was returned."
          );
        }

        const data = await loginWithGoogle(
          tokenResponse.access_token
        );

        if (data?.role !== "patient") {
          throw new Error(
            "This Google account is not registered as a patient account."
          );
        }

        try {
          await getMyQueue();

          navigate(
            "/patient-dashboard",
            {
              replace: true,
            },
          );

          return;

        } catch (queueError) {
          if (
            queueError?.status === 404
          ) {
            navigate(
              "/join-queue",
              {
                replace: true,
              },
            );

            return;
          }

          if (
            queueError?.status === 401
          ) {
            throw new Error(
              "Session expired while loading your queue. Please sign in again."
            );
          }

          navigate(
            "/patient-dashboard",
            {
              replace: true,
            },
          );

          return;
        }

      } catch (error) {
        console.error(
          "Google login error:",
          error
        );

        setError(
          error?.message ||
          "Unable to sign in with Google."
        );
      } finally {
        setLoading(false);
      }
    },

    onError: (error) => {
      console.error(
        "Google OAuth error:",
        error
      );

      setLoading(false);

      setError(
        "Google sign-in was cancelled or failed."
      );
    },
  });


  // ==========================================================
  // HANDLE LOGIN
  // ==========================================================

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    const cleanEmail = email.trim().toLowerCase();

    // Validate email format: must have local-part, '@', and valid domain name with extension (e.g., user@gmail.com)
    // Disallow invalid formats like missing username, malformed domain, or single-character domain typos
    const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    if (!emailRegex.test(cleanEmail)) {
      setError("Please enter a valid email address (e.g. name@gmail.com).");
      return;
    }

    setLoading(true);

    try {
      const data = await login(
        cleanEmail,
        password,
      );


      // ======================================================
      // DOCTOR
      // ======================================================

      if (
        data.role === "doctor"
      ) {

        navigate(
          "/doctor-dashboard",
          {
            replace: true,
          },
        );

        return;
      }


      // ======================================================
      // NURSE
      // ======================================================

      if (
        data.role === "nurse"
      ) {

        navigate(
          "/nurse-dashboard",
          {
            replace: true,
          },
        );

        return;
      }


      // ======================================================
      // RECEPTION
      // ======================================================

      if (
        data.role === "reception"
      ) {

        navigate(
          "/reception-dashboard",
          {
            replace: true,
          },
        );

        return;
      }


      // ======================================================
      // ADMIN
      // ======================================================

      if (
        data.role === "admin"
      ) {

        navigate(
          "/admin-dashboard",
          {
            replace: true,
          },
        );

        return;
      }


      // ======================================================
      // PATIENT
      // ======================================================

      if (
        data.role === "patient"
      ) {

        try {

          // --------------------------------------------------
          // Check existing queue
          // --------------------------------------------------

          await getMyQueue();


          // --------------------------------------------------
          // Existing queue found
          // --------------------------------------------------

          navigate(
            "/patient-dashboard",
            {
              replace: true,
            },
          );

          return;

        } catch (queueError) {

          // --------------------------------------------------
          // No active queue
          // --------------------------------------------------

          if (
            queueError?.status === 404
          ) {

            navigate(
              "/join-queue",
              {
                replace: true,
              },
            );

            return;
          }


          // --------------------------------------------------
          // Authentication error
          // --------------------------------------------------

          if (
            queueError?.status === 401
          ) {

            throw new Error(
              "Your session could not be verified. Please sign in again.",
            );
          }


          // --------------------------------------------------
          // Other error
          // --------------------------------------------------

          throw queueError;
        }
      }


      // ======================================================
      // UNKNOWN ROLE
      // ======================================================

      navigate(
        "/",
        {
          replace: true,
        },
      );

    } catch (err) {

      console.error(
        "Login error:",
        err,
      );


      setError(
        err?.message ||
        "Login failed.",
      );

    } finally {

      setLoading(false);
    }
  }


  // ==========================================================
  // RENDER
  // ==========================================================

  return (

    <main className="login-page">

      {/* ====================================================
          FULL PAGE BACKGROUND VIDEO
          ==================================================== */}

      <video
        className="login-background-video"
        autoPlay
        loop
        muted
        playsInline
        preload="auto"
      >

        <source
          src={loginVideo}
          type="video/mp4"
        />

      </video>


      {/* ====================================================
          VIDEO OVERLAY
          ==================================================== */}

      <div className="login-video-overlay" />


      {/* ====================================================
          NAVIGATION
          ==================================================== */}

      <div className="login-nav-wrapper">

        <AppNav />

      </div>


      {/* ====================================================
          LOGIN CONTENT
          ==================================================== */}

      <section className="login-content">

        <div className="login-card">

          {/* ==================================================
              LOGIN HEADER
              ================================================== */}

          <div className="login-header">

            <div className="login-icon">
              +
            </div>


            <p className="eyebrow">
              SECURE LOGIN
            </p>


            <h1>
              Sign in
            </h1>


            

          </div>


          {/* ==================================================
              LOGIN FORM
              ================================================== */}

          <form
            className="login-form"
            onSubmit={handleSubmit}
          >

            {/* ================================================
                EMAIL
                ================================================ */}

            <label className="login-field">

              <span>
                Email
              </span>


              <input
                type="email"
                value={email}
                onChange={(event) =>
                  setEmail(
                    event.target.value,
                  )
                }
                placeholder="you@example.com"
                autoComplete="email"
                disabled={loading}
                required
              />

            </label>


            {/* ================================================
                PASSWORD
                ================================================ */}

            <label className="login-field">

              <span>
                Password
              </span>


              <div className="password-input-wrapper">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(event) =>
                      setPassword(
                        event.target.value,
                      )
                    }
                    placeholder="Enter your password"
                    autoComplete="current-password"
                    disabled={loading}
                    required
                  />

                  <button
                    type="button"
                    className="password-toggle"
                    onClick={() =>
                      setShowPassword(
                        (current) => !current
                      )
                    }
                    aria-label={
                      showPassword
                        ? "Hide password"
                        : "Show password"
                    }
                  >
                    {showPassword ? (
                      <svg
                        width="19"
                        height="19"
                        viewBox="0 0 24 24"
                        fill="none"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                        <circle
                          cx="12"
                          cy="12"
                          r="3"
                          stroke="currentColor"
                          strokeWidth="2"
                        />
                      </svg>
                    ) : (
                      <svg
                        width="19"
                        height="19"
                        viewBox="0 0 24 24"
                        fill="none"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          d="M3 3l18 18"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                        />
                        <path
                          d="M10.58 10.58A2 2 0 0 0 13.42 13.42"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                        />
                        <path
                          d="M9.88 5.1A10.8 10.8 0 0 1 12 5c6.5 0 10 7 10 7a18.3 18.3 0 0 1-3.16 3.94"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                        <path
                          d="M6.61 6.61C3.7 8.27 2 12 2 12s3.5 7 10 7c1.55 0 2.91-.36 4.09-.91"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    )}
                  </button>
                </div>

            </label>


            {/* ================================================
                ERROR
                ================================================ */}

            {error && (

              <p
                className="error-text"
                role="alert"
              >
                {error}
              </p>

            )}


            {/* ================================================
                SUBMIT
                ================================================ */}

            <button
              className="button primary login-button"
              type="submit"
              disabled={loading}
            >

              {loading
                ? "Signing in..."
                : "Sign in"}

            </button>

            <div className="login-divider">
              <span>OR</span>
            </div>

            <button
              type="button"
              className="google-login-button"
              onClick={() => {
                setError("");
                googleLogin();
              }}
              disabled={loading}
            >
              <span className="google-logo">G</span>
              Continue with Google
            </button>

          </form>


          {/* ==================================================
              SIGNUP
              ================================================== */}

          <p className="auth-switch">

            Don't have an account?{" "}

            <Link to="/signup">
              Create one
            </Link>

          </p>


          {/* ==================================================
              SECURITY NOTE
              ================================================== */}

          <div className="login-security-note">

            <span className="security-dot">
              •
            </span>

            Secure hospital account access

          </div>

        </div>

      </section>

    </main>
  );
}