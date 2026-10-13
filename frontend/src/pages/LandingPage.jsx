import { useNavigate } from "react-router-dom";

import AppNav from "../components/AppNav";
import homeVideo from "../assets/home.mp4";

import "./LandingPage.css";
import "./LandingResponsive.css";

export default function LandingPage() {

  const navigate = useNavigate();


  return (

    <main className="landing-page">


      {/* =====================================================
          FULL PAGE BACKGROUND VIDEO
          ===================================================== */}

      <video
        className="landing-background-video"
        autoPlay
        loop
        muted
        playsInline
        preload="auto"
        aria-hidden="true"
      >

        <source
          src={homeVideo}
          type="video/mp4"
        />

      </video>


      {/* =====================================================
          FULL PAGE VIDEO OVERLAY
          ===================================================== */}

      <div
        className="landing-video-overlay"
        aria-hidden="true"
      />


      {/* =====================================================
          NAVBAR
          ===================================================== */}

      <div className="landing-nav-wrapper">

        <AppNav />

      </div>


      {/* =====================================================
          HERO SECTION
          ===================================================== */}

      <section className="landing-hero">


        {/* HERO CONTENT */}

        <div className="landing-hero-content">

          <p className="eyebrow">
            SMART PATIENT JOURNEY
          </p>


          <h1>

            Know where you are.

            <br />

            <span>
              Know when to go.
            </span>

          </h1>


          <p className="landing-description">

            Care+ helps patients track their
            hospital queue in real time with
            secure QR-based access and intelligent
            waiting-time prediction.

          </p>


          <div className="landing-actions">


            <button
              className="button primary landing-primary-button"
              onClick={() => navigate("/login")}
            >
              Get Started
            </button>


            <button
              className="button secondary landing-secondary-button"
              onClick={() => navigate("/about")}
            >
              Learn More
            </button>


          </div>

        </div>


        {/* =================================================
            HERO INFORMATION CARD
            ================================================= */}

        <div className="landing-hero-card">


          <div className="hero-card-header">

            <div>

              <p className="card-label">
                LIVE QUEUE
              </p>


              <h2>
                Smart Hospital Flow
              </h2>

            </div>


            <span className="live-pill">

              <span className="live-dot"></span>

              Live

            </span>

          </div>


          {/* =================================================
              STATISTICS
              ================================================= */}

          <div className="hero-stat-grid">


            <div className="hero-stat">

              <span>
                Queue
              </span>

              <strong>
                Live
              </strong>

            </div>


            <div className="hero-stat">

              <span>
                QR Access
              </span>

              <strong>
                Secure
              </strong>

            </div>


            <div className="hero-stat">

              <span>
                Prediction
              </span>

              <strong>
                AI
              </strong>

            </div>


            <div className="hero-stat">

              <span>
                App
              </span>

              <strong>
                None
              </strong>

            </div>


          </div>


          {/* =================================================
              FLOW
              ================================================= */}

          <div className="hero-flow">


            <div className="hero-flow-step">

              <span className="flow-number">
                01
              </span>


              <div>

                <strong>
                  Registration
                </strong>

                <p>
                  Patient enters the hospital.
                </p>

              </div>

            </div>


            <div className="hero-flow-step">

              <span className="flow-number">
                02
              </span>


              <div>

                <strong>
                  Checkup
                </strong>

                <p>
                  Nurse records the initial
                  assessment.
                </p>

              </div>

            </div>


            <div className="hero-flow-step">

              <span className="flow-number">
                03
              </span>


              <div>

                <strong>
                  Queue
                </strong>

                <p>
                  Reception generates the
                  queue QR.
                </p>

              </div>

            </div>


            <div className="hero-flow-step">

              <span className="flow-number">
                04
              </span>


              <div>

                <strong>
                  Track
                </strong>

                <p>
                  Patient follows the live
                  queue.
                </p>

              </div>

            </div>


          </div>

        </div>

      </section>


      {/* =====================================================
          FEATURES
          ===================================================== */}

      <section className="landing-features">


        <div className="landing-section-heading">

          <p className="eyebrow">
            CARE<span>+</span>
          </p>


          <h2>
            A smarter way to manage
            hospital queues.
          </h2>


          <p>

            Designed to connect patients,
            nurses, doctors and reception
            through one secure workflow.

          </p>

        </div>


        <div className="landing-feature-grid">


          {/* FEATURE 1 */}

          <article className="landing-feature-card">

            <div className="feature-icon">
              QR
            </div>


            <h3>
              Secure QR Access
            </h3>


            <p>

              Patients scan the official queue
              QR generated by reception to access
              their queue information.

            </p>

          </article>


          {/* FEATURE 2 */}

          <article className="landing-feature-card">

            <div className="feature-icon">
              AI
            </div>


            <h3>
              Intelligent Prediction
            </h3>


            <p>

              Waiting time is estimated using
              machine-learning prediction and
              Bayesian waiting-state analysis.

            </p>

          </article>


          {/* FEATURE 3 */}

          <article className="landing-feature-card">

            <div className="feature-icon">
              LIVE
            </div>


            <h3>
              Real-Time Queue
            </h3>


            <p>

              Queue information can be refreshed
              continuously so patients can follow
              their current position.

            </p>

          </article>


        </div>

      </section>


      {/* =====================================================
          WORKFLOW
          ===================================================== */}

      <section className="landing-workflow">


        <div className="landing-section-heading">

          <p className="eyebrow">
            PATIENT WORKFLOW
          </p>


          <h2>
            From hospital entry to consultation.
          </h2>

        </div>


        <div className="workflow-grid">


          {/* 01 */}

          <article className="workflow-card">

            <span>
              01
            </span>


            <h3>
              Patient Login
            </h3>


            <p>

              The patient logs into the
              Care+ hospital website.

            </p>

          </article>


          {/* 02 */}

          <article className="workflow-card">

            <span>
              02
            </span>


            <h3>
              Nurse Assessment
            </h3>


            <p>

              The nurse records the patient's
              initial checkup information.

            </p>

          </article>


          {/* 03 */}

          <article className="workflow-card">

            <span>
              03
            </span>


            <h3>
              Queue Registration
            </h3>


            <p>

              Reception adds the patient to
              the appropriate department queue.

            </p>

          </article>


          {/* 04 */}

          <article className="workflow-card">

            <span>
              04
            </span>


            <h3>
              QR Tracking
            </h3>


            <p>

              The patient scans the QR and
              privately views their queue status.

            </p>

          </article>


        </div>

      </section>


      {/* =====================================================
          CTA
          ===================================================== */}

      <section className="landing-cta">


        <div>

          <p className="eyebrow">
            CARE<span>+</span>
          </p>


          <h2>
            Make waiting more predictable.
          </h2>


          <p>

            Start your secure patient journey
            with Care+.

          </p>

        </div>


        <button
          className="button primary landing-cta-button"
          onClick={() => navigate("/login")}
        >
          Login
        </button>


      </section>

    </main>

  );

}