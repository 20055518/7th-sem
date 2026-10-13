import {
  useEffect,
  useRef,
  useState,
} from "react";

import { useNavigate } from "react-router-dom";

import AppNav from "../components/AppNav";

import {
  getDoctorDashboard,
  getDoctorPatient,
  callDoctorPatient,
  startDoctorConsultation,
  completeDoctorConsultation,
  skipPatient,
  requeuePatient,
  getNurseAssessment,
  getDoctorConsultation,
  saveDoctorConsultation,
  getDoctorPatientMedicalHistory,
} from "../api";

import "./DoctorDashboard.css";


// ============================================================
// HELPERS
// ============================================================

function formatToken(token) {
  if (
    token === null ||
    token === undefined ||
    token === ""
  ) {
    return "—";
  }

  return `#${String(token).padStart(3, "0")}`;
}


function formatMinutes(value) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "—";
  }

  const number = Number(value);

  return Number.isFinite(number)
    ? `${number.toFixed(1)} min`
    : "—";
}


function formatPercentage(value) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "—";
  }

  const number = Number(value);

  return Number.isFinite(number)
    ? `${(number * 100).toFixed(1)}%`
    : "—";
}


function normalizeStatus(status) {
  return String(status || "")
    .trim()
    .toLowerCase();
}


function formatStatus(status) {
  return String(status || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) =>
      char.toUpperCase()
    );
}


function extractQueue(data) {
  if (Array.isArray(data)) {
    return data;
  }

  if (Array.isArray(data?.active_patients)) {
    return data.active_patients;
  }

  if (Array.isArray(data?.patients)) {
    return data.patients;
  }

  if (Array.isArray(data?.queue)) {
    return data.queue;
  }

  return [];
}


function normalizeRisk(value) {
  const risk = String(value || "")
    .trim()
    .toLowerCase()
    .replaceAll("_", "-")
    .replaceAll(" ", "-");

  if (
    risk === "urgent" ||
    risk === "critical" ||
    risk === "high" ||
    risk === "medium" ||
    risk === "normal" ||
    risk === "low"
  ) {
    if (risk === "critical") {
      return "urgent";
    }
    if (risk === "normal") {
      return "normal";
    }
    return risk;
  }

  return "";
}


function extractRisk(details) {
  if (
    !details ||
    typeof details !== "object"
  ) {
    return "";
  }

  /*
   * IMPORTANT:
   * Risk must be checked BEFORE priority.
   *
   * The previous implementation checked "priority" first.
   * A patient with priority "normal" could therefore be
   * interpreted as a risk value, while the real risk_level
   * was ignored.
   */

  const directRiskKeys = [
    "risk_level",
    "riskLevel",
    "risk",
    "predicted_risk",
    "predictedRisk",
  ];

  for (const key of directRiskKeys) {
    const value = normalizeRisk(details?.[key]);

    if (value) {
      return value;
    }
  }

  /*
   * Check common nested prediction objects.
   */

  const nestedKeys = [
    "prediction",
    "ml_prediction",
    "mlPrediction",
    "assessment",
    "data",
    "patient",
    "queue_entry",
  ];

  for (const key of nestedKeys) {
    const nestedRisk =
      extractRisk(details?.[key]);

    if (nestedRisk) {
      return nestedRisk;
    }
  }

  /*
   * Never use triage priority as risk here.
   * Priority and risk are different concepts.
   */

  return "";
}


function deriveRiskFromPrediction(patient) {
  if (
    !patient ||
    typeof patient !== "object"
  ) {
    return "";
  }

  /*
   * Priority set by nurse in triage assessment takes precedence
   * over generic ML risk defaults.
   */
  const nursePriority = normalizeRisk(
    patient?.priority ??
    patient?.triage_priority
  );

  if (nursePriority) {
    return nursePriority;
  }

  /*
   * If the backend supplied an actual risk_level,
   * prefer it next.
   */
  const backendRisk =
    normalizeRisk(
      patient?.risk_level ??
      patient?.riskLevel ??
      patient?.risk ??
      patient?.predicted_risk ??
      patient?.predictedRisk,
    );

  if (backendRisk) {
    return backendRisk;
  }

  /*
   * Fallback only when the backend did not send risk.
   *
   * This prevents the UI from being stuck at "Loading..."
   * forever when ML wait/probability data are already available.
   */

  const wait = Number(
    patient?.predicted_wait_minutes,
  );

  const longProbability =
    Number(
      patient?.probability_long_or_more,
    );

  const priority =
    String(
      patient?.priority ??
      patient?.triage_priority ??
      "",
    )
      .trim()
      .toLowerCase();

  if (priority === "urgent") {
    return "urgent";
  }

  if (priority === "high") {
    return "high";
  }

  if (priority === "medium") {
    return "medium";
  }

  if (
    Number.isFinite(wait) &&
    wait >= 60
  ) {
    return "urgent";
  }

  if (
    Number.isFinite(wait) &&
    wait >= 45
  ) {
    return "high";
  }

  if (
    Number.isFinite(wait) &&
    wait >= 30
  ) {
    return "medium";
  }

  if (
    Number.isFinite(longProbability) &&
    longProbability >= 0.75
  ) {
    return "urgent";
  }

  if (
    Number.isFinite(longProbability) &&
    longProbability >= 0.50
  ) {
    return "high";
  }

  if (
    Number.isFinite(longProbability) &&
    longProbability >= 0.25
  ) {
    return "medium";
  }

  if (
    Number.isFinite(wait) ||
    Number.isFinite(longProbability)
  ) {
    return "low";
  }

  return "";
}

const EMPTY_CONSULTATION = {
  diagnosis: "",
  consultation_notes: "",
  prescription: "",
  treatment_advice: "",
};


// ============================================================
// DOCTOR DASHBOARD
// ============================================================

