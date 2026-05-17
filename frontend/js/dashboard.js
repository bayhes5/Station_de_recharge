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
    const head = document.createElement("div");
    head.className = "list-item-head";
    const title = document.createElement("strong");
    title.textContent = session.station || "-";
    const state = document.createElement("span");
    state.textContent = session.status === "active" ? "En cours" : "Archivée";
    head.appendChild(title);
    head.appendChild(state);

    const emplacement = document.createElement("p");
    emplacement.textContent = `Emplacement ${session.emplacement || "-"}`;
    const start = document.createElement("p");
    start.textContent = `Début : ${formatDateTime(session.start_time)}`;
    const end = document.createElement("p");
    end.textContent = `Fin : ${formatDateTime(session.end_time)}`;

    item.appendChild(head);
    item.appendChild(emplacement);
    item.appendChild(start);
    item.appendChild(end);
    return item;
}

function appendAccessPayload(container, result) {
    container.innerHTML = "";

    if (result.reservation_code) {
        const reservationLine = document.createElement("div");
        reservationLine.className = "empty-state";
        reservationLine.textContent = `Code de réservation : ${result.reservation_code}`;
        container.appendChild(reservationLine);
    }

    const access = result.access_payload;
    if (!access) return;

    if (access.mode === "qr") {
        const qrCard = document.createElement("article");
        qrCard.className = "qr-access-card";

        const title = document.createElement("strong");
        title.textContent = "QR code sécurisé";

        const qrFrame = document.createElement("div");
        qrFrame.className = "qr-frame";
        if (!window.AuthAPI.renderQrSvg(qrFrame, access.qr_svg)) {
            qrFrame.textContent = "QR indisponible. Vérifiez la dépendance backend qrcode[pil].";
        }

        const meta = document.createElement("p");
        meta.textContent = `Valide jusqu’à ${formatDateTime(access.expires_at)}.`;

        qrCard.appendChild(title);
        qrCard.appendChild(qrFrame);
        qrCard.appendChild(meta);
        container.appendChild(qrCard);
        return;
    }

    if (access.mode === "code") {
        const codeLine = document.createElement("div");
        codeLine.className = "empty-state access-code";
        if (access.sent_at) {
            codeLine.textContent = `Code SMS temporaire envoyé au ${access.recipient_hint || "numéro enregistré"}.`;
        } else {
            codeLine.textContent = "Code SMS temporaire généré. Utilisez le bouton d'envoi avant votre passage à la borne.";
        }
        container.appendChild(codeLine);
    }
}

function reservationCanShowAccess(reservation) {
    return ["qr", "code"].includes(reservation.auth_mode)
        && !["annulee", "terminee"].includes(reservation.statut)
        && (!reservation.date_fin || new Date(reservation.date_fin) >= new Date());
}

