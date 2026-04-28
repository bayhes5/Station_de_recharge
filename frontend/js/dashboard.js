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
            <span>${session.status === "active" ? "En cours" : "Terminée"}</span>
        </div>
        <p>Emplacement ${session.emplacement}</p>
        <p>Début : ${formatDateTime(session.start_time)}</p>
        <p>Fin : ${formatDateTime(session.end_time)}</p>
    `;
    return item;
}

function renderReservationCard(reservation) {
    const item = document.createElement("article");
    item.className = "list-item";
    item.innerHTML = `
        <div class="list-item-head">
            <strong>${reservation.station_nom || reservation.station}</strong>
            <span>${reservation.statut}</span>
        </div>
        <p>Emplacement ${reservation.emplacement}</p>
        <p>Début : ${formatDateTime(reservation.date_debut)}</p>
        <p>Fin : ${formatDateTime(reservation.date_fin)}</p>
        <p>Mode : ${reservation.auth_mode || "-"}</p>
        <p>Code : ${reservation.reference_code || "-"}</p>
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

function setActiveTab(tabName) {
    document.querySelectorAll("[data-tab]").forEach((button) => {
        button.classList.toggle("active", button.dataset.tab === tabName);
        button.setAttribute("aria-selected", String(button.dataset.tab === tabName));
    });
    document.querySelectorAll("[data-tab-panel]").forEach((panel) => {
        panel.hidden = panel.dataset.tabPanel !== tabName;
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    const status = document.getElementById("dashboard-status");
    const logoutBtn = document.getElementById("dashboard-logout");

    document.querySelectorAll("[data-tab]").forEach((button) => {
        button.addEventListener("click", () => setActiveTab(button.dataset.tab));
    });

    logoutBtn.addEventListener("click", () => {
        window.AuthAPI.logout();
    });

    const session = await window.AuthAPI.ensureSession();
    if (!session) {
        status.classList.add("error");
        status.textContent = "Session absente ou expirée. Redirection vers la connexion.";
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
            ? "Expiré"
            : `Expire dans ${snapshot.accessReadable}`;
        document.getElementById("refresh-expiry").textContent = snapshot.refreshExpired
            ? "Expiré"
            : `Expire dans ${snapshot.refreshReadable}`;

        document.getElementById("kpi-sessions-total").textContent = result.stats.sessions_total;
        document.getElementById("kpi-reservations-total").textContent = result.stats.reservations_total;
        document.getElementById("kpi-upcoming-reservations").textContent = result.stats.reservations_upcoming;

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
        if (result.recharge_history.length === 0) {
            renderEmpty(historyContainer, "Aucune recharge à afficher.");
        } else {
            historyContainer.innerHTML = "";
            result.recharge_history.forEach((sessionItem) => {
                historyContainer.appendChild(renderSessionCard(sessionItem));
            });
        }

        const upcomingReservations = document.getElementById("upcoming-reservations");
        if (!result.upcoming_reservations?.length) {
            renderEmpty(upcomingReservations, "Aucune réservation à venir.");
        } else {
            upcomingReservations.innerHTML = "";
            result.upcoming_reservations.forEach((reservation) => {
                upcomingReservations.appendChild(renderReservationCard(reservation));
            });
        }

        const recentReservations = document.getElementById("recent-reservations");
        if (!result.reservations_history?.length) {
            renderEmpty(recentReservations, "Aucune réservation récente.");
        } else {
            recentReservations.innerHTML = "";
            result.reservations_history.forEach((reservation) => {
                recentReservations.appendChild(renderReservationCard(reservation));
            });
        }

        status.textContent = "Données chargées.";
        setActiveTab("overview");
    } catch (_error) {
        status.classList.add("error");
        status.textContent = "Impossible de charger le tableau de bord. Reconnecte-toi.";
        window.AuthAPI.clearTokens();
        window.setTimeout(() => {
            window.location.href = "/login.html";
        }, 1200);
    }
});