export default function DoctorDashboard() {

  const navigate = useNavigate();

  // ----------------------------------------------------------
  // Queue
  // ----------------------------------------------------------

  const [queue, setQueue] =
    useState([]);

  const [skippedPatients, setSkippedPatients] =
    useState([]);

  // ----------------------------------------------------------
  // Risk cache
  // ----------------------------------------------------------

  const riskCacheRef =
    useRef({});

  const [riskCache, setRiskCache] =
    useState({});

  // ----------------------------------------------------------
  // Scroll targets
  // ----------------------------------------------------------

  const workspaceRef = useRef(null);
  const queueRef     = useRef(null);
  const patientRowRefs = useRef({});
  // ----------------------------------------------------------
  // General state
  // ----------------------------------------------------------

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");

  const [actionLoading, setActionLoading] =
    useState("");

  // ----------------------------------------------------------
  // Selected patient
  // ----------------------------------------------------------

  const [selectedPatient, setSelectedPatient] =
    useState(null);

  const [checkup, setCheckup] =
    useState(null);

  const [checkupLoading, setCheckupLoading] =
    useState(false);

  // ----------------------------------------------------------
  // Doctor consultation
  // ----------------------------------------------------------

  const [consultation, setConsultation] =
    useState(EMPTY_CONSULTATION);

  const [consultationLoading, setConsultationLoading] =
    useState(false);

  const [consultationSaving, setConsultationSaving] =
    useState(false);

  const [consultationSaved, setConsultationSaved] =
    useState(false);

  const [completionMessage, setCompletionMessage] =
    useState("");

  // Past Medical Records Modal State
  const [historyModalPatient, setHistoryModalPatient] = useState(null);
  const [historyRecords, setHistoryRecords] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");

  async function openDoctorHistoryModal(patient) {
    setHistoryModalPatient(patient);
    setHistoryRecords([]);
    setHistoryError("");
    setHistoryLoading(true);

    try {
      const idToLookup = patient.token_number || patient.patient_email;
      const res = await getDoctorPatientMedicalHistory(idToLookup);
      setHistoryRecords(Array.isArray(res?.records) ? res.records : []);
    } catch (err) {
      console.error("Doctor past records error:", err);
      setHistoryError("Unable to load past medical records.");
    } finally {
      setHistoryLoading(false);
    }
  }

  function closeDoctorHistoryModal() {
    setHistoryModalPatient(null);
    setHistoryRecords([]);
    setHistoryError("");
  }

  // Scroll target: jump to consultation form after Start
  const consultationRef = useRef(null);
  const diagnosisRef = useRef(null);


  // ==========================================================
  // LOAD ACTUAL PATIENT RISK
  // ==========================================================

  async function loadPatientRisk(patient) {

    const token =
      patient?.token_number;

    if (
      token === null ||
      token === undefined ||
      token === ""
    ) {
      return;
    }

    const tokenKey =
      String(token);

    /*
     * First use the queue payload itself.
     *
     * getDoctorDashboard() normally already contains
     * risk_level. There is no reason to make another API
     * request when the value is already available.
     */

    const queueRisk =
      deriveRiskFromPrediction(
        patient,
      );

    if (queueRisk) {

      riskCacheRef.current[
        tokenKey
      ] = queueRisk;

      setRiskCache(
        (current) => ({
          ...current,
          [tokenKey]:
            queueRisk,
        }),
      );

      return;
    }

    /*
     * Only request the detailed patient endpoint when the
     * queue payload does not contain enough information.
     */

    try {

      const details =
        await getDoctorPatient(token);

      const actualRisk =
        extractRisk(details);

      const fallbackRisk =
        actualRisk ||
        deriveRiskFromPrediction(
          patient,
        );

      /*
       * Always resolve the cache.
       *
       * The old code left the UI in "Loading..." forever when
       * the detail endpoint returned no risk.
       */

      riskCacheRef.current[
        tokenKey
      ] =
        fallbackRisk ||
        "unavailable";

      setRiskCache(
        (current) => ({
          ...current,
          [tokenKey]:
            fallbackRisk ||
            "unavailable",
        }),
      );

    } catch (err) {

      console.error(
        `Unable to load patient risk for ${token}:`,
        err,
      );

      /*
       * Even if the detail request fails, calculate a
       * client-side fallback from the queue prediction data.
       */

      const fallbackRisk =
        deriveRiskFromPrediction(
          patient,
        );

      riskCacheRef.current[
        tokenKey
      ] =
        fallbackRisk ||
        "unavailable";

      setRiskCache(
        (current) => ({
          ...current,
          [tokenKey]:
            fallbackRisk ||
            "unavailable",
        }),
      );

    }
  }


  // ==========================================================
  // LOAD RISKS
  // ==========================================================

  async function loadQueueRisks(patients) {

    if (
      !Array.isArray(patients) ||
      patients.length === 0
    ) {
      return;
    }

    /*
     * Seed the cache directly from the queue response.
     * This makes risk render immediately without waiting for
     * getDoctorPatient().
     */

    const pending = [];

    for (const patient of patients) {

      const token =
        patient?.token_number;

      if (
        token === null ||
        token === undefined ||
        token === ""
      ) {
        continue;
      }

      const tokenKey =
        String(token);

      const risk =
        deriveRiskFromPrediction(
          patient,
        );

      if (risk) {

        riskCacheRef.current[
          tokenKey
        ] = risk;

        continue;
      }

      if (
        !Object.prototype.hasOwnProperty.call(
          riskCacheRef.current,
          tokenKey,
        )
      ) {
        pending.push(patient);
      }
    }

    /*
     * Publish all directly available risks immediately.
     */

    setRiskCache(
      { ...riskCacheRef.current },
    );

    /*
     * Only unresolved patients need another request.
     */

    if (pending.length > 0) {

      await Promise.all(
        pending.map(
          (patient) =>
            loadPatientRisk(
              patient,
            ),
        ),
      );

    }

  }

  // ==========================================================
  // LOAD DOCTOR QUEUE
  // ==========================================================

  async function loadQueue() {

    try {

      const data =
        await getDoctorDashboard();

      const activePatients =
        Array.isArray(data?.active_patients)
          ? data.active_patients
          : extractQueue(data).filter(
              (patient) => {

                const status =
                  normalizeStatus(
                    patient?.status,
                  );

                return (
                  status === "waiting" ||
                  status === "called" ||
                  status === "in_consultation"
                );

              },
            );

      const backendSkipped =
        Array.isArray(data?.skipped_patients)
          ? data.skipped_patients
          : extractQueue(data).filter(
              (patient) =>
                normalizeStatus(
                  patient?.status,
                ) === "skipped",
            );

      setQueue(
        activePatients,
      );

      setSkippedPatients(
        backendSkipped,
      );

      /*
       * Remove cached risks for patients who are no longer
       * present in the active queue.
       */

      const activeTokenSet =
        new Set(
          activePatients
            .map(
              (patient) =>
                patient?.token_number,
            )
            .filter(
              (token) =>
                token !== null &&
                token !== undefined &&
                token !== "",
            )
            .map(
              (token) =>
                String(token),
            ),
        );

      for (
        const tokenKey of Object.keys(
          riskCacheRef.current,
        )
      ) {

        if (
          !activeTokenSet.has(tokenKey)
        ) {

          delete riskCacheRef.current[
            tokenKey
          ];

        }

      }

      /*
       * Render the queue immediately with risk values from
       * the dashboard response.
       */

      const immediateRiskCache = {
        ...riskCacheRef.current,
      };

      for (
        const patient of activePatients
      ) {

        const token =
          patient?.token_number;

        if (
          token === null ||
          token === undefined ||
          token === ""
        ) {
          continue;
        }

        const risk =
          deriveRiskFromPrediction(
            patient,
          );

        if (risk) {

          immediateRiskCache[
            String(token)
          ] = risk;

          riskCacheRef.current[
            String(token)
          ] = risk;

        }

      }

      setRiskCache(
        immediateRiskCache,
      );

      await loadQueueRisks(
        activePatients,
      );

      setError("");

    } catch (err) {

      console.error(
        "Doctor dashboard error:",
        err,
      );

      if (
        err?.status === 401
      ) {

        navigate(
          "/login",
          {
            replace: true,
          },
        );

        return;
      }

      setError(
        err?.message ||
        "Unable to load doctor queue.",
      );

    } finally {

      setLoading(false);

    }
  }


  // ==========================================================
  // LIVE QUEUE
  // ==========================================================

  useEffect(() => {

    let mounted = true;

    loadQueue();

    const interval =
      setInterval(
        () => {

          if (mounted) {
            loadQueue();
          }

        },
        3000,
      );

    return () => {

      mounted = false;

      clearInterval(
        interval,
      );

    };

  }, []);


  // ==========================================================
  // LOAD NORMAL CHECK-UP
  // ==========================================================

  async function loadPatientCheckup(patient) {

    const patientEmail =
      patient?.patient_email ||
      patient?.email;

    if (!patientEmail) {

      setError(
        "Patient email is unavailable.",
      );

      return;

    }

    try {

      setCheckupLoading(
        true,
      );

      setSelectedPatient(
        patient,
      );

      setError("");

      const data =
        await getNurseAssessment(
          patientEmail,
        );

      const assessment =
        data?.assessment ||
        data?.data ||
        data;

      setCheckup(
        assessment,
      );

    } catch (err) {

      console.error(
        "Normal check-up error:",
        err,
      );

      setCheckup(
        null,
      );

      setError(
        err?.message ||
        "Unable to load normal check-up.",
      );

    } finally {

      setCheckupLoading(
        false,
      );

    }
  }


  // ==========================================================
  // LOAD CONSULTATION
  // ==========================================================

async function loadDoctorConsultation(patient) {
  const token = patient?.token_number;

  if (
    token === null ||
    token === undefined ||
    token === ""
  ) {
    return;
  }

  const status = normalizeStatus(patient?.status);

  // A consultation record is created only after
  // the doctor starts the consultation.
  if (status !== "in_consultation") {
    setConsultation({ ...EMPTY_CONSULTATION });
    setConsultationSaved(false);
    setConsultationLoading(false);
    return;
  }

  try {
    setConsultationLoading(true);

    const data = await getDoctorConsultation(token);

    const hasSavedRecord = Boolean(data?.id || data?.diagnosis);

    setConsultation({
      diagnosis: data?.diagnosis || "",
      consultation_notes: data?.consultation_notes || "",
      prescription: data?.prescription || "",
      treatment_advice: data?.treatment_advice || "",
    });

    setConsultationSaved(hasSavedRecord);
  } catch (err) {
    if (err?.status === 401) {
      navigate("/login", {
        replace: true,
      });
      return;
    }

    if (err?.status === 404) {
      setConsultation({
        ...EMPTY_CONSULTATION,
      });
      setConsultationSaved(false);
      return;
    }

    console.error(
      "Doctor consultation load error:",
      err
    );

    setError(
      err?.message ||
        "Unable to load consultation."
    );

    setConsultation({
      ...EMPTY_CONSULTATION,
    });

    setConsultationSaved(false);
  } finally {
    setConsultationLoading(false);
  }
}


  // ==========================================================
  // SELECT PATIENT
  // ==========================================================

  async function openPatientWorkspace(
    patient,
  ) {

    setSelectedPatient(
      patient,
    );

    setCheckup(
      null,
    );

    setConsultation(
      { ...EMPTY_CONSULTATION },
    );

    setConsultationSaved(
      false,
    );

    await loadPatientCheckup(
      patient,
    );

    await loadDoctorConsultation(
      patient,
    );

    // Scroll to the workspace panel
    setTimeout(() => {
      workspaceRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }, 80);

  }


  // ==========================================================
  // CLOSE WORKSPACE
  // ==========================================================

function closeWorkspace() {
  const token = selectedPatient?.token_number;

  setSelectedPatient(null);
  setCheckup(null);
  setConsultation({ ...EMPTY_CONSULTATION });
  setConsultationSaved(false);
  setConsultationLoading(false);
  setConsultationSaving(false);

  if (token !== null && token !== undefined) {
    setTimeout(() => {
      patientRowRefs.current[String(token)]?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }, 100);
  }
}


  // ==========================================================
  // CONSULTATION FIELD CHANGE
  // ==========================================================

  function updateConsultationField(
    field,
    value,
  ) {

    setConsultation(
      (current) => ({
        ...current,
        [field]:
          value,
      }),
    );

    setConsultationSaved(
      false,
    );

  }


  // ==========================================================
  // SAVE CONSULTATION
  // ==========================================================

  async function handleSaveConsultation() {

    if (!selectedPatient) {
      return;
    }

    const token =
      selectedPatient.token_number;

    const diagnosis =
      consultation.diagnosis.trim();

    if (!diagnosis) {
      setError(
        "Diagnosis is required before saving the consultation.",
      );

      setTimeout(() => {
        diagnosisRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "center",
        });

        diagnosisRef.current?.focus();
      }, 100);

      return;
    }

    try {

      setConsultationSaving(
        true,
      );

      setError("");

      const saved =
        await saveDoctorConsultation(
          token,
          {
            diagnosis:
              consultation.diagnosis.trim(),

            consultation_notes:
              consultation.consultation_notes.trim(),

            prescription:
              consultation.prescription.trim(),

            treatment_advice:
              consultation.treatment_advice.trim(),
          },
        );

      setConsultation({
        diagnosis:
          saved?.diagnosis || "",

        consultation_notes:
          saved?.consultation_notes || "",

        prescription:
          saved?.prescription || "",

        treatment_advice:
          saved?.treatment_advice || "",
      });

      setConsultationSaved(
        true,
      );

    } catch (err) {

      console.error(
        "Save consultation error:",
        err,
      );

      if (
        err?.status === 401
      ) {

        navigate(
          "/login",
          {
            replace: true,
          },
        );

        return;
      }

      setError(
        err?.message ||
        "Unable to save consultation.",
      );

    } finally {

      setConsultationSaving(
        false,
      );

    }
  }


  // ==========================================================
  // COMPLETE CONSULTATION
  // ==========================================================

