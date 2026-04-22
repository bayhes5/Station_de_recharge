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

function renderReservationCard(reservation) {
    const item = document.createElement("article");
    item.className = "list-item";

    item.innerHTML = `
        <div class="list-item-head">
            <strong>${reservation.station}</strong>
            <span>${reservation.statut}</span>
        </div>
        <p>Emplacement ${reservation.emplacement}</p>
        <p>${formatDateTime(reservation.date_debut)} - ${formatDateTime(reservation.date_fin)}</p>
    `;

    return item;
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

        document.getElementById("kpi-reservations-total").textContent =
            result.stats.reservations_total;
        document.getElementById("kpi-reservations-upcoming").textContent =
            result.stats.reservations_upcoming;
        document.getElementById("kpi-active-sessions").textContent =
            result.stats.active_sessions;

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

        const upcomingReservationsContainer = document.getElementById("upcoming-reservations");
        upcomingReservationsContainer.innerHTML = "";
        if (result.upcoming_reservations.length === 0) {
            renderEmpty(upcomingReservationsContainer, "Aucune reservation a venir.");
        } else {
            result.upcoming_reservations.forEach((reservation) => {
                upcomingReservationsContainer.appendChild(renderReservationCard(reservation));
            });
        }

        const recentSessionsContainer = document.getElementById("recent-sessions");
        recentSessionsContainer.innerHTML = "";
        if (result.recent_sessions.length === 0) {
            renderEmpty(recentSessionsContainer, "Aucune session enregistree.");
        } else {
            result.recent_sessions.forEach((sessionItem) => {
                recentSessionsContainer.appendChild(renderSessionCard(sessionItem));
            });
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
