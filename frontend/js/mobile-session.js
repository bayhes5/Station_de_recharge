function formatDateTime(value) {
    if (!value) return "-";
    return new Intl.DateTimeFormat("fr-FR", {
        dateStyle: "short",
        timeStyle: "short",
    }).format(new Date(value));
}

function currentPathWithQuery() {
    return `${window.location.pathname}${window.location.search}`;
}

function getToken() {
    return new URLSearchParams(window.location.search).get("token") || "";
}

function terminalLabel(session) {
    const station = session?.station_nom || "Station";
    const borne = session?.borne_nom || "borne";
    return `${station} - ${borne}`;
}

function emplacementLabel(reservation) {
    const numero = reservation.emplacement_numero || reservation.emplacement || "-";
    return `Emplacement ${numero}`;
}

function unlockButtonLabel(reservation) {
    const numero = reservation.emplacement_numero || reservation.emplacement || "-";
    return `Déverrouiller l’emplacement ${numero}`;
}

function reservationWindowLabel(reservation) {
    const start = reservation.date_debut ? new Date(reservation.date_debut) : null;
    const end = reservation.date_fin ? new Date(reservation.date_fin) : null;
    if (!start || Number.isNaN(start.getTime())) {
        return "Réservation";
    }
    const day = new Intl.DateTimeFormat("fr-FR", {
        weekday: "long",
        day: "numeric",
        month: "long",
    }).format(start);
    const startTime = new Intl.DateTimeFormat("fr-FR", {
        hour: "2-digit",
        minute: "2-digit",
    }).format(start);
    const endTime = end && !Number.isNaN(end.getTime())
        ? new Intl.DateTimeFormat("fr-FR", {
            hour: "2-digit",
            minute: "2-digit",
        }).format(end)
        : "--:--";
    return `${day} · ${startTime} - ${endTime}`;
}

function setStatus(message, isError = false) {
    const status = document.getElementById("mobile-session-status");
    status.classList.toggle("error", Boolean(isError));
    status.hidden = !message;
    status.textContent = message || "";
}

function setMobileSessionStep(status) {
    const authorizedStep = document.getElementById("mobile-step-authorized");
    const consumedStep = document.getElementById("mobile-step-consumed");
    authorizedStep?.classList.toggle("active", ["authorized", "consumed"].includes(status));
    consumedStep?.classList.toggle("active", status === "consumed");
}

function setExpiredState() {
    document.getElementById("mobile-session-expired").hidden = false;
    document.getElementById("mobile-session-reservations-panel").hidden = true;
    document.getElementById("mobile-session-authorized").hidden = true;
}

function renderReservation(reservation, session, onAuthorize) {
    const item = document.createElement("article");
    item.className = "mobile-reservation-card";
    const compatible = reservation.compatible_terminal ?? reservation.compatible_station;

    const heading = document.createElement("div");
    heading.className = "mobile-reservation-heading";

    const title = document.createElement("h2");
    title.textContent = reservationWindowLabel(reservation);

    const state = document.createElement("span");
    state.className = compatible ? "session-pill" : "session-pill muted-pill";
    state.textContent = compatible ? "Disponible ici" : "Autre borne";

    heading.append(title, state);

    const target = document.createElement("p");
    target.className = "mobile-reservation-target";
    target.textContent = [
        reservation.station_nom || reservation.station || "Station",
        reservation.borne_nom || reservation.borne || "borne",
        emplacementLabel(reservation),
    ].join(" - ");

    const details = document.createElement("dl");
    details.className = "mobile-reservation-details";
    [
        ["Code", reservation.reference_code || "-"],
        ["Début", formatDateTime(reservation.date_debut)],
        ["Fin", formatDateTime(reservation.date_fin)],
    ].forEach(([label, value]) => {
        const term = document.createElement("dt");
        term.textContent = label;
        const description = document.createElement("dd");
        description.textContent = value;
        details.append(term, description);
    });

    const button = document.createElement("button");
    button.className = "btn btn-primary full-width";
    button.type = "button";
    button.textContent = compatible
        ? unlockButtonLabel(reservation)
        : "Réservation prévue ailleurs";
    button.disabled = !compatible || session.status === "authorized" || session.status === "consumed";
    button.addEventListener("click", () => onAuthorize(reservation, button));

    item.append(heading, target, details, button);
    return item;
}