async function handleCompleteConsultation(targetPatient = null) {
  const activePt = targetPatient || selectedPatient;

  if (!activePt) {
    return;
  }

  const token = activePt.token_number;

  // Completion must happen from the consultation workspace.
  const workspaceOpenForThisPatient =
    selectedPatient &&
    String(selectedPatient.token_number) === String(token);

  if (!workspaceOpenForThisPatient) {
    setError(
      "Please open the consultation workspace, enter the diagnosis, and save the consultation before completing."
    );

    return;
  }

  const diagnosis = consultation.diagnosis.trim();

  if (!diagnosis) {
    setError(
      "Diagnosis is required before completing the consultation."
    );

    return;
  }

  try {
    setActionLoading(`complete-${token}`);
    setError("");

    // Save consultation first.
    await saveDoctorConsultation(
      token,
      {
        diagnosis: consultation.diagnosis.trim(),

        consultation_notes:
          consultation.consultation_notes.trim(),

        prescription:
          consultation.prescription.trim(),

        treatment_advice:
          consultation.treatment_advice.trim(),
      }
    );

    // Only after successful save, complete the consultation.
    await completeDoctorConsultation(token);

    closeWorkspace();

    await loadQueue();

    const tokenLabel =
      `#${String(token).padStart(3, "0")}`;

    setCompletionMessage(
      `Consultation completed — Patient ${tokenLabel}`
    );

    setTimeout(() => {
      queueRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }, 80);

    setTimeout(() => {
      setCompletionMessage("");
    }, 4000);

  } catch (err) {
    console.error(
      "Complete consultation error:",
      err
    );

    if (err?.status === 401) {
      navigate("/login", {
        replace: true,
      });

      return;
    }

    setError(
      err?.message ||
      "Unable to complete consultation."
    );

  } finally {
    setActionLoading("");
  }
}

  // ==========================================================
  // SKIP PATIENT
  // ==========================================================

  async function handleSkip(
    patient,
  ) {

    const token =
      patient?.token_number;

    const department =
      patient?.department ||
      "";

    const actionKey =
      `skip-${token}`;

    if (actionLoading) {
      return;
    }

    try {

      setActionLoading(
        actionKey,
      );

      setError("");

      await skipPatient(
        department,
        token,
      );

      setQueue(
        (current) =>
          current.filter(
            (item) =>
              String(
                item?.token_number,
              ) !==
              String(token),
          ),
      );

      setSkippedPatients(
        (current) => {

          const exists =
            current.some(
              (item) =>
                String(
                  item?.token_number,
                ) ===
                String(token),
            );

          if (exists) {
            return current;
          }

          return [
            ...current,
            {
              ...patient,
              status: "skipped",
            },
          ];

        },
      );

      if (
        selectedPatient &&
        String(
          selectedPatient?.token_number,
        ) ===
        String(token)
      ) {

        closeWorkspace();

      }

    } catch (err) {

      console.error(
        "Skip patient error:",
        err,
      );

      if (
        err?.status === 401
      ) {

        navigate(
          "/login",
          {
            replace: true,
          },
        );

        return;
      }

      setError(
        err?.message ||
        "Unable to skip patient.",
      );

    } finally {

      setActionLoading(
        "",
      );

    }
  }


  // ==========================================================
  // REQUEUE PATIENT
  // ==========================================================

  async function handleRequeue(
    patient,
  ) {

    const token =
      patient?.token_number;

    const department =
      patient?.department ||
      "";

    const actionKey =
      `requeue-${token}`;

    if (actionLoading) {
      return;
    }

    try {

      setActionLoading(
        actionKey,
      );

      setError("");

      await requeuePatient(
        department,
        token,
      );

      setSkippedPatients(
        (current) =>
          current.filter(
            (item) =>
              String(
                item?.token_number,
              ) !==
              String(token),
          ),
      );

      delete riskCacheRef.current[
        String(token)
      ];

      setRiskCache(
        (current) => {

          const updated = {
            ...current,
          };

          delete updated[
            String(token)
          ];

          return updated;

        },
      );

      await loadQueue();

    } catch (err) {

      console.error(
        "Requeue patient error:",
        err,
      );

      if (
        err?.status === 401
      ) {

        navigate(
          "/login",
          {
            replace: true,
          },
        );

        return;
      }

      setError(
        err?.message ||
        "Unable to add patient back to queue.",
      );

    } finally {

      setActionLoading(
        "",
      );

    }
  }


  // ==========================================================
  // CALL PATIENT
  // ==========================================================

