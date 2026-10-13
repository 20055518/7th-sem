import { initializeApp, getApps, getApp } from "firebase/app";
import { getAnalytics, isSupported as isAnalyticsSupported } from "firebase/analytics";
import { getMessaging, getToken, onMessage, isSupported as isMessagingSupported } from "firebase/messaging";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "AIzaSyCKPVW6ASYAPOgU4pfmTsgKzfSDDhr9rWE",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "carepluse-5d705.firebaseapp.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "carepluse-5d705",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "carepluse-5d705.firebasestorage.app",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "698475780736",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:698475780736:web:9d26aa97b3d80f043f2465",
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID || "G-8YSGJ56BVF"
};

// Initialize or reuse Firebase App
const app = !getApps().length ? initializeApp(firebaseConfig) : getApp();

// Conditionally init analytics (client-side only)
let analytics = null;
if (typeof window !== "undefined") {
  isAnalyticsSupported().then((supported) => {
    if (supported) {
      analytics = getAnalytics(app);
    }
  }).catch(() => {});
}

/**
 * Request notification permission and retrieve the FCM registration token.
 * Registers / reuses the service worker at /firebase-messaging-sw.js.
 */
export async function requestNotificationPermissionAndGetToken() {
  try {
    if (typeof window === "undefined" || !("Notification" in window)) {
      console.warn("Notifications are not supported in this browser environment.");
      return null;
    }

    const messagingSupported = await isMessagingSupported();
    if (!messagingSupported) {
      console.warn("Firebase Messaging is not supported in this browser.");
      return null;
    }

    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      console.warn("Notification permission was not granted:", permission);
      return null;
    }

    // Register service worker if available
    let swRegistration = null;
    if ("serviceWorker" in navigator) {
      swRegistration = await navigator.serviceWorker.register("/firebase-messaging-sw.js", {
        scope: "/"
      });
      await navigator.serviceWorker.ready;
    }

    const messaging = getMessaging(app);
    const vapidKey = import.meta.env.VITE_FIREBASE_VAPID_KEY || undefined;

    const tokenOptions = {
      serviceWorkerRegistration: swRegistration || undefined
    };
    if (vapidKey) {
      tokenOptions.vapidKey = vapidKey;
    }

    const currentToken = await getToken(messaging, tokenOptions);
    if (currentToken) {
      return currentToken;
    } else {
      console.warn("No registration token available. Request permission to generate one.");
      return null;
    }
  } catch (error) {
    console.error("An error occurred while retrieving FCM token:", error);
    return null;
  }
}

/**
 * Listen for foreground FCM push notifications.
 * @param {Function} callback - invoked with payload when a message arrives in foreground.
 * @returns {Function|null} unsubscribe function or null
 */
export function onForegroundMessageListener(callback) {
  try {
    if (typeof window === "undefined") return () => {};
    const messaging = getMessaging(app);
    return onMessage(messaging, (payload) => {
      console.log("Foreground FCM message received:", payload);
      if (typeof callback === "function") {
        callback(payload);
      }
    });
  } catch (error) {
    console.warn("Could not set up onForegroundMessageListener:", error);
    return () => {};
  }
}

export { app, analytics };