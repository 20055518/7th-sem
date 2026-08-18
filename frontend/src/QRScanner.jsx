import { useEffect, useRef } from "react";
import { Html5Qrcode } from "html5-qrcode";

export default function QRScanner({ onScan }) {
  const onScanRef = useRef(onScan);

  onScanRef.current = onScan;

  useEffect(() => {
    let mounted = true;
    const scanner = new Html5Qrcode("qr-reader");

    const startScanner = async () => {
      try {
        await scanner.start(
          { facingMode: "environment" },
          {
            fps: 10,
            qrbox: { width: 250, height: 250 },
          },
          (decodedText) => {
            if (mounted) {
              onScanRef.current(decodedText);
            }
          },
          () => {},
        );

        if (!mounted && scanner.isScanning) {
          await scanner.stop();
        }
      } catch (error) {
        if (mounted) {
          console.error("Unable to start QR scanner:", error);
        }
      }
    };

    startScanner();

    return () => {
      mounted = false;

      if (scanner.isScanning) {
        scanner
          .stop()
          .then(() => scanner.clear())
          .catch(() => {});
      }
    };
  }, []);

  return <div id="qr-reader" />;
}