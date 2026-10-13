/* eslint-disable no-undef */
// Firebase Cloud Messaging Service Worker for Care+

// Give the service worker access to Firebase Messaging.
// Note that you can only use Firebase Messaging here. Other Firebase libraries
// are not available in the service worker.
importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-messaging-compat.js');

// Initialize the Firebase app in the service worker by passing in the messagingSenderId.
firebase.initializeApp({
  apiKey: "AIzaSyCKPVW6ASYAPOgU4pfmTsgKzfSDDhr9rWE",
  authDomain: "carepluse-5d705.firebaseapp.com",
  projectId: "carepluse-5d705",
  storageBucket: "carepluse-5d705.firebasestorage.app",
  messagingSenderId: "698475780736",
  appId: "1:698475780736:web:9d26aa97b3d80f043f2465",
  measurementId: "G-8YSGJ56BVF"
});

// Retrieve an instance of Firebase Messaging so that it can handle background messages.
const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
  console.log('[firebase-messaging-sw.js] Received background message:', payload);

  const notificationTitle = payload.notification?.title || payload.data?.title || 'Care+ Queue Alert';
  const notificationOptions = {
    body: payload.notification?.body || payload.data?.body || 'You have an update regarding your queue status.',
    icon: '/logo.png',
    badge: '/logo.png',
    data: payload.data || {},
    tag: payload.data?.tag || 'careplus-queue-update',
    renotify: true
  };

  self.registration.showNotification(notificationTitle, notificationOptions);
});

// Handle notification click to bring patient back into Care+
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const clickAction = event.notification.data?.click_action || '/patient-dashboard';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      // Check if there is already a window open with this app
      for (let client of windowClients) {
        if (client.url.includes(clickAction) && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(clickAction);
      }
    })
  );
});
