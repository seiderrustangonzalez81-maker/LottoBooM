// Service Worker — LottoBooM
const CACHE = 'lottoboom-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

// Network-first: siempre intenta traer lo más nuevo, si falla usa caché
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});

// Notificaciones push (opcional, para más adelante)
self.addEventListener('push', (event) => {
  let data = { title: 'LottoBooM', body: 'Nuevo mensaje' };
  if (event.data) {
    try { data = event.data.json(); } catch (e) { data.body = event.data.text(); }
  }
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/static/pwa/icon-192.png',
      badge: '/static/pwa/icon-192.png'
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow('/'));
});
