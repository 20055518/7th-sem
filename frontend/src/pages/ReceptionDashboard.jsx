import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppNav from "../components/AppNav";
import {
  getReceptionQueue,
  generateQueueQr,
  logout,
} from "../api";

import "./ReceptionDashboard.css";
import "./Receptionresponsive.css";


/* =========================================================
   HELPERS
========================================================= */

function normalizeStatus(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") {
    value = value?.value ?? value?.name ?? "";
  }
  return String(value)
    .trim()
    .toLowerCase()
    .replaceAll("_", "-")
    .replaceAll(" ", "-");
}


function formatStatus(value) {
  if (!value) return "Waiting";
  if (typeof value === "object") {
    value = value?.value ?? value?.name ?? "";
  }
  if (!value) return "Waiting";
  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}


function extractRisk(patient) {
  /*
   * Reception should use the nurse-assigned triage priority as the
   * patient risk indicator. This value is written during the nurse
   * assessment and carried into the queue entry as `priority`.
   *
   * Do NOT prefer the ML risk_level here because Reception is using
   * the nurse's clinical triage decision to manage QR distribution.
   */
  return (
    patient?.priority ??
    patient?.assessment?.priority ??
    patient?.risk_level ??
    patient?.riskLevel ??
    patient?.risk ??
    patient?.assessment?.risk_level ??
    patient?.assessment?.risk
  );
}


function displayRisk(value) {
  if (!value) return "Loading";
  if (typeof value === "object") return "Loading";
  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}


function getRiskClass(value) {
  switch (normalizeStatus(value)) {
    case "low":
    case "normal":
      return "risk-low";
    case "medium":
      return "risk-medium";
    case "high":
      return "risk-high";
    case "urgent":
      return "risk-urgent";
    default:
      return "risk-loading";
  }
}


/* =========================================================
   QR / QUEUE ACCESS DISPLAY
   ========================================================= */

function getQrDisplayState(normalizedStatus, verified) {
  /* A verified patient is already authorized for the doctor queue. */
  if (verified) {
    return {
      type: "scanned",
      label: "✓ Scanned",
    };
  }

  /*
   * Normal state: the patient completed triage and is waiting
   * for Reception to display the QR.
   */
  if (normalizedStatus === "waiting-for-reception") {
    return {
      type: "show-qr",
      label: "Generate QR",
    };
  }

  /*
   * Legacy/repair state: an old record may still say WAITING while
   * queue_access_verified is false. It is not allowed in the doctor
   * queue. We expose the QR action so the backend can normalize the
   * record back to WAITING_FOR_RECEPTION and issue its QR.
   */
  if (normalizedStatus === "waiting") {
    return {
      type: "show-qr",
      label: "Generate QR",
    };
  }

  if (normalizedStatus === "waiting-for-triage") {
    return {
      type: "info",
      label: "Awaiting triage",
    };
  }

  /* CALLED / IN_CONSULTATION / COMPLETED should always be verified. */
  if (
    normalizedStatus === "called" ||
    normalizedStatus === "in-consultation" ||
    normalizedStatus === "completed"
  ) {
    return {
      type: "blocked",
      label: "QR verification required",
    };
  }

  return {
    type: "info",
    label: "Not available",
  };
}


/* =========================================================
   RECEPTION DASHBOARD
========================================================= */

