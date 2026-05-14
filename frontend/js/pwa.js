function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) {
        return;
    }

    const isLocalDev =
        import.meta.env?.DEV
        || ["localhost", "127.0.0.1"].includes(window.location.hostname);

    if (isLocalDev) {
        navigator.serviceWorker.getRegistrations()
            .then((registrations) => Promise.all(registrations.map((registration) => registration.unregister())))
            .then(() => (window.caches ? window.caches.keys() : []))
            .then((keys) => Promise.all((keys || []).map((key) => window.caches.delete(key))))
            .catch(() => {
                // Local development must keep working even if cache cleanup is blocked.
            });
        return;
    }

    window.addEventListener("load", () => {
        navigator.serviceWorker.register("/sw.js").catch(() => {
            // The app remains fully usable when service workers are unavailable.
        });
    });
}

registerServiceWorker();
