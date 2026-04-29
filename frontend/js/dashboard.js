function formatDateTime(value) {
    if (!value) return "-";
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
            <span>${session.status === "active" ? "En cours" : "Archivée"}</span>
        </div>
        <p>Emplacement ${session.emplacement}</p>
        <p>Début : ${formatDateTime(session.start_time)}</p>
        <p>Fin : ${formatDateTime(session.end_time)}</p>
    `;
    return item;
}

function renderReservationCard(reservation, onCancel) {
    const item = document.createElement("article");
    item.className = "list-item";
    item.innerHTML = `
        <div class="list-item-head">
            <strong>${reservation.station_nom || reservation.station}</strong>
            <span>${reservation.statut}</span>
        </div>
        <p>Emplacement ${reservation.emplacement_numero || reservation.emplacement}</p>
        <p>Début : ${formatDateTime(reservation.date_debut)}</p>
        <p>Fin : ${formatDateTime(reservation.date_fin)}</p>
        <p>Mode : ${reservation.auth_mode || "-"}</p>
        <p>Code : ${reservation.reference_code || "-"}</p>
    `;

    if (reservation.can_cancel && onCancel) {
        const actions = document.createElement("div");
        actions.className = "cta-row";
        const cancelButton = document.createElement("button");
        cancelButton.className = "btn btn-secondary";
        cancelButton.type = "button";
        cancelButton.textContent = "Annuler la réservation";
        cancelButton.addEventListener("click", () => onCancel(reservation));
        actions.appendChild(cancelButton);
        item.appendChild(actions);
    }

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
        const active = button.dataset.tab === tabName;
        button.classList.toggle("active", active);
        button.setAttribute("aria-selected", String(active));
    });
    document.querySelectorAll("[data-tab-panel]").forEach((panel) => {
        panel.hidden = panel.dataset.tabPanel !== tabName;
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    const status = document.getElementById("dashboard-status");
    const logoutBtn = document.getElementById("dashboard-logout");
    const adminLink = document.getElementById("dashboard-admin-link");

    function setStatus(message, isError = false) {
        status.classList.toggle("error", isError);
        status.classList.toggle("success", Boolean(message) && !isError);
        status.textContent = message;
    }

    document.querySelectorAll("[data-tab]").forEach((button) => {
        button.addEventListener("click", () => setActiveTab(button.dataset.tab));
    });

    logoutBtn.addEventListener("click", () => {
        window.AuthAPI.logout();
    });

    async function cancelUserReservation(reservation) {
        if (!window.confirm(`Annuler la réservation ${reservation.reference_code || ""} ?`)) return;

        try {
            await window.AuthAPI.cancelReservation(reservation.id_reservation);
            setStatus("Réservation annulée.");
            await loadDashboard();
            setActiveTab("reservations");
        } catch (error) {
            setStatus(error.message || "Impossible d'annuler la réservation.", true);
        }
    }

    async function loadDashboard() {
        const result = await window.AuthAPI.getDashboard();
        const user = result.user;
        const snapshot = window.AuthAPI.getSessionSnapshot();

        adminLink.hidden = !user.is_staff;
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
                upcomingReservations.appendChild(renderReservationCard(reservation, cancelUserReservation));
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
    }

    const session = await window.AuthAPI.ensureSession();
    if (!session) {
        setStatus("Session absente ou expirée. Redirection vers la connexion.", true);
        window.setTimeout(() => {
            window.location.href = "/login.html";
        }, 1200);
        return;
    }

    try {
        await loadDashboard();
        setStatus("Données chargées.");
        setActiveTab("overview");
    } catch (_error) {
        setStatus("Impossible de charger le tableau de bord. Reconnectez-vous.", true);
        window.AuthAPI.clearTokens();
        window.setTimeout(() => {
            window.location.href = "/login.html";
        }, 1200);
    }
});
