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

function setStatus(message, isError = false) {
    const status = document.getElementById("mobile-session-status");
    status.classList.toggle("error", Boolean(isError));
    status.textContent = message || "";
}

function setExpiredState() {
    document.getElementById("mobile-session-expired").hidden = false;
    document.getElementById("mobile-session-reservations-panel").hidden = true;
    document.getElementById("mobile-session-authorized").hidden = true;
}

function renderReservation(reservation, session, onAuthorize) {
    const item = document.createElement("article");
    item.className = "mobile-reservation-card";

    const heading = document.createElement("div");
    heading.className = "mobile-reservation-heading";

    const title = document.createElement("h2");
    title.textContent = reservation.station_nom || reservation.station || "Station";

    const state = document.createElement("span");
    state.className = reservation.compatible_station ? "session-pill" : "session-pill muted-pill";
    state.textContent = reservation.compatible_station ? "Compatible" : "Autre station";

    heading.append(title, state);

    const details = document.createElement("dl");
    details.className = "mobile-reservation-details";
    [
        ["Emplacement", reservation.emplacement_numero || reservation.emplacement || "-"],
        ["Debut", formatDateTime(reservation.date_debut)],
        ["Fin", formatDateTime(reservation.date_fin)],
        ["Code", reservation.reference_code || "-"],
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
    button.textContent = "Demarrer sur cette borne";
    button.disabled = !reservation.compatible_station || session.status === "authorized" || session.status === "consumed";
    button.addEventListener("click", () => onAuthorize(reservation, button));

    item.append(heading, details, button);
    return item;
}

function renderReservations(reservations, session, onAuthorize) {
    const container = document.getElementById("mobile-session-reservations");
    container.replaceChildren();

    if (!reservations.length) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = "Aucune reservation active ou proche du debut pour ce compte.";
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

    context.textContent = session.station_nom
        ? `Borne ${session.station_nom}`
        : "Borne en attente d'autorisation";
    countdown.textContent = session.expires_in > 0
        ? window.AuthAPI.formatDuration(session.expires_in)
        : "expiree";
}

document.addEventListener("DOMContentLoaded", async () => {
    const token = getToken();
    if (!token) {
        setStatus("Lien de session mobile incomplet.", true);
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
        setStatus("Envoi de l'autorisation a la borne...");
        try {
            const result = await window.AuthAPI.authorizeMobileSession(token, reservation.id_reservation);
            const mobileSession = result.mobile_session;
            updateSessionHeader(mobileSession);
            document.getElementById("mobile-session-reservations-panel").hidden = true;
            document.getElementById("mobile-session-authorized").hidden = false;
            document.getElementById("mobile-session-authorized-detail").textContent =
                `${reservation.station_nom || reservation.station} - emplacement ${reservation.emplacement_numero || reservation.emplacement}.`;
            setStatus("Autorisation confirmee. Regardez l'ecran de la borne.");
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
            document.getElementById("mobile-session-reservations-panel").hidden = true;
            document.getElementById("mobile-session-authorized").hidden = false;
            setStatus(mobileSession.status === "consumed"
                ? "La borne a demarre la session."
                : "Autorisation deja envoyee a la borne.");
            return;
        }

        renderReservations(result.reservations || [], mobileSession, authorizeReservation);
    } catch (error) {
        setStatus(error.message || "Session mobile introuvable.", true);
        setExpiredState();
    }
});
