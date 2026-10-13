import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import AppNav from "../components/AppNav";
import "./PatientDashboard.css";
import "./PatientDashboardResponsive.css";
import backgroundVideo from "../assets/background.mp4";

import {
  getMyQueue,
  getPublicDoctorQueue,
  verifyQr,
  logout,
  getPatientMedicalHistory,
  getFcmPreferences,
  saveFcmToken,
} from "../api";
import {
  requestNotificationPermissionAndGetToken,
  onForegroundMessageListener,
} from "../firebase/firebase";
import QRScanner from "../components/QRScanner";



export default function PatientDashboard() {
  const navigate = useNavigate();

  const [queue, setQueue] = useState(null);
  const [publicQueue, setPublicQueue] = useState([]);
  const [publicQueueError, setPublicQueueError] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [scanning, setScanning] = useState(false);
  const [scanLoading, setScanLoading] = useState(false);
  const [manualCode, setManualCode] = useState("");
  const [manualCodeLoading, setManualCodeLoading] = useState(false);

  // Past Medical Records
  const [pastRecords, setPastRecords] = useState([]);
  const [pastRecordsLoading, setPastRecordsLoading] = useState(false);
  const [pastRecordsError, setPastRecordsError] = useState("");

  // FCM Web Push Notifications
  const [notificationsEnabled, setNotificationsEnabled] = useState(false);
  const [notificationLoading, setNotificationLoading] = useState(false);
  const [notificationStatusMsg, setNotificationStatusMsg] = useState("");


  async function loadQueue() {
    /*
     * The backend is the source of truth.
     * We must fetch the current queue record first and then
     * inspect queue_access_verified for THIS queue entry.
     */
    try {
      const data = await getMyQueue();

      setQueue(data);
      setError("");

      // Load the public live queue only after this queue has been
      // verified by the official reception QR.
      if (
        data?.queue_access_verified === true &&
        data?.department &&
        data?.doctor_email
      ) {
        try {
          const publicData = await getPublicDoctorQueue(
            data.department,
            data.doctor_email,
          );

          const liveQueue = Array.isArray(publicData)
            ? publicData
            : publicData?.queue || [];

          setPublicQueue(liveQueue);
          setPublicQueueError("");
        } catch (publicError) {
          console.error("Public queue error:", publicError);
          setPublicQueue([]);
          setPublicQueueError(
            publicError?.message ||
              "Unable to load the live queue.",
          );
        }
      } else {
        setPublicQueue([]);
        setPublicQueueError("");
      }
    } catch (err) {
      const message =
        err?.message || "";

      if (
        err?.status === 401 ||
        message.includes("401") ||
        message
          .toLowerCase()
          .includes(
            "not authenticated",
          )
      ) {
        logout();
        navigate("/login", { replace: true });
        return;
      }


      if (
        err?.status === 404 ||
        message.includes("404") ||
        message
          .toLowerCase()
          .includes(
            "no queue entry found",
          )
      ) {
        setQueue(null);
        setPublicQueue([]);
        setPublicQueueError("");
        setError("");
        return;
      }


      setError(message);
    } finally {
      setLoading(false);
    }
  }
  async function handleReceptionQrScan(scannedValue) {
    if (scanLoading || !scanning) return;

    try {
      setScanLoading(true);
      setScanning(false);
      setError("");

      await verifyQr(scannedValue);
      await loadQueue();
    } catch (err) {
      console.error("Patient QR verification error:", err);
      setError(err?.message || "Unable to verify the reception QR.");
      setScanning(true);
    } finally {
      setScanLoading(false);
    }
  }

  async function handleManualCodeSubmit(event) {
    event.preventDefault();

    const cleanCode = manualCode.trim();

    if (
      manualCodeLoading ||
      !/^[0-9]{6}$/.test(cleanCode)
    ) {
      setError("Please enter the 6-digit backup code.");
      return;
    }

    try {
      setManualCodeLoading(true);
      setError("");
      setScanning(false);

      await verifyQr({ manual_code: cleanCode });
      setManualCode("");
      await loadQueue();
    } catch (err) {
      console.error("Manual QR verification error:", err);
      setError(err?.message || "Unable to verify the backup code.");
    } finally {
      setManualCodeLoading(false);
    }
  }

  async function loadPastRecords() {
    try {
      setPastRecordsLoading(true);
      setPastRecordsError("");
      const res = await getPatientMedicalHistory();
      setPastRecords(Array.isArray(res?.records) ? res.records : []);
    } catch (err) {
      console.error("Past records error:", err);
      setPastRecordsError("Unable to load past medical records.");
    } finally {
      setPastRecordsLoading(false);
    }
  }

  // Load past medical records when conditions are met:
  // - Patient has no active queue (returning visit)
  // - OR queue status is beyond waiting_for_triage (i.e. nurse assessment is completed)
  useEffect(() => {
    if (!loading) {
      const nurseAssessmentDone = queue && queue.status !== "waiting_for_triage";
      const returningVisit = !queue;
      if (nurseAssessmentDone || returningVisit) {
        loadPastRecords();
      }
    }
  }, [loading, queue?.status]);

  // Initialize FCM preferences and foreground message listener
  useEffect(() => {
    async function checkNotificationStatus() {
      try {
        const prefs = await getFcmPreferences();
        if (prefs?.notifications_enabled && prefs?.fcm_token_registered) {
          setNotificationsEnabled(true);
        }
      } catch (err) {
        console.debug("Could not fetch FCM preferences:", err);
      }
    }
    checkNotificationStatus();

    // Listen to foreground alerts
    const unsubscribe = onForegroundMessageListener((payload) => {
      console.log("Foreground notification received:", payload);
      const title = payload.notification?.title || payload.data?.title || "Care+ Alert";
      const body = payload.notification?.body || payload.data?.body || "Queue updated";
      setNotificationStatusMsg(`🔔 ${title}: ${body}`);
      // Refresh queue status immediately
      loadQueue();
      setTimeout(() => setNotificationStatusMsg(""), 7000);
    });

    return () => {
      if (typeof unsubscribe === "function") unsubscribe();
    };
  }, []);

  async function handleToggleNotifications() {
    if (notificationLoading) return;
    try {
      setNotificationLoading(true);
      setNotificationStatusMsg("");

      if (notificationsEnabled) {
        // Disable notifications
        await saveFcmToken("", false);
        setNotificationsEnabled(false);
        setNotificationStatusMsg("Push notifications disabled.");
        setTimeout(() => setNotificationStatusMsg(""), 4000);
        return;
      }

      // Enable notifications: Request browser permission and obtain FCM token
      const token = await requestNotificationPermissionAndGetToken();
      if (!token) {
        setNotificationStatusMsg("Permission not granted or browser does not support push notifications.");
        setTimeout(() => setNotificationStatusMsg(""), 5000);
        return;
      }

      await saveFcmToken(token, true);
      setNotificationsEnabled(true);
      setNotificationStatusMsg("✓ Queue push notifications enabled! You will receive live alerts.");
      setTimeout(() => setNotificationStatusMsg(""), 5000);
    } catch (err) {
      console.error("Error updating notifications:", err);
      setNotificationStatusMsg("Failed to configure push notifications.");
      setTimeout(() => setNotificationStatusMsg(""), 5000);
    } finally {
      setNotificationLoading(false);
    }
  }

  useEffect(() => {
    loadQueue();

    const interval =
      setInterval(
        loadQueue,
        3000,
      );

    return () => {
      clearInterval(interval);
    };
  }, []);


  if (loading) {
    return (
      <main className="patient-dashboard">
        <DashboardBackground />
        <AppNav />

        <div className="loading-card">
          Loading...
        </div>
      </main>
    );
  }


  /*
   * ==========================================================
   * NO ACTIVE QUEUE
   * ==========================================================
   */

  if (!queue) {
    return (
      <main className="patient-dashboard">
        <DashboardBackground />
        <AppNav />

        <header className="page-header">
          <div>
            <p className="eyebrow">
              PATIENT DASHBOARD
            </p>

            <h1>
              Your Queue
            </h1>
          </div>
        </header>

        {error && (
          <div className="alert danger">
            {error}
          </div>
        )}

        <section className="empty-card">
          <p className="eyebrow">
            QUEUE
          </p>

          <h2>
            No active queue
          </h2>

          <p className="muted">
            Join a department queue to start your hospital journey.
          </p>

          <div className="dashboard-actions">
            <button
              className="button primary"
              onClick={() => navigate("/join-queue")}
            >
              Join Queue
            </button>
          </div>
        </section>
        <PastMedicalRecordsSection
          records={pastRecords}
          loading={pastRecordsLoading}
          error={pastRecordsError}
        />
      </main>
    );
  }


  /*
   * ==========================================================
   * QR NOT VERIFIED
   * ==========================================================
   */

  const queueAccessVerified = queue.queue_access_verified === true;

  if (!queueAccessVerified) {
    const waitingForTriage = queue?.status === "waiting_for_triage";
    const waitingForReception = queue?.status === "waiting_for_reception";

    return (
      <main className="patient-dashboard">
        <DashboardBackground />
        <AppNav />

        <header className="page-header">
          <div>
            <p className="eyebrow">PATIENT DASHBOARD</p>
            <h1>Your Queue</h1>
          </div>

          <div className="header-badge-actions">
            <button
              type="button"
              className={`notification-toggle-button ${notificationsEnabled ? "active" : ""}`}
              onClick={handleToggleNotifications}
              disabled={notificationLoading}
              title={notificationsEnabled ? "Web Push Notifications active (Click to disable)" : "Enable Web Push Notifications"}
              aria-label="Toggle Queue Push Notifications"
            >
              {notificationLoading ? (
                <span className="notif-spinner">...</span>
              ) : notificationsEnabled ? (
                <>
                  <span className="notif-icon">🔔</span>
                  <span className="notif-text">Alerts On</span>
                </>
              ) : (
                <>
                  <span className="notif-icon">🔕</span>
                  <span className="notif-text">Enable Alerts</span>
                </>
              )}
            </button>
          </div>
        </header>

        {notificationStatusMsg && (
          <div className="alert notification-banner">
            {notificationStatusMsg}
          </div>
        )}

        {error && <div className="alert danger">{error}</div>}

        <section className="empty-card">
          <p className="eyebrow">QUEUE ACCESS</p>
          <h2>
            {waitingForTriage
              ? "Waiting for Nurse Triage"
              : waitingForReception
                ? "Waiting for Reception QR"
                : "Waiting for Queue Verification"}
          </h2>

          <p className="muted">
            {waitingForTriage
              ? "Please wait while the nurse completes your assessment."
              : waitingForReception
                ? "Go to reception. Reception will display a QR code for your token. Scan that QR code with your phone to enter the doctor queue."
                : "Please wait for reception verification."}
          </p>

          {waitingForReception && !scanning && (
            <div className="dashboard-actions reception-scan-actions">
              <button
                type="button"
                className="button primary reception-scan-button"
                onClick={() => {
                  setError("");
                  setScanning(true);
                }}
              >
                Scan Reception QR
              </button>
            </div>
          )}

          {scanning && (
            <div className="scanner-card reception-scanner-card">
              <div className="reception-scanner-viewport">
                <QRScanner
                  onScan={handleReceptionQrScan}
                  onError={(message) => setError(message)}
                />
              </div>

              <div className="dashboard-actions reception-scan-actions">
                <button
                  type="button"
                  className="button secondary reception-cancel-button"
                  onClick={() => setScanning(false)}
                  disabled={scanLoading}
                >
                  Cancel Scan
                </button>
              </div>
            </div>
          )}

          {waitingForReception && (
            <form
              className="manual-qr-form"
              onSubmit={handleManualCodeSubmit}
            >
              <div className="manual-qr-divider">
                <span>OR</span>
              </div>

              <p className="eyebrow">
                BACKUP VERIFICATION
              </p>

              <h3>Enter 6-digit code</h3>

              <p className="muted manual-qr-help">
                Use the 6-digit code shown by Reception if the camera cannot scan the QR code.
              </p>

              <input
                className="manual-qr-input"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                pattern="[0-9]{6}"
                value={manualCode}
                onChange={(event) => {
                  const digitsOnly = event.target.value
                    .replace(/\\D/g, "")
                    .slice(0, 6);
                  setManualCode(digitsOnly);
                }}
                placeholder="000000"
                aria-label="6-digit backup verification code"
              />

              <button
                type="submit"
                className="button primary manual-qr-submit"
                disabled={manualCodeLoading || manualCode.length !== 6}
              >
                {manualCodeLoading ? "Verifying..." : "Verify Code"}
              </button>
            </form>
          )}

          {scanLoading && (
            <p className="muted verification-progress">
              Verifying QR and adding you to the doctor queue...
            </p>
          )}
        </section>

        {waitingForReception && (
          <PastMedicalRecordsSection
            records={pastRecords}
            loading={pastRecordsLoading}
            error={pastRecordsError}
          />
        )}
    
      </main>
    );
  }

  /*
   * ==========================================================
   * PATIENT QUEUE DATA
   * ==========================================================
   */

  const token =
    queue.token_number ??
    queue.token ??
    "—";


  const ownQueueEntry = publicQueue.find(
    (entry) =>
      Number(entry?.token_number ?? entry?.token) ===
      Number(queue?.token_number ?? queue?.token),
  );

  const position =
    ownQueueEntry?.position ??
    queue.position ??
    "—";


  const status =
    queue.status ??
    "Waiting";


  const risk =
    queue.risk_level ??
    "—";


  const predictedWait =
    queue.predicted_wait_minutes ??
    "—";


  const bayesianWait =
    queue.bayesian_expected_wait_minutes ??
    "—";


  const bayesianState =
    queue.bayesian_state ??
    "—";


  const longProbability =
    queue.probability_long_or_more ??
    0;


  const probabilities = {
    short: queue.probability_short ?? 0,
    moderate: queue.probability_moderate ?? 0,
    long: queue.probability_long ?? 0,
    very_long: queue.probability_very_long ?? 0,
  };


  return (
    <main className="patient-dashboard">

      <DashboardBackground />
      <AppNav />


      <header className="page-header">

        <div>

          <p className="eyebrow">
            PATIENT DASHBOARD
          </p>

          <h1>
            Your Queue
          </h1>

        </div>


        <div className="header-badge-actions">
          <button
            type="button"
            className={`notification-toggle-button ${notificationsEnabled ? "active" : ""}`}
            onClick={handleToggleNotifications}
            disabled={notificationLoading}
            title={notificationsEnabled ? "Web Push Notifications active (Click to disable)" : "Enable Web Push Notifications"}
            aria-label="Toggle Queue Push Notifications"
          >
            {notificationLoading ? (
              <span className="notif-spinner">...</span>
            ) : notificationsEnabled ? (
              <>
                <span className="notif-icon">🔔</span>
                <span className="notif-text">Alerts On</span>
              </>
            ) : (
              <>
                <span className="notif-icon">🔕</span>
                <span className="notif-text">Enable Alerts</span>
              </>
            )}
          </button>

          <span className="live-pill">
            ● Live
          </span>
        </div>

      </header>

      {notificationStatusMsg && (
        <div className="alert notification-banner">
          {notificationStatusMsg}
        </div>
      )}


      {error && (
        <div className="alert danger">
          {error}
        </div>
      )}


      

      {/* ====================================================
          MY QUEUE SUMMARY
          ==================================================== */}

      <section className="patient-summary">

        <article className="token-card">
          <span>
            Token
          </span>

          <strong>
            #{String(token).padStart(
              3,
              "0",
            )}
          </strong>
        </article>


        <article className="summary-card">
          <span>
            Position
          </span>

          <strong>
            {position}
          </strong>
        </article>


        <article className="summary-card">
          <span>
            Status
          </span>

          <strong>
            {status}
          </strong>
        </article>


        <article className="summary-card">
          <span>
            Risk
          </span>

          <strong>
            {risk}
          </strong>
        </article>

      </section>


      {/* ====================================================
          WAITING PREDICTION
          ==================================================== */}

      <section className="prediction-grid">

              {/* 1 — ESTIMATED WAITING TIME */}
              <article className="prediction-main">
                <p className="card-label">
                  Estimated Waiting Time
                </p>

                <strong className="prediction-number">
                  {typeof predictedWait === "number"
                    ? `${predictedWait.toFixed(1)} min`
                    : predictedWait}
                </strong>

                <p className="muted">
                  Expected wait:{" "}
                  {typeof bayesianWait === "number"
                    ? `${bayesianWait.toFixed(1)} min`
                    : bayesianWait}
                </p>
              </article>


              {/* 2 — DOCTOR */}
              <article className="prediction-main">
                <p className="card-label">
                  Doctor
                </p>

                <strong className="doctor-name">
                  {queue.doctor_name ||
                    queue.doctor_email ||
                    "Assigned Doctor"}
                </strong>

                <p className="muted">
                  {queue.department ||
                    "Department not available"}
                </p>
              </article>


              {/* 3 — PREDICTED WAIT RANGE */}
              <article className="prediction-main">
                <p className="card-label">
                  Predicted Wait Range
                </p>

                <strong className="state-text">
                  {bayesianState}
                </strong>

                <p className="muted">
                  Long-or-more probability:{" "}
                  {longProbability}%
                </p>
              </article>

            </section>


      {/* ====================================================
          PUBLIC LIVE QUEUE
          ==================================================== */}

      <section className="public-queue-section">

        <div className="section-heading public-queue-heading">
          <div>
            <p className="eyebrow">
              LIVE QUEUE
            </p>

            <h2>
              {queue.department} Queue
            </h2>

            <p className="public-queue-description">
              Other patients are shown only by queue token.
            </p>
          </div>

          <span className="live-pill">
            ● Live
          </span>
        </div>

        {publicQueueError && (
          <div className="alert danger">
            {publicQueueError}
          </div>
        )}

        {publicQueue.length > 0 ? (
          <div className="public-queue-list">
            {publicQueue.map((entry, index) => {
              const entryToken =
                entry.token_number ?? entry.token;

              const entryPosition =
                entry.position ?? index + 1;

              const ownQueue =
                Number(entryToken) === Number(token);

              const entryStatus =
                entry.status ?? "waiting";

              return (
                <article
                  key={`${entryToken}-${entryPosition}-${index}`}
                  className={
                    `public-queue-row${
                      ownQueue
                        ? " own-queue-row"
                        : ""
                    }`
                  }
                >
                  <div className="public-queue-cell">
                    <span className="card-label">
                      TOKEN
                    </span>

                    <strong>
                      #{String(entryToken).padStart(3, "0")}
                    </strong>
                  </div>

                  <div className="public-queue-cell">
                    <span className="card-label">
                      POSITION
                    </span>

                    <strong>
                      {entryPosition}
                    </strong>
                  </div>

                  <div className="public-queue-cell">
                    <span className="card-label">
                      STATUS
                    </span>

                    <span
                      className={`status-badge status-${String(
                        entryStatus,
                      ).toLowerCase()}`}
                    >
                      {String(entryStatus)
                        .replaceAll("_", " ")
                        .replace(/\b\w/g, (char) =>
                          char.toUpperCase(),
                        )}
                    </span>
                  </div>

                  {ownQueue && (
                    <span className="own-label">
                      YOU
                    </span>
                  )}
                </article>
              );
            })}
          </div>
        ) : (
          <div className="public-queue-empty">
            No patients are currently in the queue.
          </div>
        )}

      </section>


      {/* ====================================================
          SMS NOTIFICATION SETTINGS
          ==================================================== */}
      {/* ====================================================
          PAST MEDICAL RECORDS
          ==================================================== */}
      <PastMedicalRecordsSection
        records={pastRecords}
        loading={pastRecordsLoading}
        error={pastRecordsError}
      />

    </main>
  );
}


