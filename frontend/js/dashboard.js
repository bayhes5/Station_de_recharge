function formatDateTime(value) {
    if (!value) {
        return "-";
    }

    return new Intl.DateTimeFormat("fr-FR", {
        dateStyle: "medium",
        timeStyle: "short",
    }).format(new Date(value));
}

function renderBadge(status) {
    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = status;
    return badge;
}

function renderSessionCard(session) {
    const item = document.createElement("article");
    item.className = "list-item";

    item.innerHTML = `
        <div class="list-item-head">
            <strong>${session.station}</strong>
            <span>${session.status === "active" ? "En cours" : "Terminee"}</span>
        </div>
        <p>Emplacement ${session.emplacement}</p>
        <p>Debut: ${formatDateTime(session.start_time)}</p>
        <p>Fin: ${formatDateTime(session.end_time)}</p>
    `;

    return item;
}

function renderEmpty(container, message) {
    container.innerHTML = "";
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = message;
    container.appendChild(empty);
}

document.addEventListener("DOMContentLoaded", async () => {
    const status = document.getElementById("dashboard-status");
    const logoutBtn = document.getElementById("dashboard-logout");
    const adminLink = document.getElementById("admin-link");

    logoutBtn.addEventListener("click", () => {
        window.AuthAPI.logout();
    });

    const session = await window.AuthAPI.ensureSession();
    if (!session) {
        status.classList.add("error");
        status.textContent = "Session absente ou expiree. Redirection vers la connexion.";
        window.setTimeout(() => {
            window.location.href = "/login.html";
        }, 1200);
        return;
    }

    try {
        const result = await window.AuthAPI.getDashboard();
        const user = result.user;
        const snapshot = window.AuthAPI.getSessionSnapshot();

        document.getElementById("dashboard-pseudo").textContent = user.pseudo;
        document.getElementById("dashboard-email").textContent = user.email;
        document.getElementById("dashboard-statut").textContent = user.statut || "-";

        document.getElementById("access-expiry").textContent = snapshot.accessExpired
            ? "Expire"
            : `Expire dans ${snapshot.accessReadable}`;
        document.getElementById("refresh-expiry").textContent = snapshot.refreshExpired
            ? "Expire"
            : `Expire dans ${snapshot.refreshReadable}`;

        document.getElementById("kpi-sessions-total").textContent = result.stats.sessions_total;
        document.getElementById("kpi-past-sessions").textContent = result.stats.past_sessions;
        document.getElementById("kpi-active-sessions").textContent = result.stats.active_sessions;

        const activeSessionContainer = document.getElementById("active-session");
        activeSessionContainer.innerHTML = "";
        if (result.active_session) {
            activeSessionContainer.classList.remove("empty-state");
            activeSessionContainer.appendChild(renderBadge("En cours"));
            activeSessionContainer.appendChild(renderSessionCard(result.active_session));
        } else {
            activeSessionContainer.classList.add("empty-state");
            activeSessionContainer.textContent = "Aucune session active pour le moment.";
        }

        const historyContainer = document.getElementById("recent-sessions");
        historyContainer.innerHTML = "";
        if (result.recharge_history.length === 0) {
            renderEmpty(historyContainer, "Aucune recharge a afficher.");
        } else {
            result.recharge_history.forEach((sessionItem) => {
                historyContainer.appendChild(renderSessionCard(sessionItem));
            });
        }

        if (user.is_staff) {
            adminLink.hidden = false;
        }

        status.textContent = `Session valide. Access: ${snapshot.accessReadable}, refresh: ${snapshot.refreshReadable}.`;
    } catch (_error) {
        status.classList.add("error");
        status.textContent = "Impossible de charger le dashboard. Reconnecte-toi.";
        window.AuthAPI.clearTokens();
        window.setTimeout(() => {
            window.location.href = "/login.html";
        }, 1200);
    }
});
