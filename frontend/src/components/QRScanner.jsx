import { useEffect, useRef } from "react";
import {
  Html5Qrcode,
  Html5QrcodeScannerState,
} from "html5-qrcode";

import "./QRScanner.css";


export default function QRScanner({
  onScan,
  onError,
}) {
  const scannerRef = useRef(null);
  const startPromiseRef = useRef(null);

  const mountedRef = useRef(false);
  const scanHandledRef = useRef(false);


  const onScanRef = useRef(onScan);
  const onErrorRef = useRef(onError);


  // ============================================================
  // KEEP CALLBACKS UPDATED
  // ============================================================

  useEffect(() => {
    onScanRef.current = onScan;
  }, [onScan]);


  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);


  // ============================================================
  // START SCANNER
  // ============================================================

  useEffect(() => {

    mountedRef.current = true;
    scanHandledRef.current = false;


    const readerElement =
      document.getElementById("qr-reader");


    if (!readerElement) {
      console.error(
        "QR reader element not found.",
      );

      return;
    }


    const scanner =
      new Html5Qrcode("qr-reader");


    scannerRef.current = scanner;


    const startScanner = async () => {

      try {

        /*
         * Save the start promise.
         * Cleanup can wait for it before
         * attempting to stop the scanner.
         */

        startPromiseRef.current =
            scanner.start(
                {
                facingMode: "environment",
                },
                {
                fps: 10,

                qrbox: {
                    width: 250,
                    height: 250,
                },

                disableFlip: false,
                },

            (decodedText) => {

              if (
                !mountedRef.current ||
                scanHandledRef.current
              ) {
                return;
              }


              scanHandledRef.current = true;


              onScanRef.current?.(
                decodedText,
              );
            },

            () => {
              // Ignore normal QR decoding failures.
            },
          );


        await startPromiseRef.current;


        /*
         * Component may have been removed while
         * the camera was starting.
         */

        if (!mountedRef.current) {

          await safelyStopScanner(
            scanner,
          );

          return;
        }

      } catch (error) {

        /*
         * AbortError can happen when the
         * camera element is removed during
         * React development remounting.
         */

        if (
          error?.name === "AbortError" ||
          String(error).includes(
            "media was removed",
          )
        ) {
          console.warn(
            "QR scanner startup was interrupted.",
          );

          return;
        }


        console.error(
          "QR scanner start error:",
          error,
        );


        if (mountedRef.current) {

          onErrorRef.current?.(
            "Unable to access the camera. Please allow camera permission and try again.",
          );
        }

      }

    };


    startScanner();


    // ==========================================================
    // CLEANUP
    // ==========================================================

    return () => {

      mountedRef.current = false;


      const currentScanner =
        scannerRef.current;


      if (!currentScanner) {
        return;
      }


      const cleanupScanner =
        async () => {

          /*
           * Wait until start() finishes.
           * This prevents calling stop()
           * while the scanner is still starting.
           */

          try {

            if (
              startPromiseRef.current
            ) {
              await startPromiseRef.current;
            }

          } catch {
            /*
             * start() may fail because the
             * component was removed.
             */
          }


          await safelyStopScanner(
            currentScanner,
          );

        };


      cleanupScanner();

    };

  }, []);


  return (
    <div className="qr-scanner-wrapper">

      <div
        id="qr-reader"
        className="qr-reader-container"
      />

      <p className="muted scanner-help">
        Point your camera at the hospital
        queue QR code.
      </p>

    </div>
  );
}


// ============================================================
// SAFE STOP FUNCTION
// ============================================================

async function safelyStopScanner(
  scanner,
) {

  try {

    const state =
      scanner.getState();


    /*
     * Only call stop() when the scanner
     * is actually running.
     */

    if (
      state ===
      Html5QrcodeScannerState.SCANNING
    ) {

      await scanner.stop();

    }

  } catch (error) {

    /*
     * Ignore expected cleanup races.
     */

    if (
      !String(error).includes(
        "Cannot stop",
      )
    ) {
      console.warn(
        "QR scanner cleanup:",
        error,
      );
    }

  }


  try {

    scanner.clear();

  } catch {
    // Ignore DOM cleanup errors.
  }
}