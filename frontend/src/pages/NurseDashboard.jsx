import { useEffect, useLayoutEffect, useRef, useState } from "react";
import AppNav from "../components/AppNav";
import {
  getNursePatients,
  createNurseAssessment,
  getNursePatientMedicalHistory,
} from "../api";

import "./NurseDashboard.css";
import "./Nurseresponsive.css";

export default function NurseDashboard() {
  const [patients, setPatients] = useState([]);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const assessmentRef = useRef(null);

  // Past Medical Records Modal State
  const [historyModalPatient, setHistoryModalPatient] = useState(null);
  const [historyRecords, setHistoryRecords] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");

  async function openHistoryModal(patient) {
    setHistoryModalPatient(patient);
    setHistoryRecords([]);
    setHistoryError("");
    setHistoryLoading(true);

    try {
      const idToLookup = patient.token_number || patient.patient_email;
      const res = await getNursePatientMedicalHistory(idToLookup);
      setHistoryRecords(Array.isArray(res?.records) ? res.records : []);
    } catch (err) {
      console.error("Nurse past records error:", err);
      setHistoryError("Unable to load past medical records.");
    } finally {
      setHistoryLoading(false);
    }
  }

  function closeHistoryModal() {
    setHistoryModalPatient(null);
    setHistoryRecords([]);
    setHistoryError("");
  }

  // ==========================================================
  // LOAD PATIENTS
  // ==========================================================
  async function loadPatients() {
    try {
      setLoading(true);
      setError("");

      const data = await getNursePatients();

      setPatients(
        Array.isArray(data)
          ? data
          : data?.patients || []
      );
    } catch (err) {
      console.error("Nurse patients error:", err);
      setError(
        err?.message || "Unable to load patients."
      );
    } finally {
      setLoading(false);
    }
  }

  // ==========================================================
  // INITIAL LOAD (manual refresh via the ↻ button in the header)
  // ==========================================================
  useEffect(() => {
    loadPatients();
  }, []);

  // ==========================================================
  // OPEN PATIENT
  // ==========================================================
  function openPatient(patient) {
    setSelectedPatient(patient);
    setError("");
    setSuccess("");
    setFieldErrors({});
  }

  // ==========================================================
  // CLOSE PATIENT
  // ==========================================================
  function closePatient() {
    setSelectedPatient(null);
    setError("");
    setSuccess("");
    setFieldErrors({});
  }

  // Automatically scroll to the assessment form after clicking Assess.
  useLayoutEffect(() => {
    if (!selectedPatient || !assessmentRef.current) {
      return;
    }

    const frame = window.requestAnimationFrame(() => {
      const element = assessmentRef.current;
      if (!element) {
        return;
      }

      const navbarOffset = 90;
      const targetY =
        window.scrollY +
        element.getBoundingClientRect().top -
        navbarOffset;

      window.scrollTo({
        top: Math.max(0, targetY),
        behavior: "smooth",
      });
    });

    return () => {
      window.cancelAnimationFrame(frame);
    };
  }, [selectedPatient]);

  // ==========================================================
  // CLEAR ONE FIELD ERROR
  // ==========================================================
  function clearFieldError(fieldName) {
    setFieldErrors((current) => {
      if (!current[fieldName]) {
        return current;
      }

      const next = { ...current };
      delete next[fieldName];
      return next;
    });
  }

  // ==========================================================
  // NUMBER PARSER
  // ==========================================================
  function parseNumber(value) {
    const text = String(value ?? "").trim();

    if (!text) {
      return null;
    }

    const number = Number(text);
    return Number.isFinite(number)
      ? number
      : NaN;
  }

  // ==========================================================
  // SUBMIT ASSESSMENT
  // ==========================================================
  async function handleAssessmentSubmit(event) {
    event.preventDefault();

    setError("");
    setSuccess("");
    setFieldErrors({});
    setSaving(true);

    const form = new FormData(event.currentTarget);

    const temperature = parseNumber(
      form.get("temperature")
    );
    const pulse = parseNumber(
      form.get("pulse")
    );
    const systolic = parseNumber(
      form.get("systolic_bp")
    );
    const diastolic = parseNumber(
      form.get("diastolic_bp")
    );
    const spo2 = parseNumber(
      form.get("spo2")
    );
    const priority = String(
      form.get("priority") || "normal"
    );

    const validationErrors = {};

    // --------------------------------------------------------
    // TEMPERATURE: Backend expects Celsius 25-45
    // --------------------------------------------------------
    if (temperature === null || Number.isNaN(temperature)) {
      validationErrors.temperature =
        "Temperature is required.";
    } else if (temperature < 25 || temperature > 45) {
      validationErrors.temperature =
        "Temperature must be between 25°C and 45°C.";
    }

    // --------------------------------------------------------
    // PULSE: 20-250 bpm
    // --------------------------------------------------------
    if (pulse === null || Number.isNaN(pulse)) {
      validationErrors.pulse =
        "Pulse is required.";
    } else if (pulse < 20 || pulse > 250) {
      validationErrors.pulse =
        "Pulse must be between 20 and 250 bpm.";
    }

    // --------------------------------------------------------
    // SYSTOLIC BP: 50-250 mmHg
    // --------------------------------------------------------
    if (systolic === null || Number.isNaN(systolic)) {
      validationErrors.systolic_bp =
        "Systolic BP is required.";
    } else if (systolic < 50 || systolic > 250) {
      validationErrors.systolic_bp =
        "Systolic BP must be between 50 and 250 mmHg.";
    }

    // --------------------------------------------------------
    // DIASTOLIC BP: 30-150 mmHg
    // --------------------------------------------------------
    if (diastolic === null || Number.isNaN(diastolic)) {
      validationErrors.diastolic_bp =
        "Diastolic BP is required.";
    } else if (diastolic < 30 || diastolic > 150) {
      validationErrors.diastolic_bp =
        "Diastolic BP must be between 30 and 150 mmHg.";
    }

    // --------------------------------------------------------
    // SPO2: 50-100%
    // --------------------------------------------------------
    if (spo2 === null || Number.isNaN(spo2)) {
      validationErrors.spo2 =
        "Oxygen saturation is required.";
    } else if (spo2 < 50 || spo2 > 100) {
      validationErrors.spo2 =
        "Oxygen saturation must be between 50% and 100%.";
    }

    if (Object.keys(validationErrors).length > 0) {
      setFieldErrors(validationErrors);
      setSaving(false);
      return;
    }

    try {
      const assessment = {
        patient_email: selectedPatient.patient_email,
        department: selectedPatient.department,
        doctor_email:
          selectedPatient.doctor_email || null,
        temperature,
        pulse,
        systolic_bp: systolic,
        diastolic_bp: diastolic,
        spo2,
        symptoms:
          String(form.get("symptoms") || "").trim() || null,
        nurse_notes:
          String(form.get("nurse_notes") || "").trim() || null,
        priority,
      };

      await createNurseAssessment(assessment);

      setSuccess(
        `Assessment completed for token #${String(
          selectedPatient.token_number
        ).padStart(3, "0")}. Patient moved to reception for QR verification.`
      );

      setSelectedPatient(null);
      setFieldErrors({});
      await loadPatients();
    } catch (err) {
      console.error("Nurse assessment error:", err);
      setError(
        err?.message || "Unable to save assessment."
      );
    } finally {
      setSaving(false);
    }
  }

  // ==========================================================
  // RENDER
  // ==========================================================
  return (
    <main className="dashboard-page nurse-dashboard">
      <AppNav />

      {/* ====================================================
          HEADER
          ==================================================== */}
      <section className="page-header">
        <div>
          <p className="eyebrow">NURSE DASHBOARD</p>
          <h1>Patient Assessment</h1>
        </div>
        <span className="live-pill">● Live</span>
      </section>

      {/* ====================================================
          GLOBAL ALERTS
          Validation errors are shown beside the fields instead.
          ==================================================== */}
      {error && (
        <div className="alert danger" role="alert">
          {error}
        </div>
      )}

      {success && (
        <div className="alert success" role="status">
          ✓ {success}
        </div>
      )}

      {/* ====================================================
          STATS
          ==================================================== */}
      <section className="doctor-stats nurse-stats">
        <div className="summary-card">
          <span>Waiting Assessment</span>
          <strong>{patients.length}</strong>
        </div>

        <div className="summary-card">
          <span>Department</span>
          <strong>All</strong>
        </div>

        <div className="summary-card">
          <span>Status</span>
          <strong>Active</strong>
        </div>
      </section>

      {/* ====================================================
          PATIENT LIST
          ==================================================== */}
      <section className="queue-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">TRIAGE QUEUE</p>
            <h2>Patients Waiting for Assessment</h2>
          </div>

          <button
            type="button"
            className="mini-button refresh-btn"
            onClick={() => window.location.reload()}
            aria-label="Refresh page"
          >
            ↻ Refresh
          </button>
        </div>

        {loading ? (
          <div className="loading-card">
            Loading patients...
          </div>
        ) : patients.length === 0 ? (
          <div className="empty-card">
            <h2>No patients waiting</h2>
            <p className="muted">
              Patients who join the queue will appear here for initial nurse assessment.
            </p>
          </div>
        ) : (
          <div className="queue-table-wrap">
            <table className="queue-table">
              <thead>
                <tr>
                  <th>Token</th>
                  <th>Patient</th>
                  <th>Department</th>
                  <th>Doctor</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {patients.map((patient) => (
                  <tr
                    key={`${patient.patient_email}-${patient.token_number}`}
                  >
                    <td>
                      <strong className="token-text">
                        #{String(
                          patient.token_number
                        ).padStart(3, "0")}
                      </strong>
                    </td>
                    <td>
                      <span
                        className="patient-email-text"
                        title={patient.patient_email}
                      >
                        {patient.patient_email}
                      </span>
                    </td>
                    <td>{patient.department}</td>
                    <td>
                      {patient.doctor_email ||
                        "Not assigned"}
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                        <button
                          type="button"
                          className="mini-button"
                          onClick={() =>
                            openPatient(patient)
                          }
                        >
                          Assess
                        </button>
                        {patient?.has_past_records && (
                          <button
                            type="button"
                            className="mini-button past-records-btn"
                            onClick={() =>
                              openHistoryModal(patient)
                            }
                          >
                            View Past Records
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ====================================================
          ASSESSMENT
          ==================================================== */}
      {selectedPatient && (
        <section
          ref={assessmentRef}
          className="queue-section nurse-assessment-card"
        >
          <div className="section-heading">
            <div>
              <p className="eyebrow">NURSE ASSESSMENT</p>
              <h2>
                Token #{String(
                  selectedPatient.token_number
                ).padStart(3, "0")}
              </h2>
            </div>

            <button
              type="button"
              className="mini-button close-btn"
              onClick={closePatient}
              disabled={saving}
            >
              Close
            </button>
          </div>

          {/* PATIENT SUMMARY CARDS */}
          <div className="patient-summary nurse-patient-summary">
            <div className="token-card">
              <span className="summary-label">
                Token
              </span>
              <strong className="summary-token">
                #{String(
                  selectedPatient.token_number
                ).padStart(3, "0")}
              </strong>
            </div>

            <div className="summary-card">
              <span className="summary-label">
                Patient Email
              </span>
              <strong
                className="summary-value summary-email"
                title={selectedPatient.patient_email}
              >
                {selectedPatient.patient_email}
              </strong>
            </div>

            <div className="summary-card">
              <span className="summary-label">
                Department
              </span>
              <strong className="summary-value">
                {selectedPatient.department}
              </strong>
            </div>

            <div className="summary-card">
              <span className="summary-label">
                Assigned Doctor
              </span>
              <strong
                className="summary-value summary-email"
                title={
                  selectedPatient.doctor_email ||
                  "Not assigned"
                }
              >
                {selectedPatient.doctor_email ||
                  "Not assigned"}
              </strong>
            </div>
          </div>

          {/* ==================================================
              FORM
              ================================================== */}
          <form
            className="nurse-assessment-form"
            onSubmit={handleAssessmentSubmit}
            noValidate
          >
            <div className="nurse-form-grid">
              {/* TEMPERATURE */}
              <label className="nurse-field">
                <span className="nurse-field-label">
                  Temperature (°C)
                </span>

                <input
                  type="number"
                  step="0.1"
                  min="25"
                  max="45"
                  name="temperature"
                  placeholder="e.g. 37.0"
                  required
                  className={
                    fieldErrors.temperature
                      ? "input-error"
                      : ""
                  }
                  onChange={() =>
                    clearFieldError("temperature")
                  }
                  aria-invalid={Boolean(
                    fieldErrors.temperature
                  )}
                />

                {fieldErrors.temperature && (
                  <span className="field-error">
                    {fieldErrors.temperature}
                  </span>
                )}
              </label>

              {/* PULSE */}
              <label className="nurse-field">
                <span className="nurse-field-label">
                  Pulse (bpm)
                </span>

                <input
                  type="number"
                  min="20"
                  max="250"
                  name="pulse"
                  placeholder="e.g. 72"
                  required
                  className={
                    fieldErrors.pulse
                      ? "input-error"
                      : ""
                  }
                  onChange={() =>
                    clearFieldError("pulse")
                  }
                  aria-invalid={Boolean(
                    fieldErrors.pulse
                  )}
                />

                {fieldErrors.pulse && (
                  <span className="field-error">
                    {fieldErrors.pulse}
                  </span>
                )}
              </label>

              {/* SYSTOLIC BP */}
              <label className="nurse-field">
                <span className="nurse-field-label">
                  Systolic BP (mmHg)
                </span>

                <input
                  type="number"
                  min="50"
                  max="250"
                  name="systolic_bp"
                  placeholder="e.g. 120"
                  required
                  className={
                    fieldErrors.systolic_bp
                      ? "input-error"
                      : ""
                  }
                  onChange={() =>
                    clearFieldError("systolic_bp")
                  }
                  aria-invalid={Boolean(
                    fieldErrors.systolic_bp
                  )}
                />

                {fieldErrors.systolic_bp && (
                  <span className="field-error">
                    {fieldErrors.systolic_bp}
                  </span>
                )}
              </label>

              {/* DIASTOLIC BP */}
              <label className="nurse-field">
                <span className="nurse-field-label">
                  Diastolic BP (mmHg)
                </span>

                <input
                  type="number"
                  min="30"
                  max="150"
                  name="diastolic_bp"
                  placeholder="e.g. 80"
                  required
                  className={
                    fieldErrors.diastolic_bp
                      ? "input-error"
                      : ""
                  }
                  onChange={() =>
                    clearFieldError("diastolic_bp")
                  }
                  aria-invalid={Boolean(
                    fieldErrors.diastolic_bp
                  )}
                />

                {fieldErrors.diastolic_bp && (
                  <span className="field-error">
                    {fieldErrors.diastolic_bp}
                  </span>
                )}
              </label>

              {/* OXYGEN SATURATION */}
              <label className="nurse-field">
                <span className="nurse-field-label">
                  Oxygen Saturation (%)
                </span>

                <input
                  type="number"
                  step="0.1"
                  min="50"
                  max="100"
                  name="spo2"
                  placeholder="e.g. 98"
                  required
                  className={
                    fieldErrors.spo2
                      ? "input-error"
                      : ""
                  }
                  onChange={() =>
                    clearFieldError("spo2")
                  }
                  aria-invalid={Boolean(
                    fieldErrors.spo2
                  )}
                />

                {fieldErrors.spo2 && (
                  <span className="field-error">
                    {fieldErrors.spo2}
                  </span>
                )}
              </label>

              {/* PRIORITY */}
              <label className="nurse-field">
                <span className="nurse-field-label">
                  Triage Priority
                </span>

                <select
                  name="priority"
                  defaultValue="normal"
                >
                  <option value="normal">
                    Normal
                  </option>
                  <option value="medium">
                    Medium
                  </option>
                  <option value="high">
                    High
                  </option>
                  <option value="urgent">
                    Urgent
                  </option>
                </select>
              </label>

              {/* SYMPTOMS */}
              <label className="nurse-field full-width">
                <span className="nurse-field-label">
                  Patient Symptoms
                </span>

                <textarea
                  name="symptoms"
                  rows="3"
                  placeholder="Describe the patient's symptoms..."
                />
              </label>

              {/* NURSE NOTES */}
              <label className="nurse-field full-width">
                <span className="nurse-field-label">
                  Nurse Assessment Notes
                </span>

                <textarea
                  name="nurse_notes"
                  rows="3"
                  placeholder="Enter assessment observations and clinical notes..."
                />
              </label>
            </div>

            <div className="dashboard-actions">
              <button
                type="submit"
                className="button primary"
                disabled={saving}
              >
                {saving
                  ? "Saving Assessment..."
                  : "Complete Assessment"}
              </button>

              <button
                type="button"
                className="button secondary"
                disabled={saving}
                onClick={closePatient}
              >
                Cancel
              </button>
            </div>
          </form>
        </section>
      )}

      {/* ====================================================
          PAST MEDICAL RECORDS MODAL
          ==================================================== */}
      {historyModalPatient && (
        <div className="admin-modal-backdrop" onClick={closeHistoryModal}>
          <div
            className="admin-modal past-records-modal"
            onClick={(e) => e.stopPropagation()}
            style={{ width: "min(720px, 96%)", maxHeight: "88vh" }}
          >
            <div className="modal-header">
              <div>
                <p className="eyebrow">
                  PATIENT #{String(historyModalPatient.token_number || "").padStart(3, "0")}
                </p>
                <h2>Past Medical Records</h2>
                <p className="muted" style={{ margin: "4px 0 0", fontSize: "0.85rem" }}>
                  {historyModalPatient.patient_email} • Read-only historical visits
                </p>
              </div>
              <button
                type="button"
                className="mini-button close-btn"
                onClick={closeHistoryModal}
              >
                Close
              </button>
            </div>

            {historyLoading ? (
              <div className="loading-card" style={{ padding: "32px", textAlign: "center" }}>
                Loading medical records...
              </div>
            ) : historyError ? (
              <div className="alert danger">
                {historyError}
              </div>
            ) : !historyRecords || historyRecords.length === 0 ? (
              <div className="empty-card" style={{ padding: "32px", textAlign: "center" }}>
                <h3 style={{ margin: "0 0 8px" }}>No Past Medical Records</h3>
                <p className="muted" style={{ margin: 0 }}>
                  No previous completed medical visits were found.
                </p>
              </div>
            ) : (
              <div className="past-records-list" style={{ marginTop: "12px" }}>
                {historyRecords.map((record, index) => (
                  <article key={record.record_id || index} className="past-record-card">
                    <div className="past-record-header">
                      <span className="past-record-badge">
                        VISIT {historyRecords.length - index}
                      </span>
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

            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "20px" }}>
              <button
                type="button"
                className="button secondary"
                onClick={closeHistoryModal}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