function renderReservationCard(reservation, onCancel, onAccess) {
    const item = document.createElement("article");
    item.className = "list-item";

    const head = document.createElement("div");
    head.className = "list-item-head";
    const title = document.createElement("strong");
    title.textContent = reservation.station_nom || reservation.station || "-";
    const state = document.createElement("span");
    state.textContent = reservation.statut || "-";
    head.appendChild(title);
    head.appendChild(state);
    item.appendChild(head);

    [
        `Emplacement ${reservation.emplacement_numero || reservation.emplacement || "-"}`,
        `Début : ${formatDateTime(reservation.date_debut)}`,
        `Fin : ${formatDateTime(reservation.date_fin)}`,
        `Mode : ${reservation.auth_mode || "-"}`,
        `Code : ${reservation.reference_code || "-"}`,
    ].forEach((line) => {
        const paragraph = document.createElement("p");
        paragraph.textContent = line;
        item.appendChild(paragraph);
    });

    if ((reservation.can_cancel && onCancel) || (reservationCanShowAccess(reservation) && onAccess)) {
        const actions = document.createElement("div");
        actions.className = "cta-row";
        if (reservationCanShowAccess(reservation) && onAccess) {
            const accessButton = document.createElement("button");
            accessButton.className = "btn btn-secondary";
            accessButton.type = "button";
            accessButton.dataset.accessToggle = reservation.id_reservation;
            accessButton.textContent = reservation.auth_mode === "qr" ? "+ Afficher le QR" : "Recevoir le code SMS";
            accessButton.addEventListener("click", () => onAccess(reservation, item, accessButton));
            actions.appendChild(accessButton);
        }
        if (reservation.can_cancel && onCancel) {
            const cancelButton = document.createElement("button");
            cancelButton.className = "btn btn-secondary";
            cancelButton.type = "button";
            cancelButton.textContent = "Annuler la réservation";
            cancelButton.addEventListener("click", () => onCancel(reservation));
            actions.appendChild(cancelButton);
        }
        item.appendChild(actions);
    }

    const accessContainer = document.createElement("div");
    accessContainer.className = "reservation-access-host";
    accessContainer.dataset.reservationId = reservation.id_reservation;
    accessContainer.dataset.accessMode = reservation.auth_mode || "";
    item.appendChild(accessContainer);

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
        const confirmed = await window.AuthAPI.confirmAction(
            `Annuler la réservation ${reservation.reference_code || ""} ?`,
            {
                title: "Annuler la réservation",
                confirmLabel: "Annuler la réservation",
                danger: true,
            }
        );
        if (!confirmed) return;

        try {
            await window.AuthAPI.cancelReservation(reservation.id_reservation);
            setStatus("Réservation annulée.");
            await loadDashboard();
            setActiveTab("reservations");
        } catch (error) {
            setStatus(error.message || "Impossible d'annuler la réservation.", true);
        }
    }

    async function showReservationAccess(reservation, card, triggerButton) {
        const accessContainer = card.querySelector(".reservation-access-host");
        if (!accessContainer) return;

        if (reservation.auth_mode === "code") {
            try {
                if (triggerButton) triggerButton.disabled = true;
                const result = await window.AuthAPI.sendReservationAccessCode(reservation.id_reservation);
                accessContainer.innerHTML = "";
                appendAccessPayload(accessContainer, result);
                accessContainer.dataset.visible = "true";
                if (triggerButton) {
                    triggerButton.textContent = "Renvoyer le code SMS";
                }
                setStatus("Code SMS temporaire envoyé.");
                setActiveTab("reservations");
            } catch (error) {
                setStatus(error.message || "Impossible d'envoyer le code SMS temporaire.", true);
            } finally {
                if (triggerButton) triggerButton.disabled = false;
            }
            return;
        }

        if (accessContainer.dataset.visible === "true") {
            accessContainer.innerHTML = "";
            accessContainer.dataset.visible = "false";
            if (triggerButton) {
                triggerButton.textContent = "+ Afficher le QR";
            }
            return;
        }

        try {
            const result = await window.AuthAPI.getReservationAccessPayload(reservation.id_reservation);
            accessContainer.innerHTML = "";
            appendAccessPayload(accessContainer, result);
            accessContainer.dataset.visible = "true";
            if (triggerButton) {
                triggerButton.textContent = "- Masquer le QR";
            }
            setActiveTab("reservations");
        } catch (error) {
            setStatus(error.message || "Impossible d'afficher l'accès temporaire.", true);
        }
    }

    async function refreshVisibleAccesses() {
        if (document.hidden) return;

        const visibleContainers = document.querySelectorAll(".reservation-access-host[data-visible='true']");
        for (const accessContainer of visibleContainers) {
            const reservationId = accessContainer.dataset.reservationId;
            const accessMode = accessContainer.dataset.accessMode;
            if (!reservationId || accessMode !== "qr") continue;

            try {
                const result = await window.AuthAPI.getReservationAccessPayload(reservationId);
                appendAccessPayload(accessContainer, result);
            } catch (_error) {
                accessContainer.innerHTML = "";
                accessContainer.dataset.visible = "false";
                const toggleButton = document.querySelector(`[data-access-toggle="${reservationId}"]`);
                if (toggleButton) {
                    toggleButton.textContent = "+ Afficher le QR";
                }
            }
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
        document.getElementById("refresh-expiry").textContent = snapshot.refreshExpiry
            ? (snapshot.refreshExpired ? "Expiré" : `Expire dans ${snapshot.refreshReadable}`)
            : (snapshot.hasRefreshToken ? "Cookie HttpOnly actif" : "Inconnu");

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
                upcomingReservations.appendChild(renderReservationCard(reservation, cancelUserReservation, showReservationAccess));
            });
        }

        const recentReservations = document.getElementById("recent-reservations");
        if (!result.reservations_history?.length) {
            renderEmpty(recentReservations, "Aucune réservation récente.");
        } else {
            recentReservations.innerHTML = "";
            result.reservations_history.forEach((reservation) => {
                recentReservations.appendChild(renderReservationCard(reservation, null, showReservationAccess));
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
        setStatus("");
        const initialTab = (window.location.hash || "#overview").replace("#", "");
        setActiveTab(["overview", "reservations", "sessions"].includes(initialTab) ? initialTab : "overview");
        window.setInterval(refreshVisibleAccesses, 15000);
        document.addEventListener("visibilitychange", () => {
            if (!document.hidden) refreshVisibleAccesses();
        });
    } catch (_error) {
        setStatus("Impossible de charger le tableau de bord. Reconnectez-vous.", true);
        window.AuthAPI.clearTokens();
        window.setTimeout(() => {
            window.location.href = "/login.html";
        }, 1200);
    }
});