/* ============================================================
   BACKGROUND VIDEO
   ============================================================ */

function DashboardBackground() {
  return (
    <>
      <video
        className="patient-dashboard-video"
        autoPlay
        muted
        loop
        playsInline
        preload="auto"
        aria-hidden="true"
        onCanPlay={(event) => {
          const video = event.currentTarget;
          if (video.paused) {
            video.play().catch(() => {});
          }
        }}
      >
        <source
          src={backgroundVideo}
          type="video/mp4"
        />
      </video>

      <div
        className="patient-dashboard-video-overlay"
        aria-hidden="true"
      />
    </>
  );
}

/* ============================================================
   PROBABILITY ROW
   ============================================================ */

function ProbabilityRow({
  label,
  value,
}) {
  const numericValue =
    Number(value) || 0;


  return (
    <div className="probability-row">

      <div className="probability-meta">

        <span>
          {label}
        </span>

        <strong>
          {numericValue.toFixed(1)}%
        </strong>

      </div>


      <div className="progress-track">

        <div
          className="progress-fill"
          style={{
            width: `${Math.min(
              Math.max(
                numericValue,
                0,
              ),
              100,
            )}%`,
          }}
        />

      </div>

    </div>
  );
}

/* ============================================================
   PAST MEDICAL RECORDS SECTION
   ============================================================ */