function renderReservations(reservations, session, onAuthorize) {
    const container = document.getElementById("mobile-session-reservations");
    container.replaceChildren();

    if (!reservations.length) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = "Aucune réservation active ou proche du début pour ce compte.";
        container.appendChild(empty);
        return;
    }

    reservations.forEach((reservation) => {
        container.appendChild(renderReservation(reservation, session, onAuthorize));
    });
}

function updateSessionHeader(session) {
    const context = document.getElementById("mobile-session-context");
    const countdown = document.getElementById("mobile-session-countdown");
    const terminalName = document.getElementById("mobile-session-terminal-name");
    const terminalDetail = document.getElementById("mobile-session-terminal-detail");

    const label = session.station_nom
        ? terminalLabel(session)
        : "Borne en attente d'autorisation";
    context.textContent = "Confirmez l'accès depuis votre téléphone, puis suivez les instructions sur l'écran tactile.";
    terminalName.textContent = label;
    terminalDetail.textContent = "Session QR temporaire";
    countdown.textContent = session.expires_in > 0
        ? window.AuthAPI.formatDuration(session.expires_in)
        : "expirée";
}

function showAuthorizedPanel(session, reservation = null) {
    const authorizedTitle = document.getElementById("mobile-session-authorized-title");
    const authorizedDetail = document.getElementById("mobile-session-authorized-detail");
    const reservationLabel = reservation
        ? `${emplacementLabel(reservation)} est autorisé sur ${reservation.borne_nom || reservation.borne || "la borne"}.`
        : "La borne peut maintenant ouvrir l'emplacement.";

    document.getElementById("mobile-session-reservations-panel").hidden = true;
    document.getElementById("mobile-session-authorized").hidden = false;
    setMobileSessionStep(session.status);

    if (session.status === "consumed") {
        authorizedTitle.textContent = "Borne déverrouillée";
        authorizedDetail.textContent = "Retournez à la borne : l'emplacement est prêt pour le branchement.";
        setStatus("");
    } else {
        authorizedTitle.textContent = "Accès envoyé";
        authorizedDetail.textContent = reservationLabel;
        setStatus("En attente de prise en compte par la borne...");
    }
}

function startAuthorizationPolling(token, reservation = null) {
    let attempts = 0;
    const maxAttempts = 60;
    const interval = window.setInterval(async () => {
        attempts += 1;
        try {
            const result = await window.AuthAPI.getMobileSession(token);
            const mobileSession = result.mobile_session;
            updateSessionHeader(mobileSession);
            showAuthorizedPanel(mobileSession, result.reservation || reservation);

            if (mobileSession.status === "consumed" || attempts >= maxAttempts) {
                window.clearInterval(interval);
                if (mobileSession.status !== "consumed") {
                    setStatus("Accès envoyé. Vérifiez l'écran de la borne.");
                }
            }
        } catch (error) {
            window.clearInterval(interval);
            setStatus(error.message || "Impossible de suivre l'état de la borne.", true);
        }
    }, 2000);
}

document.addEventListener("DOMContentLoaded", async () => {
    const token = getToken();
    if (!token) {
        setStatus("Lien de session mobile absent ou invalide.", true);
        setExpiredState();
        return;
    }

    const session = await window.AuthAPI.ensureSession();
    if (!session) {
        const next = encodeURIComponent(currentPathWithQuery());
        window.location.href = `/login.html?next=${next}`;
        return;
    }

    async function authorizeReservation(reservation, button) {
        button.disabled = true;
        setStatus("Transmission de l'accès à la borne...");
        try {
            const result = await window.AuthAPI.authorizeMobileSession(token, reservation.id_reservation);
            const mobileSession = result.mobile_session;
            updateSessionHeader(mobileSession);
            showAuthorizedPanel(mobileSession, result.reservation || reservation);
            startAuthorizationPolling(token, result.reservation || reservation);
        } catch (error) {
            button.disabled = false;
            setStatus(error.message || "Autorisation impossible.", true);
        }
    }

    try {
        const result = await window.AuthAPI.getMobileSession(token);
        const mobileSession = result.mobile_session;
        updateSessionHeader(mobileSession);

        if (mobileSession.status === "authorized" || mobileSession.status === "consumed") {
            showAuthorizedPanel(mobileSession, result.reservation || null);
            if (mobileSession.status === "authorized") {
                startAuthorizationPolling(token, result.reservation || null);
            }
            return;
        }

        renderReservations(result.reservations || [], mobileSession, authorizeReservation);
    } catch (error) {
        setStatus(error.message || "Session mobile introuvable.", true);
        setExpiredState();
    }
});
