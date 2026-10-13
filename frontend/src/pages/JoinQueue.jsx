import {
  useEffect,
  useState,
} from "react";

import {
  useNavigate,
} from "react-router-dom";

import AppNav from "../components/AppNav";

import "./JoinQueue.css";

import {
  getAvailableDoctors,
  joinQueue,
  logout,
} from "../api";


// ============================================================
// DEPARTMENTS
// ============================================================

const DEPARTMENTS = [
  "General",
  "Cardiology",
  "Orthopedics",
  "Pediatrics",
  "Neurology",
];


// ============================================================
// JOIN QUEUE
// ============================================================

export default function JoinQueue() {

  const navigate =
    useNavigate();


 const [
  department,
  setDepartment,
] = useState("");

  const [
    doctors,
    setDoctors,
  ] = useState([]);


  const [
    selectedDoctor,
    setSelectedDoctor,
  ] = useState("");


  const [
    loadingDoctors,
    setLoadingDoctors,
  ] = useState(true);


  const [
    joining,
    setJoining,
  ] = useState(false);


  const [
    error,
    setError,
  ] = useState("");


  const [
    success,
    setSuccess,
  ] = useState(null);



  // ==========================================================
  // LOAD DOCTORS
  // ==========================================================

  async function loadDoctors(
    selectedDepartment,
  ) {

    try {

      setLoadingDoctors(true);

      setError("");

      setSelectedDoctor("");

      const data =
        await getAvailableDoctors(
          selectedDepartment,
        );


      const doctorList =
        Array.isArray(data)
          ? data
          : data?.doctors || [];


      setDoctors(
        doctorList,
      );


      /*
       * Automatically select the first
       * available doctor.
       */

      const firstAvailable =
        doctorList.find(
          (doctor) =>
            doctor.availability === "available"
            || doctor.available === true,
        );


      if (firstAvailable) {

        setSelectedDoctor(
          firstAvailable.email,
        );

      }

    } catch (err) {

      console.error(
        "Doctor loading error:",
        err,
      );

      if (err?.status === 401) {
        logout();
        navigate("/login", { replace: true });
        return;
      }

      setDoctors([]);

      setError(
        err?.message ||
        "Unable to load doctors.",
      );

    } finally {

      setLoadingDoctors(false);

    }

  }


  // ==========================================================
  // INITIAL DOCTOR LOAD
  // ==========================================================

  useEffect(() => {
  if (!department) {
    setDoctors([]);
    setSelectedDoctor("");
    setLoadingDoctors(false);
    return;
  }

  loadDoctors(department);
}, [department]);



  // ==========================================================
  // JOIN QUEUE
  // ==========================================================

async function handleSubmit(
  event,
) {

  event.preventDefault();

  setError("");

  setSuccess(null);

  if (!department) {

    setError(
      "Please select a department.",
    );

    return;
  }

  if (!selectedDoctor) {

    setError(
      "Please select an available doctor.",
    );

    return;
  }

  const doctor = doctors.find(
    (item) => item.email === selectedDoctor,
  );

  const doctorIsAvailable =
    doctor?.availability === "available"
    || doctor?.available === true;

  if (!doctor || !doctorIsAvailable) {

    setError(
      doctor?.availability_reason
        || "The selected doctor is no longer available. Please select another doctor.",
    );

    await loadDoctors(department);

    return;
  }

  try {

    setJoining(true);

    const queue = await joinQueue(
      department,
      selectedDoctor,
    );

    setSuccess(queue);

  } catch (err) {

    console.error(
      "Join queue error:",
      err,
    );

    if (err?.status === 401) {

      logout();

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
      "Unable to join the queue.",
    );

  } finally {

    setJoining(false);

  }
}


  // ==========================================================
  // SUCCESS VIEW
  // ==========================================================

  if (success) {

    return (

      <main className="join-queue-page">

        <AppNav />


        <section className="join-queue-card">

          <p className="eyebrow">
            QUEUE JOINED
          </p>


          <h1>
            You are in the queue
          </h1>


          <div className="join-success-icon">
            ✓
          </div>


          <div className="queue-created-summary">

            <div className="queue-created-item">

              <span>
                Token
              </span>

              <strong>

                #
                {String(
                  success.token_number,
                ).padStart(
                  3,
                  "0",
                )}

              </strong>

            </div>


            <div className="queue-created-item">

              <span>
                Department
              </span>

              <strong>
                {success.department}
              </strong>

            </div>


            <div className="queue-created-item">

              <span>
                Doctor
              </span>

              <strong>
                {success.doctor_email}
              </strong>

            </div>


            <div className="queue-created-item">

              <span>
                Status
              </span>

              <strong>
                Waiting for nurse Assessment
              </strong>

            </div>

          </div>


          <div className="alert success queue-created-alert">
            <p className="queue-alert-title">Your queue entry has been created.</p>
            <p className="queue-alert-row">Please wait for the nurse to complete your assessment.</p>
            <p className="queue-alert-row">After the assessment, Reception will provide your official QR code.</p>
          </div>


          <div className="dashboard-actions">
            <button
              className="button primary"
              onClick={() =>
                navigate("/patient-dashboard")
              }
            >
              Go to My Queue
            </button>

            <button
              type="button"
              className="button secondary waiting-button"
              disabled
            >
              Waiting for Nurse Assessment
            </button>
          </div>

        </section>

      </main>

    );

  }


  // ==========================================================
  // FORM
  // ==========================================================

  return (

    <main className="join-queue-page">

      <AppNav />


      <section className="join-queue-card">

        <div className="join-queue-header">

          <p className="eyebrow">
            QUEUE ACCESS
          </p>


          <h1>
            Join Hospital Queue
          </h1>


          <p className="muted">

            Select your department and an
            available doctor.

          </p>

        </div>


        {/* ==================================================
            ERROR
            ================================================== */}

        {error && (

          <div className="alert danger">
            {error}
          </div>

        )}


        <form
          className="join-queue-form"
          onSubmit={
            handleSubmit
          }
        >

          {/* ================================================
              DEPARTMENT
              ================================================ */}

          <div className="form-group">

            <label htmlFor="department">
              Department
            </label>


            <select
              id="department"
              value={department}
              onChange={(event) =>
                setDepartment(
                  event.target.value,
                )
              }
              required
              disabled={
                joining ||
                loadingDoctors
              }
            >

              <option value="" disabled>
                Select Department
              </option>

              {DEPARTMENTS.map(
                (item) => (

                  <option
                    key={item}
                    value={item}
                  >
                    {item}
                  </option>

                ),
              )}

            </select>

          </div>


          {/* ================================================
              DOCTORS
              ================================================ */}

          <div className="form-group">

            <label>
              Available Doctors
            </label>


            {loadingDoctors ? (

              <div className="loading-card">

                Loading available doctors...

              </div>

            ) : doctors.length === 0 ? (

              <div className="empty-card">

                <h2>
                  No doctors found
                </h2>

                <p className="muted">

                  No doctors are currently
                  associated with this department.

                </p>

              </div>

            ) : (

              <div className="doctor-selection-list">

                {doctors.map(
                  (doctor) => {

                    const availability =
                      doctor.availability
                      || (doctor.available === true
                        ? "available"
                        : "busy");

                    const available =
                      availability === "available";

                    const selected =
                      selectedDoctor ===
                      doctor.email;


                    return (

                      <button
                        key={
                          doctor.email
                        }
                        type="button"
                        className={`doctor-option ${
                          selected
                            ? "selected"
                            : ""
                        } ${
                          !available
                            ? "unavailable"
                            : ""
                        }`}
                        disabled={
                          joining ||
                          !available
                        }
                        onClick={() => {

                          if (
                            available
                          ) {

                            setSelectedDoctor(
                              doctor.email,
                            );

                          }

                        }}
                      >

                        <div className="doctor-option-main">

                          <strong>
                            Dr.{" "}
                            {doctor.name ||
                              doctor.email}
                          </strong>


                          <span>
                            {doctor.email}
                          </span>

                        </div>


                        <div
                          className={`doctor-availability ${availability}`}
                        >

                          <span>●</span>

                          {availability === "available"
                            ? "Available"
                            : availability === "busy"
                              ? "Busy"
                              : "Unavailable"}
                        </div>

                        <div className="doctor-capacity">
                          {Number(doctor.queue_count || 0)} / {Number(doctor.queue_capacity || 25)} patients
                        </div>

                        {(doctor.shift_start || doctor.shift_end) && (
                          <div className="doctor-shift">
                            Shift: {doctor.shift_start || "--:--"} – {doctor.shift_end || "--:--"}
                          </div>
                        )}

                        {doctor.availability_reason && (
                          <div className="doctor-availability-reason">
                            {doctor.availability_reason}
                          </div>
                        )}

                      </button>

                    );

                  },
                )}

              </div>

            )}

          </div>


          {/* ================================================
              SELECTED DOCTOR
              ================================================ */}

          {selectedDoctor && (

            <div className="selected-doctor-card">

              <span className="card-label">
                SELECTED DOCTOR
              </span>


              <strong>
                {selectedDoctor}
              </strong>


              <p className="muted">
                {department}
              </p>

            </div>

          )}


          {/* ================================================
              SUBMIT
              ================================================ */}

          <button
            type="submit"
            className="button primary join-submit-button"
            disabled={
              joining ||
              loadingDoctors ||
              !selectedDoctor
            }
          >

            {joining
              ? "Joining Queue..."
              : "Join Queue"}

          </button>


          <button
            type="button"
            className="button secondary"
            disabled={joining}
            onClick={() =>
              navigate(
                "/patient-dashboard",
              )
            }
          >
            Back to My Queue
          </button>

        </form>

      </section>

    </main>

  );

}