function PastMedicalRecordsSection({ records, loading, error }) {
  // If not loading, and there are no records (new patient), do not display the section
  if (!loading && (!records || records.length === 0)) {
    return null;
  }

  return (
    <section className="past-medical-records-section">
      <div className="section-heading">
        <div>
          <p className="eyebrow">HISTORICAL RECORDS</p>
          <h2>Past Medical Records</h2>
          <p className="muted">Previous completed consultations and medical history.</p>
        </div>
      </div>

      {loading ? (
        <div className="loading-card">
          Loading medical records...
        </div>
      ) : error ? (
        <div className="alert danger">
          {error}
        </div>
      ) : (
        <div className="past-records-list">
          {records.map((record, index) => (
            <article key={record.record_id || index} className="past-record-card">
              <div className="past-record-header">
                <span className="past-record-badge">PAST MEDICAL RECORD</span>
                <span className="past-record-date">{record.date || "Completed Visit"}</span>
              </div>

              <div className="past-record-meta-row">
                <div>
                  <span className="meta-label">Doctor:</span>
                  <strong>{record.doctor_name || record.doctor_email || "Assigned Doctor"}</strong>
                </div>
                <div>
                  <span className="meta-label">Department:</span>
                  <strong>{record.department || "General"}</strong>
                </div>
              </div>

              <div className="past-record-field">
                <span className="field-title">Diagnosis</span>
                <p>{record.diagnosis || "No diagnosis recorded."}</p>
              </div>

              {record.consultation_notes && (
                <div className="past-record-field">
                  <span className="field-title">Consultation Notes</span>
                  <p>{record.consultation_notes}</p>
                </div>
              )}

              {record.prescription && (
                <div className="past-record-field">
                  <span className="field-title">Prescription</span>
                  <p>{record.prescription}</p>
                </div>
              )}

              {record.treatment_advice && (
                <div className="past-record-field">
                  <span className="field-title">Treatment / Advice</span>
                  <p>{record.treatment_advice}</p>
                </div>
              )}

              {record.nurse_assessment && (
                <div className="past-record-nurse-summary">
                  <span className="nurse-summary-title">Nurse Assessment Summary</span>
                  <div className="nurse-summary-details">
                    <div>
                      <span className="sub-label">Priority:</span>
                      <strong>{String(record.nurse_assessment.priority || "Normal").toUpperCase()}</strong>
                    </div>
                    {record.nurse_assessment.symptoms && (
                      <div>
                        <span className="sub-label">Symptoms:</span>
                        <p>{record.nurse_assessment.symptoms}</p>
                      </div>
                    )}
                    {record.nurse_assessment.nurse_notes && (
                      <div>
                        <span className="sub-label">Nurse Notes:</span>
                        <p>{record.nurse_assessment.nurse_notes}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

