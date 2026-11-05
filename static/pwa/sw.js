/* LottoBooM Service Worker — v3 (2026-11-02)
 * Cache strategy:
 *  - HTML: network-first (siempre busca la versión nueva primero)
 *  - Assets estáticos (png, css, js): cache-first con fallback
 *  - NO cachea páginas dinámicas (/, /dashboard/, etc.)
 */
const CACHE_NAME = 'lottoboom-v3-2026-11-02';
const STATIC_ASSETS = [
    '/static/pwa/favicon.ico',
    '/static/pwa/favicon-32x32.png',
    '/static/pwa/favicon-16x16.png',
    '/static/pwa/apple-touch-icon.png',
    '/static/pwa/android-chrome-192x192.png',
    '/static/pwa/android-chrome-512x512.png',
];

/* Install: pre-cachear solo assets estáticos */
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();  // Forzar activación inmediata
});

/* Activate: borrar TODOS los caches viejos */
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.map(k => {
                if (k !== CACHE_NAME) {
                    console.log('[SW] Borrando cache viejo:', k);
                    return caches.delete(k);
                }
            }))
        ).then(() => self.clients.claim())
    );
});

/* Fetch: network-first para HTML, cache-first para assets estáticos */
self.addEventListener('fetch', (event) => {
    const req = event.request;
    const url = new URL(req.url);

    // Solo manejar mismo origen
    if (url.origin !== location.origin) return;

    // Métodos distintos a GET: dejar pasar (POST, etc.)
    if (req.method !== 'GET') return;

    // HTML / navegación → NETWORK FIRST (siempre la versión más nueva)
    const isHTML = req.headers.get('accept')?.includes('text/html') ||
                   url.pathname === '/' ||
                   url.pathname.endsWith('/');

    if (isHTML) {
        event.respondWith(
            fetch(req).then(resp => {
                // No cachear HTML — siempre red
                return resp;
            }).catch(() => {
                // Sin red: intentar cache
                return caches.match(req).then(cached => cached || caches.match('/'));
            })
        );
        return;
    }

    // Assets estáticos (imagen, css, js) → CACHE FIRST
    if (url.pathname.startsWith('/static/') ||
        /\.(png|jpg|jpeg|gif|svg|ico|css|js|woff2?|ttf)$/.test(url.pathname)) {
        event.respondWith(
            caches.match(req).then(cached => {
                if (cached) return cached;
                return fetch(req).then(resp => {
                    if (resp.ok) {
                        const clone = resp.clone();
                        caches.open(CACHE_NAME).then(c => c.put(req, clone));
                    }
                    return resp;
                });
            })
        );
        return;
    }

    // Todo lo demás: NETWORK FIRST (sin cache)
    event.respondWith(fetch(req).catch(() => caches.match(req)));
});
