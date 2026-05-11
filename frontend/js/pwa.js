function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) {
        return;
    }

    window.addEventListener("load", () => {
        navigator.serviceWorker.register("/sw.js").catch(() => {
            // The app remains fully usable when service workers are unavailable.
        });
    });
}

registerServiceWorker();