async function handleCall(patient) {
  const token = patient?.token_number;

  // Check whether another patient is already called
  // or currently in consultation.
  const activePatient = queue.find((item) => {
    const itemToken = item?.token_number;
    const status = normalizeStatus(item?.status);

    return (
      String(itemToken) !== String(token) &&
      (status === "called" ||
        status === "in_consultation")
    );
  });

  if (activePatient) {
    const activeToken = activePatient?.token_number;
    const activeStatus = normalizeStatus(
      activePatient?.status
    );

    setError(
      activeStatus === "in_consultation"
        ? `Patient ${formatToken(
            activeToken
          )} is currently in consultation. Complete that patient first.`
        : `Patient ${formatToken(
            activeToken
          )} has already been called. Complete that patient first.`
    );

    return;
  }

  const actionKey = `call-${token}`;

  if (actionLoading) {
    return;
  }

  try {
    setActionLoading(actionKey);
    setError("");

    await callDoctorPatient(token);

    setQueue((current) =>
      current.map((item) =>
        String(item?.token_number) === String(token)
          ? {
              ...item,
              status: "called",
            }
          : item
      )
    );

    /*
     * Do NOT auto-open workspace when calling.
     * Doctor clicks "Check-up" or "Start" manually.
     * Previously openPatientWorkspace() was called here
     * which caused the "auto-call" behaviour.
     */

  } catch (err) {
    console.error(
      "Call patient error:",
      err
    );

    if (err?.status === 401) {
      navigate("/login", {
        replace: true,
      });
      return;
    }

    setError(
      err?.message ||
        "Unable to call patient."
    );
  } finally {
    setActionLoading("");
  }
}


  // ==========================================================
  // START CONSULTATION
  // ==========================================================

  async function handleStart(
    patient,
  ) {

    const token =
      patient?.token_number;

    const actionKey =
      `start-${token}`;

    if (actionLoading) {
      return;
    }

    const anotherPatientInConsultation = queue.find((item) => {
      const itemToken = item?.token_number;
      const status = normalizeStatus(item?.status);

      return (
        String(itemToken) !== String(token) &&
        status === "in_consultation"
      );
    });

    if (anotherPatientInConsultation) {
      setError(
        `Patient ${formatToken(
          anotherPatientInConsultation?.token_number
        )} is currently in consultation. Complete that patient first.`
      );
      return;
    }

    try {

      setActionLoading(
        actionKey,
      );

      setError("");

      await startDoctorConsultation(
        token,
      );

      const updatedPatient = {
        ...patient,
        status:
          "in_consultation",
      };

      setQueue(
        (current) =>
          current.map(
            (item) =>
              String(
                item?.token_number,
              ) ===
              String(token)
                ? updatedPatient
                : item,
          ),
      );

      await openPatientWorkspace(
        updatedPatient,
      );

      // Scroll to the consultation form, not just the workspace top
      setTimeout(() => {
        consultationRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }, 200);

    } catch (err) {

      console.error(
        "Start consultation error:",
        err,
      );

      if (
        err?.status === 401
      ) {

        navigate(
          "/login",
          {
            replace: true,
          },
        );

        return;
      }

      setError(
        err?.message ||
        "Unable to start consultation.",
      );

    } finally {

      setActionLoading(
        "",
      );

    }
  }


  // ==========================================================
  // COUNTS
  // ==========================================================

  const waitingCount =
    queue.filter(
      (patient) =>
        normalizeStatus(
          patient?.status,
        ) === "waiting",
    ).length;

  const calledCount =
    queue.filter(
      (patient) =>
        normalizeStatus(
          patient?.status,
        ) === "called",
    ).length;

  const consultationCount =
    queue.filter(
      (patient) =>
        normalizeStatus(
          patient?.status,
        ) === "in_consultation",
    ).length;

    const activePatient =
  queue.find((patient) => {
    const status = normalizeStatus(patient?.status);

    return (
      status === "called" ||
      status === "in_consultation"
    );
  }) || null;

