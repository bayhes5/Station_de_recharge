document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("login-form");
    const status = document.getElementById("login-status");
    const nextUrl = new URLSearchParams(window.location.search).get("next");
    const allowedNextPaths = new Set([
        "/admin-dashboard.html",
        "/admin-form.html",
        "/admin-station.html",
        "/dashboard.html",
        "/mobile-session.html",
        "/profile.html",
        "/reservation.html",
        "/technician-dashboard.html",
    ]);
    const safeNextUrl = (() => {
        if (!nextUrl) {
            return "";
        }
        try {
            const parsed = new URL(nextUrl, window.location.origin);
            const relativePath = `${parsed.pathname}${parsed.search}${parsed.hash}`;
            return parsed.origin === window.location.origin && allowedNextPaths.has(parsed.pathname)
                ? relativePath
                : "";
        } catch (_error) {
            return "";
        }
    })();

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        status.classList.remove("error");
        status.textContent = "";
        const submitButton = form.querySelector('button[type="submit"]');
        submitButton.disabled = true;

        const payload = {
            identifiant: form.identifiant.value.trim(),
            password: form.password.value,
        };

        if (!payload.identifiant || !payload.password) {
            status.classList.add("error");
            status.textContent = "Le pseudo/e-mail et le mot de passe sont obligatoires.";
            submitButton.disabled = false;
            return;
        }

        try {
            const result = await window.AuthAPI.login(payload);
            window.AuthAPI.setTokens(result);
            status.textContent = "Connexion réussie.";
            window.setTimeout(() => {
                if (result.user?.must_change_password) {
                    window.location.href = "/profile.html?force_password_change=1";
                } else if (safeNextUrl) {
                    window.location.href = safeNextUrl;
                } else if (result.user?.is_staff) {
                    window.location.href = "/admin-dashboard.html";
                } else if (result.user?.is_technician) {
                    window.location.href = "/technician-dashboard.html";
                } else {
                    window.location.href = "/dashboard.html";
                }
            }, 800);
        } catch (error) {
            status.classList.add("error");
            status.textContent = error.status === 401
                ? "Identifiants invalides."
                : error.message || "Connexion impossible.";
        } finally {
            submitButton.disabled = false;
        }
    });
});
