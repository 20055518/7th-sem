import { useState } from "react";
import { useNavigate } from "react-router-dom";

import AppNav from "../components/AppNav";

import QRScanner from "../components/QRScanner";

import {
  verifyQr,
  getMyQueue,
  getPublicDepartmentQueue,
} from "../api";

import "./QueueAccess.css";


/* ============================================================
   QUEUE ACCESS / QR VERIFICATION
   ============================================================ */

export default function QueueAccess() {

  const navigate = useNavigate();


  /* ==========================================================
     STATE
     ========================================================== */

  const [
    scanning,
    setScanning,
  ] = useState(true);


  const [
    loading,
    setLoading,
  ] = useState(false);


  const [
    error,
    setError,
  ] = useState("");


  const [
    result,
    setResult,
  ] = useState(null);


  const [
    queueDetails,
    setQueueDetails,
  ] = useState(null);


  const [
    publicQueue,
    setPublicQueue,
  ] = useState([]);


  const [
    publicQueueError,
    setPublicQueueError,
  ] = useState("");


  const [
    manualCode,
    setManualCode,
  ] = useState("");


  /* ==========================================================
     HANDLE QR SCAN
     ========================================================== */

  async function handleScan(
    scannedValue,
  ) {

    if (
      !scanning ||
      loading
    ) {
      return;
    }


    setScanning(false);

    setLoading(true);

    setError("");

    setPublicQueueError("");

    setResult(null);

    setQueueDetails(null);

    setPublicQueue([]);


    try {

      /* ======================================================
         STEP 1
         VERIFY QR
         ====================================================== */

      const verification =
        await verifyQr(
          scannedValue,
        );


      if (
        !verification ||
        verification.valid !== true
      ) {

        throw new Error(
          "Invalid or expired QR code.",
        );

      }


      /* ======================================================
         SAVE DEPARTMENT
         ====================================================== */

      if (
        verification.department
      ) {

        sessionStorage.setItem(
          "queue_department",
          verification.department,
        );

      }


      /* ======================================================
         STEP 2
         SAVE VERIFICATION RESULT
         ====================================================== */

      setResult(
        verification,
      );


      /* ======================================================
         STEP 3
         LOAD PATIENT QUEUE
         ====================================================== */

      const ownQueue =
        await getMyQueue();


      setQueueDetails(
        ownQueue,
      );


      /* ======================================================
         STEP 4
         LOAD PUBLIC QUEUE
         ====================================================== */

      const department =
        ownQueue?.department ||
        verification?.department;


      if (
        department
      ) {

        try {

          const publicData =
            await getPublicDepartmentQueue(
              department,
            );


          const liveQueue =
            Array.isArray(
              publicData,
            )
              ? publicData
              : publicData?.queue ||
                [];


          setPublicQueue(
            liveQueue,
          );

        } catch (
          publicError
        ) {

          console.error(
            "Unable to load public queue:",
            publicError,
          );


          setPublicQueueError(
            "Your queue is verified, but the live public queue could not be loaded.",
          );

        }

      }

    } catch (
      scanError
    ) {

      console.error(
        "QR verification failed:",
        scanError,
      );


      setError(
        scanError?.message ||
        "QR verification failed. Please scan the official hospital queue QR code.",
      );


      setScanning(true);

    } finally {

      setLoading(false);

    }

  }


  function handleManualSubmit(event) {

    event.preventDefault();

    const code = manualCode.trim();

    if (!code) {

      setError(
        "Enter the one-time verification code from reception.",
      );

      return;

    }

    handleScan(code);

  }


  /* ==========================================================
     SCAN ANOTHER
     ========================================================== */

  function handleScanAnother() {

    setResult(null);

    setQueueDetails(null);

    setPublicQueue([]);

    setError("");

    setPublicQueueError("");

    setScanning(true);

  }


  /* ==========================================================
     OPEN PATIENT DASHBOARD
     ========================================================== */

  function goToDashboard() {

    navigate(
      "/patient-dashboard",
    );

  }


  /* ==========================================================
     FORMAT TOKEN
     ========================================================== */

  function formatToken(
    token,
  ) {

    if (
      token === null ||
      token === undefined
    ) {

      return "--";

    }


    return `#${String(
      token,
    ).padStart(
      3,
      "0",
    )}`;

  }


  /* ==========================================================
     FORMAT STATUS
     ========================================================== */

  function formatStatus(
    status,
  ) {

    if (!status) {
      return "Unknown";
    }


    return String(
      status,
    )
      .replaceAll(
        "_",
        " ",
      )
      .replace(
        /\b\w/g,
        (letter) =>
          letter.toUpperCase(),
      );

  }


  /* ==========================================================
     LOADING
     ========================================================== */

  if (
    loading
  ) {

    return (

      <main className="queue-access-page">

        <AppNav />


        <header className="page-header">

          <div>

            <p className="eyebrow">
              QR CHECK
            </p>

            <h1>
              Scan Queue QR
            </h1>

            <p className="muted">
              Verifying your hospital
              queue access...
            </p>

          </div>

        </header>


        <section className="scanner-card">

          <div className="scanner-loading">

            <div className="scanner-loading-icon">
              QR
            </div>

            <h2>
              Verifying QR code
            </h2>

            <p className="muted">
              Please wait while we verify
              your queue access.
            </p>

          </div>

        </section>

      </main>

    );

  }


  /* ==========================================================
     VERIFIED RESULT
     ========================================================== */

  if (
    result &&
    queueDetails
  ) {

    const token =
      queueDetails?.token_number ??
      result?.token_number;


    const department =
      queueDetails?.department ||
      result?.department ||
      "Unknown";


    const doctor =
      queueDetails?.doctor_email ||
      "Not assigned";


    const status =
      queueDetails?.status ||
      result?.status ||
      "";


    return (

      <main className="queue-access-page">

        <AppNav />


        <header className="page-header">

          <div>

            <p className="eyebrow">
              QR VERIFIED
            </p>

            <h1>
              Queue Access Granted
            </h1>

            <p className="muted">
              Your queue QR has been
              successfully verified.
            </p>

          </div>

        </header>


        <section className="qr-result-card">

          <div className="verification-icon">
            ✓
          </div>


          <p className="eyebrow">
            SECURE ACCESS
          </p>


          <h2>
            QR verified successfully
          </h2>


          <p className="muted">
            This queue belongs to your
            patient account.
          </p>


          <div className="patient-summary">

            <article className="token-card">

              <span>
                Token
              </span>

              <strong>
                {formatToken(
                  token,
                )}
              </strong>

            </article>


            <article className="summary-card">

              <span>
                Department
              </span>

              <strong>
                {department}
              </strong>

            </article>


            <article className="summary-card">

              <span>
                Doctor
              </span>

              <strong>
                {doctor}
              </strong>

            </article>


            <article className="summary-card">

              <span>
                Status
              </span>

              <strong>
                {formatStatus(
                  status,
                )}
              </strong>

            </article>

          </div>


          <div className="dashboard-actions">

            <button
              className="button primary"
              onClick={
                goToDashboard
              }
            >
              Open My Queue
            </button>


            <button
              className="button secondary"
              onClick={
                handleScanAnother
              }
            >
              Scan Another
            </button>

          </div>

        </section>


        <section className="public-queue-section">

          <div className="section-heading">

            <div>

              <p className="eyebrow">
                LIVE QUEUE
              </p>

              <h2>
                {department} Queue
              </h2>

            </div>


            <span className="live-pill">
              ● Live
            </span>

          </div>


          <p className="muted">
            Other patients are shown
            only by queue token.
          </p>


          {publicQueueError && (

            <div className="alert danger">
              {publicQueueError}
            </div>

          )}


          {publicQueue.length === 0 ? (

            <div className="empty-card">

              No active patients
              in this queue.

            </div>

          ) : (

            <div className="public-queue-list">

              {publicQueue.map(
                (entry) => {

                  const isOwn =
                    String(
                      entry?.token_number,
                    ) ===
                    String(token);


                  const entryStatus =
                    formatStatus(
                      entry?.status,
                    );


                  return (

                    <div
                      key={
                        `${entry?.token_number}-${entryStatus}`
                      }
                      className={`public-queue-row ${
                        isOwn
                          ? "own-queue-row"
                          : ""
                      }`}
                    >

                      <div>

                        <span>
                          Token
                        </span>

                        <strong>
                          {formatToken(
                            entry?.token_number,
                          )}
                        </strong>

                      </div>


                      <div>

                        <span>
                          Position
                        </span>

                        <strong>
                          {entry?.position ??
                            "--"}
                        </strong>

                      </div>


                      <div>

                        <span>
                          Status
                        </span>

                        <strong>
                          {entryStatus}
                        </strong>

                      </div>


                      {isOwn && (

                        <span className="own-label">
                          You
                        </span>

                      )}

                    </div>

                  );

                },
              )}

            </div>

          )}

        </section>

      </main>

    );

  }


  /* ==========================================================
     SCANNER PAGE
     ========================================================== */

  return (

    <main className="queue-access-page">

      <AppNav />


      <header className="page-header">

        <div>

          <p className="eyebrow">
            QR CHECK
          </p>


          <h1>
            Scan Queue QR
          </h1>


          <p className="muted">
            Scan the official queue QR
            code provided by the
            reception desk.
          </p>

        </div>

      </header>


      {error && (

        <div className="alert danger">

          {error}

        </div>

      )}


      <section className="scanner-card">

        <div className="scanner-intro">

          <p className="eyebrow">
            SECURE QR ACCESS
          </p>


          <h2>
            Scan your queue QR
          </h2>


          <p className="muted">
            Point your camera at the QR
            code given to you by reception.
          </p>

        </div>


        <form
          className="manual-code-form"
          onSubmit={handleManualSubmit}
        >

          <label htmlFor="verification-code">
            Or enter the 6-digit code from reception
          </label>

          <div className="manual-code-actions">

            <input
              id="verification-code"
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={manualCode}
              onChange={(event) =>
                setManualCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
              autoComplete="off"
              placeholder="Enter 6-digit code (e.g. 123456)"
              style={{ letterSpacing: manualCode ? "0.18em" : "normal", fontWeight: "700" }}
            />

            <button
              type="submit"
              className="button secondary"
              disabled={loading}
            >
              Verify Code
            </button>

          </div>

        </form>


        <QRScanner
          onScan={
            handleScan
          }
          onError={
            setError
          }
        />

      </section>

    </main>

  );

}
