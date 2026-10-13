import {
  useState,
} from "react";

import {
  Link,
  useNavigate,
} from "react-router-dom";
import { useGoogleLogin } from "@react-oauth/google";

import AppNav from "../components/AppNav";

import {
  registerPatient,
  loginWithGoogle,
  getMyQueue,
} from "../api";

import loginVideo from "../assets/login.mp4";

import "./Signup.css";


/* ============================================================
   CARE+
   PATIENT SIGNUP
   ============================================================ */

export default function Signup() {

  const navigate =
    useNavigate();


  /* ==========================================================
     STATE
     ========================================================== */

  const [
    email,
    setEmail,
  ] = useState("");


  const [
    password,
    setPassword,
  ] = useState("");


  const [
    confirmPassword,
    setConfirmPassword,
  ] = useState("");

  const [
  showPassword,
  setShowPassword,
] = useState(false);

const [
  showConfirmPassword,
  setShowConfirmPassword,
] = useState(false);


  const [
    error,
    setError,
  ] = useState("");


  const [
    success,
    setSuccess,
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
      console.log("Google OAuth success response:", tokenResponse);

      try {
        setError("");
        setSuccess("");
        setLoading(true);

        if (!tokenResponse?.access_token) {
          throw new Error(
            "Google authentication completed but no access token was returned."
          );
        }

        const data = await loginWithGoogle(tokenResponse.access_token);

        if (data?.role === "patient") {
          try {
            await getMyQueue();
            navigate("/patient-dashboard", { replace: true });
            return;
          } catch (queueError) {
            if (queueError?.status === 404) {
              navigate("/join-queue", { replace: true });
              return;
            }
            // If checking queue failed with another error, still route to dashboard
            navigate("/patient-dashboard", { replace: true });
            return;
          }
        } else {
          throw new Error(
            "Account authenticated, but patient permissions were not granted."
          );
        }

      } catch (authError) {
        console.error("Google authentication error:", authError);

        setError(
          authError?.message ||
          "Unable to complete Google sign-in."
        );
      } finally {
        setLoading(false);
      }
    },

    onError: (error) => {
      console.error("Google OAuth error:", error);

      setLoading(false);

      setError(
        "Google sign-in was cancelled or failed."
      );
    },
  });


  /* ==========================================================
     SUBMIT
     ========================================================== */

  async function handleSubmit(
    event,
  ) {

    event.preventDefault();

    setError("");

    setSuccess("");


    const cleanEmail = email.trim().toLowerCase();

    const gmailRegex = /^[a-zA-Z][a-zA-Z0-9._%+-]*@gmail\.com$/;

    if (!gmailRegex.test(cleanEmail)) {
      setError(
        "Only valid @gmail.com email addresses are allowed for patient accounts (e.g. yourname@gmail.com)."
      );
  return;
}

    /* ========================================================
       PASSWORD VALIDATION
       ======================================================== */

   if (password !== confirmPassword) {
  setError("Passwords do not match.");
  return;
      }

      if (password.length < 8) {
        setError("Password must contain at least 8 characters.");
        return;
      }

      if (/\s/.test(password)) {
        setError("Password must not contain spaces.");
        return;
      }

      if (!/[A-Z]/.test(password)) {
        setError("Password must contain at least one uppercase letter.");
        return;
      }

      if (!/[a-z]/.test(password)) {
        setError("Password must contain at least one lowercase letter.");
        return;
      }

      if (!/[0-9]/.test(password)) {
        setError("Password must contain at least one number.");
        return;
      }

      if (!/[@#$%!^&*()_+\-=]/.test(password)) {
        setError("Password must contain at least one special character.");
        return;
      }


    /* ========================================================
       REGISTER PATIENT
       ======================================================== */

    try {

      await registerPatient(
        cleanEmail,
        password,
      );


      setSuccess(
        "Account created successfully. Redirecting to login...",
      );


      setTimeout(
        () => {

          navigate(
            "/login",
          );

        },
        1200,
      );


    } catch (
      error
    ) {

      setError(
        error?.message ||
        "Unable to create your account.",
      );


    } finally {

      setLoading(false);

    }

  }


  /* ==========================================================
     UI
     ========================================================== */

  return (
    <div className="signup-page">
      <video
        className="signup-background-video"
        autoPlay
        muted
        loop
        playsInline
      >
        <source src={loginVideo} type="video/mp4" />
      </video>

      <div className="signup-video-overlay" />

      <div className="signup-nav-wrapper">
        <AppNav />
      </div>

      <main className="signup-content">


        {/* ==================================================
            SIGNUP CARD
            ================================================== */}

        <section className="signup-card">


          {/* =================================================
              SIGNUP HEADER
              ================================================= */}

          <div className="signup-header">


            <div className="signup-icon">

              <span>
                +
              </span>

            </div>


            <div>

              <p className="eyebrow">
                PATIENT REGISTRATION
              </p>


              <h1>
                Create account
              </h1>


              

            </div>

          </div>


          {/* =================================================
              FORM
              ================================================= */}

          <form
            className="signup-form"
            onSubmit={
              handleSubmit
            }
          >


            {/* ==============================================
                EMAIL
                ============================================== */}

            <label className="signup-field">

              <span>
                Email
              </span>


              <input
                type="email"
                value={email}
                onChange={(
                  event,
                ) =>
                  setEmail(
                    event.target.value,
                  )
                }
                placeholder="you@gmail.com"
                autoComplete="email"
                required
              />

            </label>


            {/* ==============================================
                PASSWORD
                ============================================== */}

            <label className="signup-field">

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
    placeholder="Create a password"
    autoComplete="new-password"
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


            {/* ==============================================
                CONFIRM PASSWORD
                ============================================== */}

           <label className="signup-field">

                <span>
                  Confirm Password
                </span>

                <div className="password-input-wrapper">
                    <input
                      type={showConfirmPassword ? "text" : "password"}
                      value={confirmPassword}
                      onChange={(event) =>
                        setConfirmPassword(
                          event.target.value,
                        )
                      }
                      placeholder="Confirm your password"
                      autoComplete="new-password"
                      required
                    />

                    <button
                      type="button"
                      className="password-toggle"
                      onClick={() =>
                        setShowConfirmPassword(
                          (current) => !current
                        )
                      }
                      aria-label={
                        showConfirmPassword
                          ? "Hide confirm password"
                          : "Show confirm password"
                      }
                    >
                      {showConfirmPassword ? (
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
            {/* ==============================================
                ERROR
                ============================================== */}

            {error && (

              <div
                className="signup-message signup-error"
                role="alert"
              >

                <span className="message-icon">
                  !
                </span>

                <span>
                  {error}
                </span>

              </div>

            )}


            {/* ==============================================
                SUCCESS
                ============================================== */}

            {success && (

              <div
                className="signup-message signup-success"
                role="status"
              >

                <span className="message-icon">
                  ✓
                </span>

                <span>
                  {success}
                </span>

              </div>

            )}


            {/* ==============================================
                SUBMIT BUTTON
                ============================================== */}

            <button
              className="button primary signup-button"
              type="submit"
              disabled={loading}
            >

              {loading
                ? "Creating account..."
                : "Create account"}

            </button>
            
                      <div className="signup-divider">
            <span>OR</span>
          </div>

          <button
            type="button"
            className="google-signup-button"
            onClick={() => {
              setError("");
              setSuccess("");
              googleLogin();
            }}
            disabled={loading}
          >
            <span className="google-logo">G</span>
            Continue with Google
          </button>

          </form>


          {/* =================================================
              LOGIN LINK
              ================================================= */}

          <p className="auth-switch">

            Already have an account?{" "}


            <Link to="/login">
              Sign in
            </Link>

          </p>




        </section>
      </main>
    </div>

  );

}