const hasActivePatient =
  Boolean(activePatient);
  // ==========================================================
  // RENDER
  // ==========================================================

  return (

    <main className="doctor-dashboard">

      <AppNav />


      {/* ====================================================
          HEADER
          ==================================================== */}

      <header className="page-header">

        <div>

          <p className="eyebrow">
            DOCTOR DASHBOARD
          </p>

          <h1>
            Patient Queue
          </h1>

          <p className="muted">
            Manage your assigned patients
            and consultations.
          </p>

        </div>

        <span className="live-pill">
          ● Live
        </span>

      </header>


      {/* ====================================================
          ERROR
          ==================================================== */}

      {error && (

        <div
          className="alert danger"
          role="alert"
        >
          {error}
        </div>

      )}


      {/* ====================================================
          SUMMARY
          ==================================================== */}

      <section className="doctor-stats">

        <div className="summary-card">

          <span>
            Waiting
          </span>

          <strong>
            {waitingCount}
          </strong>

        </div>


        <div className="summary-card">

          <span>
            Called
          </span>

          <strong>
            {calledCount}
          </strong>

        </div>


        <div className="summary-card">

          <span>
            Consultation
          </span>

          <strong>
            {consultationCount}
          </strong>

        </div>


        <div className="summary-card">

          <span>
            Skipped
          </span>

          <strong>
            {skippedPatients.length}
          </strong>

        </div>

      </section>


      {/* ====================================================
          ACTIVE QUEUE
          ==================================================== */}

          <section className="queue-section" ref={queueRef}>

            {completionMessage && (
              <div className="completion-toast">
                ✓ {completionMessage}
              </div>
            )}

            <div className="section-heading"> 

          <div>

            <p className="eyebrow">
              ACTIVE QUEUE
            </p>

            <h2>
              My Patients
            </h2>

          </div>

          <div className="section-heading-actions">

            <button
              type="button"
              className="mini-button refresh-btn"
              onClick={() => window.location.reload()}
              aria-label="Refresh queue"
            >
              ↻ Refresh
            </button>

            <span className="queue-count">
              {queue.length}
            </span>

          </div>

        </div>


        {loading ? (

          <div className="loading-card">
            Loading doctor queue...
          </div>

        ) : queue.length === 0 ? (

          <div className="empty-card">

            <h2>
              No active patients
            </h2>

            <p className="muted">
              There are currently no patients
              waiting for your consultation.
            </p>

          </div>

        ) : (

          <div className="queue-table-wrap">

            <table className="queue-table">

              <thead>

                <tr>

                  <th>
                    Position
                  </th>

                  <th>
                    Token
                  </th>

                  <th>
                    Patient
                  </th>

                  <th>
                    Department
                  </th>

                  <th>
                    Status
                  </th>

                  <th>
                     Wait Time
                  </th>

                  <th>
                    Probability
                  </th>

                  <th>
                    Risk
                  </th>

                  <th>
                    Actions
                  </th>

                </tr>

              </thead>


              <tbody>

                {queue.map(
                  (patient) => {

                    const token =
                      patient?.token_number;

                    const status =
                      normalizeStatus(
                        patient?.status,
                      );

                    const actionKey =
                      String(token);

                    const actualRisk =
                      normalizeRisk(
                        patient?.priority ||
                        patient?.triage_priority,
                      ) ||
                      normalizeRisk(
                        riskCache[
                          String(token)
                        ] ||
                        patient?.risk_level ||
                        patient?.riskLevel ||
                        patient?.risk,
                      ) ||
                      deriveRiskFromPrediction(
                        patient,
                      );

                    const riskClass =
                      actualRisk ||
                      "unavailable";

                    const riskLabel =
                      actualRisk
                        ? actualRisk
                            .replace(
                              /^./,
                              (char) =>
                                char.toUpperCase(),
                            )
                        : "Unavailable";


                    return (

                      <tr
                        ref={(element) => {
                          if (element) {
                            patientRowRefs.current[String(token)] = element;
                          }
                        }}
                        key={
                          patient?._id ||
                          patient?.id ||
                          `patient-${token}`
                        }
                      >

                        <td>

                          <strong>
                            {
                              patient?.position ??
                              "—"
                            }
                          </strong>

                        </td>


                        <td>

                          <strong>
                            {
                              formatToken(
                                token,
                              )
                            }
                          </strong>

                        </td>


                        <td>

                          <span className="doctor-patient-email">
                            {
                              patient?.patient_email ||
                              "—"
                            }
                          </span>

                        </td>


                        <td>
                          {
                            patient?.department ||
                            "—"
                          }
                        </td>


                        <td>

                          <span
                            className={
                              `status-badge status-${status}`
                            }
                          >

                            {
                              formatStatus(
                                status,
                              )
                            }

                          </span>

                        </td>


                        <td>
                          {
                            formatMinutes(
                              patient?.predicted_wait_minutes,
                            )
                          }
                        </td>


                        <td>
                          {
                            formatPercentage(
                              patient?.probability_long_or_more,
                            )
                          }
                        </td>


                        <td>

                          <span
                            className={
                              `risk-badge risk-${riskClass}`
                            }
                          >

                            {
                              riskLabel
                            }

                          </span>

                        </td>


                        <td>

                          <div className="action-group">


                            {/* WAITING */}

                            {status === "waiting" && (

                              <>

                                <button
                                  className="mini-button checkup-button"
                                  onClick={() =>
                                    openPatientWorkspace(
                                      patient,
                                    )
                                  }
                                >
                                  Check-up
                                </button>

                                {patient?.has_past_records && (
                                  <button
                                    className="mini-button past-records-btn"
                                    type="button"
                                    onClick={() =>
                                      openDoctorHistoryModal(
                                        patient,
                                      )
                                    }
                                  >
                                    Past Records
                                  </button>
                                )}

                                <button
                                  className="mini-button"
                                  disabled={
                                    actionLoading === `start-${actionKey}` ||
                                    actionLoading === `call-${actionKey}` ||
                                    hasActivePatient
                                  }
                                  onClick={() =>
                                    handleStart(
                                      patient,
                                    )
                                  }
                                >
                                  {actionLoading ===
                                  `start-${actionKey}`
                                    ? "Starting..."
                                    : "Start"}
                                </button>

                                <button
                                  className="mini-button danger-button"
                                  disabled={
                                    actionLoading ===
                                    `skip-${actionKey}`
                                  }
                                  onClick={() =>
                                    handleSkip(
                                      patient,
                                    )
                                  }
                                >
                                  {actionLoading ===
                                  `skip-${actionKey}`
                                    ? "Skipping..."
                                    : "Skip"}
                                </button>

                              </>

                            )}


                            {/* CALLED */}

                            {status === "called" && (

                              <>

                                <button
                                  className="mini-button checkup-button"
                                  onClick={() =>
                                    openPatientWorkspace(
                                      patient,
                                    )
                                  }
                                >
                                  Check-up
                                </button>

                                {patient?.has_past_records && (
                                  <button
                                    className="mini-button past-records-btn"
                                    type="button"
                                    onClick={() =>
                                      openDoctorHistoryModal(
                                        patient,
                                      )
                                    }
                                  >
                                    Past Records
                                  </button>
                                )}

                                <button
                                  className="mini-button"
                                  disabled={
                                    actionLoading ===
                                    `start-${actionKey}` ||
                                    hasActivePatient
                                  }
                                  onClick={() =>
                                    handleStart(
                                      patient,
                                    )
                                  }
                                >

                                  {actionLoading ===
                                  `start-${actionKey}`
                                    ? "Starting..."
                                    : "Start"}

                                </button>


                                <button
                                  className="mini-button danger-button"
                                  disabled={
                                    actionLoading ===
                                    `skip-${actionKey}`
                                  }
                                  onClick={() =>
                                    handleSkip(
                                      patient,
                                    )
                                  }
                                >
                                  Skip
                                </button>

                              </>

                            )}


                            {/* IN CONSULTATION */}

                            {status ===
                              "in_consultation" && (

                              <>

                                <button
                                  className="mini-button checkup-button"
                                  onClick={() =>
                                    openPatientWorkspace(
                                      patient,
                                    )
                                  }
                                >
                                  Check-up
                                </button>

                                {patient?.has_past_records && (
                                  <button
                                    className="mini-button past-records-btn"
                                    type="button"
                                    onClick={() =>
                                      openDoctorHistoryModal(
                                        patient,
                                      )
                                    }
                                  >
                                    Past Records
                                  </button>
                                )}

                                <button
                                  className="mini-button complete-button"
                                  disabled={
                                    actionLoading ===
                                    `complete-${actionKey}`
                                  }
                                  onClick={() =>
                                    handleCompleteConsultation(
                                      patient,
                                    )
                                  }
                                >

                                  {actionLoading ===
                                  `complete-${actionKey}`
                                    ? "Completing..."
                                    : "Complete"}

                                </button>

                                <button
                                  className="mini-button danger-button"
                                  disabled={
                                    actionLoading ===
                                    `skip-${actionKey}`
                                  }
                                  onClick={() =>
                                    handleSkip(
                                      patient,
                                    )
                                  }
                                >
                                  Skip
                                </button>

                              </>

                            )}

                          </div>

                        </td>

                      </tr>

                    );

                  },
                )}

              </tbody>

            </table>

          </div>

        )}

      </section>


      {/* ====================================================
          PATIENT WORKSPACE
          ==================================================== */}

      {selectedPatient && (

        <section className="doctor-workspace" ref={workspaceRef}>


          {/* ==================================================
              WORKSPACE HEADER
              ================================================== */}

          <div className="workspace-header">

            <div>

              <p className="eyebrow">
                PATIENT WORKSPACE
              </p>

              <h2>
                Patient{" "}
                {
                  formatToken(
                    selectedPatient?.token_number,
                  )
                }
              </h2>

              <p className="muted">

                {
                  selectedPatient?.patient_email ||
                  "Patient"
                }

                {" • "}

                {
                  selectedPatient?.department ||
                  "—"
                }

              </p>

            </div>


            <button
              className="mini-button close-checkup-button"
              onClick={
                closeWorkspace
              }
            >
              Close
            </button>

          </div>




          {/* ==================================================
              NURSE ASSESSMENT  (read-only vitals from nurse)
              ================================================== */}

          <div className="workspace-section">

            <div className="section-heading">
              <div>
                <p className="eyebrow">NORMAL CHECK-UP</p>
                <h2>Nurse Assessment</h2>
              </div>
            </div>


            {checkupLoading ? (

              <div className="loading-card">
                Loading nurse assessment...
              </div>

            ) : checkup ? (

              <div className="checkup-grid">

                <div className="checkup-item">
                  <span>Temperature</span>
                  <strong>{checkup?.temperature ?? checkup?.temp ?? "—"}</strong>
                </div>

                <div className="checkup-item">
                  <span>Pulse</span>
                  <strong>{checkup?.pulse ?? checkup?.heart_rate ?? "—"}</strong>
                </div>

                <div className="checkup-item">
                  <span>Systolic BP</span>
                  <strong>{checkup?.systolic_bp ?? checkup?.systolic ?? "—"}</strong>
                </div>

                <div className="checkup-item">
                  <span>Diastolic BP</span>
                  <strong>{checkup?.diastolic_bp ?? checkup?.diastolic ?? "—"}</strong>
                </div>

                <div className="checkup-item">
                  <span>SpO₂</span>
                  <strong>{checkup?.spo2 ?? checkup?.oxygen_saturation ?? "—"}</strong>
                </div>

                <div className="checkup-item">
                  <span>Priority</span>
                  <strong>{checkup?.priority ?? checkup?.triage_priority ?? "—"}</strong>
                </div>

                <div className="checkup-wide-item">
                  <span>Symptoms</span>
                  <p>{checkup?.symptoms || "No symptoms recorded."}</p>
                </div>

                <div className="checkup-wide-item">
                  <span>Nurse Notes</span>
                  <p>{checkup?.nurse_notes || checkup?.notes || "No nurse notes recorded."}</p>
                </div>

              </div>

            ) : (

              <div className="empty-card">
                <h2>No assessment record found</h2>
                <p className="muted">
                  No nurse assessment is available for this patient.
                </p>
              </div>

            )}


           {/* Start button — bottom of the nurse assessment box */}
              <div className="checkup-footer-actions">

                <button
                  type="button"
                  className="mini-button start-button"
                  disabled={
                    actionLoading === `start-${selectedPatient?.token_number}`
                  }
                  onClick={() => handleStart(selectedPatient)}
                >
                  {actionLoading === `start-${selectedPatient?.token_number}`
                    ? "Starting..."
                    : "Start"}
                </button>

              </div>

          </div>



          {/* ==================================================
              DOCTOR CONSULTATION
              ================================================== */}

          <div className="workspace-section" ref={consultationRef}>

            <div className="section-heading">

              <div>

                <p className="eyebrow">
                  DOCTOR CONSULTATION
                </p>

                <h2>
                  Consultation Record
                </h2>

                <p className="muted">
                  Record diagnosis, notes,
                  prescription, and treatment advice.
                </p>

              </div>


              {consultationSaved && (

                <span className="saved-pill">
                  ✓ Saved
                </span>

              )}

            </div>


            {consultationLoading ? (

              <div className="loading-card">
                Loading consultation...
              </div>

            ) : (

              <div className="consultation-form">


                {/* DIAGNOSIS */}

                <div className="form-field">

                  <label htmlFor="doctor-diagnosis">
                    Diagnosis
                  </label>
                  <textarea
                    ref={diagnosisRef}
                    id="doctor-diagnosis"
                    rows={4}
                    value={consultation.diagnosis}
                    onChange={(event) =>
                      updateConsultationField(
                        "diagnosis",
                        event.target.value,
                      )
                    }
                    disabled={
                      normalizeStatus(
                        selectedPatient?.status,
                      ) !==
                      "in_consultation"
                    }
                    placeholder="Enter the diagnosis..."
                  />

                  <small>
                    Diagnosis is required before completion.
                  </small>

                </div>


                {/* CONSULTATION NOTES */}

                <div className="form-field">

                  <label htmlFor="doctor-consultation-notes">
                    Consultation Notes
                  </label>

                  <textarea
                    id="doctor-consultation-notes"
                    rows={5}
                    value={
                      consultation.consultation_notes
                    }
                    onChange={(event) =>
                      updateConsultationField(
                        "consultation_notes",
                        event.target.value,
                      )
                    }
                    disabled={
                      normalizeStatus(
                        selectedPatient?.status,
                      ) !==
                      "in_consultation"
                    }
                    placeholder="Record important observations and consultation notes..."
                  />

                </div>


                {/* PRESCRIPTION */}

                <div className="form-field">

                  <label htmlFor="doctor-prescription">
                    Prescription
                  </label>

                  <textarea
                    id="doctor-prescription"
                    rows={5}
                    value={
                      consultation.prescription
                    }
                    onChange={(event) =>
                      updateConsultationField(
                        "prescription",
                        event.target.value,
                      )
                    }
                    disabled={
                      normalizeStatus(
                        selectedPatient?.status,
                      ) !==
                      "in_consultation"
                    }
                    placeholder="Enter medicines, dosage, and duration..."
                  />

                </div>


                {/* TREATMENT ADVICE */}

                <div className="form-field">

                  <label htmlFor="doctor-treatment-advice">
                    Treatment / Advice
                  </label>

                  <textarea
                    id="doctor-treatment-advice"
                    rows={5}
                    value={
                      consultation.treatment_advice
                    }
                    onChange={(event) =>
                      updateConsultationField(
                        "treatment_advice",
                        event.target.value,
                      )
                    }
                    disabled={
                      normalizeStatus(
                        selectedPatient?.status,
                      ) !==
                      "in_consultation"
                    }
                    placeholder="Enter follow-up instructions, lifestyle advice, or treatment guidance..."
                  />

                </div>


                {/* FORM ACTIONS */}

                {normalizeStatus(
                  selectedPatient?.status,
                ) ===
                  "in_consultation" && (

                  <div className="consultation-actions">

                    <button
                      className="mini-button save-consultation-button"
                      disabled={
                        consultationSaving ||
                        actionLoading ===
                          `complete-${selectedPatient?.token_number}`
                      }
                      onClick={handleSaveConsultation}
                    >
                      {consultationSaving
                        ? "Saving..."
                        : consultationSaved
                          ? "✓ Consultation Saved!"
                          : "Save Consultation"}
                    </button>


                    <button
                      className="mini-button complete-button"
                      disabled={
                        consultationSaving ||
                        actionLoading ===
                          `complete-${selectedPatient?.token_number}`
                      }
                      onClick={() =>
                        handleCompleteConsultation(selectedPatient)
                      }
                    >
                      {actionLoading ===
                      `complete-${selectedPatient?.token_number}`
                        ? "Completing..."
                        : "Complete Consultation"}
                    </button>

                  </div>

                )}



                {normalizeStatus(
                  selectedPatient?.status,
                ) === "called" && (

                  <div className="consultation-status-message">

                    <strong>
                      Patient has been called.
                    </strong>

                    <span>
                      Start the consultation from the queue
                      before entering doctor notes.
                    </span>

                  </div>

                )}

              </div>

            )}

          </div>

        </section>

      )}


      {/* ====================================================
          SKIPPED QUEUE
          ==================================================== */}

      <section className="queue-section skipped-patients-section">

        <div className="section-heading">

          <div>

            <p className="eyebrow">
              SKIPPED QUEUE
            </p>

            <h2>
              Skipped Patients
            </h2>

            <p className="muted">
              Patients skipped by you remain here
              until they are added back to the queue.
            </p>

          </div>

          <span className="skipped-count">
            {skippedPatients.length}
          </span>

        </div>


        {skippedPatients.length === 0 ? (

          <div className="empty-card skipped-empty-card">

            <h2>
              No skipped patients
            </h2>

            <p className="muted">
              Patients you skip will appear here.
            </p>

          </div>

        ) : (

          <div className="queue-table-wrap">

            <table className="queue-table skipped-table">

              <thead>

                <tr>

                  <th>
                    Token
                  </th>

                  <th>
                    Patient
                  </th>

                  <th>
                    Department
                  </th>

                  <th>
                    Status
                  </th>

                  <th>
                    Action
                  </th>

                </tr>

              </thead>


              <tbody>

                {skippedPatients.map(
                  (patient) => {

                    const token =
                      patient?.token_number;

                    const actionKey =
                      `requeue-${token}`;


                    return (

                      <tr
                        key={
                          patient?._id ||
                          patient?.id ||
                          `skipped-${token}`
                        }
                      >

                        <td>

                          <strong>
                            {
                              formatToken(
                                token,
                              )
                            }
                          </strong>

                        </td>


                        <td>

                          <span className="doctor-patient-email">
                            {
                              patient?.patient_email ||
                              "—"
                            }
                          </span>

                        </td>


                        <td>
                          {
                            patient?.department ||
                            "—"
                          }
                        </td>


                        <td>

                          <span className="status-badge status-skipped">
                            Skipped
                          </span>

                        </td>


                        <td>

                          <button
                            className="mini-button requeue-button"
                            disabled={
                              actionLoading ===
                              actionKey
                            }
                            onClick={() =>
                              handleRequeue(
                                patient,
                              )
                            }
                          >

                            {actionLoading ===
                            actionKey
                              ? "Adding..."
                              : "Add to Queue"}

                          </button>

                        </td>

                      </tr>

                    );

                  },
                )}

              </tbody>

            </table>

          </div>

        )}

      </section>

      {/* ====================================================
          PAST MEDICAL RECORDS MODAL
          ==================================================== */}
      {historyModalPatient && (
        <div className="admin-modal-backdrop" onClick={closeDoctorHistoryModal}>
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
                onClick={closeDoctorHistoryModal}
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
                onClick={closeDoctorHistoryModal}
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