export default function ReceptionDashboard() {
  const navigate = useNavigate();

  /* Default to "all" so every patient needing QR is visible */
  const [department, setDepartment] = useState("all");

  const [queue, setQueue] = useState([]);

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState("");

  /* QR currently displayed */
  const [qrData, setQrData] = useState(null);

  /* Patient whose QR is displayed */
  const [qrPatient, setQrPatient] = useState(null);

  /* Token currently generating a QR. Only that row is disabled. */
  const [qrLoadingToken, setQrLoadingToken] = useState(null);

  /* QR panel location for automatic scroll */
  const qrSectionRef = useRef(null);


  /* =========================================================
     LOAD RECEPTION QUEUE
  ========================================================= */

  async function loadQueue(showError = true) {
    try {
      const data = await getReceptionQueue(department);

      const list = Array.isArray(data)
  ? data
  : Array.isArray(data?.queue)
    ? data.queue
    : Array.isArray(data?.patients)
      ? data.patients
      : [];


      const activeList = list.filter((patient) => {
        const status = normalizeStatus(patient?.status);

        return status !== "completed";
      });

      const sortedList = [...activeList].sort((a, b) => {
        const aScanned =
          a?.queue_access_verified === true;

        const bScanned =
          b?.queue_access_verified === true;

        // Unscanned patients first
        if (aScanned !== bScanned) {
          return aScanned ? 1 : -1;
        }

        // Keep existing order within each group
        return 0;
      });

      setQueue(sortedList);

      if (showError) {
        setError("");
      }

    } catch (err) {
      console.error("Reception queue error:", err);

      if (err?.status === 401) {
        logout();
        navigate("/login", { replace: true });
        return;
      }

      if (showError) {
        setError(
          err?.message ||
          "Unable to load reception queue."
        );
      }

    } finally {
      setLoading(false);
    }
  }


  /* =========================================================
     INITIAL LOAD + LIVE POLLING
  ========================================================= */

  useEffect(() => {
    setLoading(true);
    loadQueue();

    const interval = setInterval(() => {
      loadQueue(false);
    }, 3000);

    return () => {
      clearInterval(interval);
    };

  }, [department]);


  /* =========================================================
     CLOSE QR AFTER SUCCESSFUL PATIENT SCAN
  ========================================================= */

  useEffect(() => {
    if (!qrPatient) return;

    const qrToken =
      qrPatient?.token_number ??
      qrPatient?.token;

    const updatedPatient = queue.find((patient) => {
      const patientToken =
        patient?.token_number ??
        patient?.token;

      return String(patientToken) === String(qrToken);
    });

    if (updatedPatient?.queue_access_verified === true) {
      setQrData(null);
      setQrPatient(null);
      setQrLoadingToken(null);
    }
  }, [queue, qrPatient]);


  /* Automatically bring the generated QR into view */
  useEffect(() => {
    if (!qrData?.qr_image_data || !qrSectionRef.current) {
      return;
    }

    requestAnimationFrame(() => {
      qrSectionRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  }, [qrData]);


  /* =========================================================
     SHOW PATIENT QR
  ========================================================= */

  async function handleShowQr(patient) {
    const status = normalizeStatus(patient?.status);
    const verified = patient?.queue_access_verified === true;

    if (verified) {
      return;
    }

    /*
     * WAITING_FOR_RECEPTION is the normal state.
     * WAITING + unverified is a legacy/inconsistent record and is
     * repaired by the QR generation endpoint before issuing the QR.
     */
    if (
      status !== "waiting-for-reception" &&
      status !== "waiting"
    ) {
      return;
    }

    const token = patient?.token_number ?? patient?.token;

    if (!token) {
      setError("Patient token is missing.");
      return;
    }

    try {
      setQrLoadingToken(token);
      setError("");

      const patientDepartment = patient?.department || department;

      const data = await generateQueueQr(patientDepartment, token);

      setQrData(data);
      setQrPatient(patient);

    } catch (err) {
      console.error("Generate reception QR error:", err);
      setError(err?.message || "Unable to generate the patient QR.");
      setQrData(null);
      setQrPatient(null);

    } finally {
      setQrLoadingToken(null);
    }
  }


  /* =========================================================
     CLOSE QR
  ========================================================= */

  function closeQr() {
    setQrData(null);
    setQrPatient(null);
    setQrLoadingToken(null);
  }


  /* =========================================================
     RENDER
  ========================================================= */

  return (
    <main className="reception-dashboard">

      <AppNav />

      <header className="page-header">
        <div>
          <p className="eyebrow">RECEPTION DASHBOARD</p>
          <h1>Queue Management</h1>
          <p className="muted">
            Show each patient their reception QR.
            The patient scans it to enter the doctor queue.
          </p>
        </div>
        <span className="live-pill">● Live</span>
      </header>

      <section className="reception-toolbar">
        <div className="department-control">
          <p className="card-label">Department</p>
          <select
            className="department-select"
            value={department}
            onChange={(event) => {
              setDepartment(event.target.value);
              closeQr();
              setError("");
            }}
          >
            <option value="all">All Departments</option>
            <option value="General">General</option>
            <option value="Cardiology">Cardiology</option>
            <option value="Orthopedics">Orthopedics</option>
            <option value="Pediatrics">Pediatrics</option>
            <option value="Neurology">Neurology</option>
          </select>
        </div>
      </section>

      {error && (
        <div className="alert danger">{error}</div>
      )}

      <section className="queue-section">

        <div className="section-heading">
          <div>
            <p className="eyebrow">LIVE QUEUE</p>
            <h2>
              {department === "all" ? "All" : department}{" "}
              Patients
            </h2>
          </div>
          <div className="queue-count">
            {queue.length}
            <span>patient{queue.length === 1 ? "" : "s"}</span>
          </div>
        </div>

        {loading ? (

          <div className="loading-card">Loading queue...</div>

        ) : queue.length === 0 ? (

          <div className="empty-card">
            <h2>No patients in queue</h2>
            <p className="muted">
              There are currently no patients in this department.
            </p>
          </div>

        ) : (

          <div className="queue-table-wrap">
            <table className="queue-table">
              <thead>
                <tr>
                  <th>Token</th>
                  <th>Position</th>
                  <th>Patient</th>
                  <th>Doctor</th>
                  <th>Status</th>
                  <th>Risk</th>
                  <th>QR</th>
                </tr>
              </thead>
              <tbody>
                {queue.map((patient, index) => {

                  const token =
                    patient?.token_number ??
                    patient?.token ??
                    index + 1;

                  const position =
                    patient?.position ??
                    index + 1;

                  const status =
                    patient?.status ??
                    "waiting";

                  const normalized = normalizeStatus(status);

                  const verified =
                    patient?.queue_access_verified === true;

                  const risk = extractRisk(patient);

                  return (
                    <tr
                      key={
                        patient?._id ??
                        patient?.id ??
                        `row-${department}-${token}`
                      }
                    >

                      <td>
                        <strong className="token-value">
                          #{String(token).padStart(3, "0")}
                        </strong>
                      </td>

                      <td>
                        <span className="position-value">
                          {position}
                        </span>
                      </td>

                      <td>
                        <span className="patient-email">
                          {patient?.patient_email ??
                            patient?.email ??
                            "—"}
                        </span>
                      </td>

                      <td>
                        <span className="doctor-email">
                          {patient?.doctor_email ?? "—"}
                        </span>
                      </td>

                      <td>
                        <span className={`status-badge status-${normalized}`}>
                          {formatStatus(status)}
                        </span>
                      </td>

                      <td>
                        <span className={`risk-badge ${getRiskClass(risk)}`}>
                          {displayRisk(risk)}
                        </span>
                      </td>

                      <td>
                        {(() => {
                          const qrState = getQrDisplayState(
                            normalized,
                            verified,
                          );

                          if (qrState.type === "scanned") {
                            return (
                              <span className="qr-scan-status qr-scan-status--scanned">
                                ✓ Scanned
                              </span>
                            );
                          }

                          if (qrState.type === "show-qr") {
                            const patientToken =
                              patient?.token_number ??
                              patient?.token;

                            const isGenerating =
                              String(qrLoadingToken) ===
                              String(patientToken);

                            return (
                              <button
                                type="button"
                                className="mini-button"
                                onClick={() => handleShowQr(patient)}
                                disabled={isGenerating}
                              >
                                {isGenerating ? "Generating..." : "Generate QR"}
                              </button>
                            );
                          }

                          return (
                            <span
                              className={
                                qrState.type === "blocked"
                                  ? "qr-access-status qr-access-status--blocked"
                                  : "muted"
                              }
                            >
                              {qrState.label}
                            </span>
                          );
                        })()}
                      </td>

                    </tr>
                  );

                })}
              </tbody>
            </table>
          </div>

        )}

      </section>

      {qrData?.qr_image_data && qrPatient && (
        <section
          ref={qrSectionRef}
          className="reception-qr-card"
          aria-label="Reception QR"
        >
          <p className="eyebrow">RECEPTION QR</p>

          <h2>
            Token #
            {String(
              qrPatient?.token_number ??
              qrPatient?.token ??
              ""
            ).padStart(3, "0")}
          </h2>

          <p className="muted">
            Ask this patient to scan the QR using their phone.
            <br />
            They will enter the doctor queue after verification.
          </p>

          <img
            src={qrData.qr_image_data}
            alt="Reception queue QR"
          />

          {qrData?.manual_code && (
            <div className="manual-code-box">
              <span className="manual-code-label">
                6-Digit Backup Code
              </span>

              <strong className="manual-code-value">
                {qrData.manual_code}
              </strong>

              <p className="manual-code-help">
                Use this code when the QR camera does not scan.
              </p>
            </div>
          )}

          {qrData?.expires_at && (
            <p className="reception-qr-expiry">
              ⏱ Expires at{" "}
              {new Date(qrData.expires_at).toLocaleTimeString()}
            </p>
          )}

          <button
            type="button"
            className="button secondary reception-qr-close"
            onClick={closeQr}
          >
            Close QR
          </button>
        </section>
      )}

    </main>
  );
}
