const SESSION_MINUTES = 30;
const AUTH_OPTIONS = {
    rfid: "Badge RFID",
    qr: "QR code temporaire",
    code: "Code alphanumérique temporaire",
};

function localToDate(value) {
    return value ? new Date(value) : null;
}

function dateToIso(date) {
    return date ? date.toISOString() : "";
}

function addMinutes(date, minutes) {
    return new Date(date.getTime() + minutes * 60 * 1000);
}

function formatDateTime(value) {
    if (!value) {
        return "-";
    }
    return new Date(value).toLocaleString("fr-FR");
}

function renderReservations(container, reservations) {
    container.innerHTML = "";

    if (!reservations.length) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = "Aucune réservation pour le moment.";
        container.appendChild(empty);
        return;
    }

    reservations.forEach((reservation) => {
        const item = document.createElement("article");
        item.className = "list-item";

        const title = document.createElement("strong");
        title.textContent = `${reservation.station_nom || reservation.station} - emplacement ${reservation.emplacement}`;

        const details = document.createElement("p");
        details.textContent = `${formatDateTime(reservation.date_debut)} → ${formatDateTime(reservation.date_fin)} | ${reservation.statut} | ${reservation.auth_mode || "-"}`;

        const code = document.createElement("p");
        code.textContent = `Code de réservation : ${reservation.reference_code || "-"}`;

        item.appendChild(title);
        item.appendChild(details);
        item.appendChild(code);
        container.appendChild(item);
    });
}

function renderAvailability(container, station, emplacements) {
    if (!station) {
        container.className = "empty-state";
        container.textContent = "Sélectionnez une station pour voir les places disponibles.";
        return;
    }

    if (!emplacements.length) {
        container.className = "empty-state";
        container.textContent = "Aucun emplacement disponible sur cette plage.";
        return;
    }

    container.className = "stacked-list";
    container.innerHTML = "";

    emplacements.forEach((emplacement) => {
        const item = document.createElement("article");
        item.className = "list-item";
        const title = document.createElement("strong");
        title.textContent = `Emplacement ${emplacement.numero}`;
        const meta = document.createElement("p");
        meta.textContent = `${emplacement.statut} | serrure : ${emplacement.lock_state}`;
        item.appendChild(title);
        item.appendChild(meta);
        container.appendChild(item);
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    const status = document.getElementById("reservation-status");
    const form = document.getElementById("reservation-form");
    const stationSelect = document.getElementById("reservation-station");
    const emplacementSelect = document.getElementById("reservation-emplacement");
    const startInput = document.getElementById("reservation-start");
    const endDisplay = document.getElementById("reservation-end-display");
    const authModeSelect = document.getElementById("reservation-auth-mode");
    const authValueField = document.getElementById("reservation-auth-value-field");
    const authValueInput = document.getElementById("reservation-auth-value");
    const availabilityBox = document.getElementById("availability-box");
    const reservationsList = document.getElementById("reservations-list");
    const reservationCodeBox = document.createElement("div");
    reservationCodeBox.className = "empty-state";

    const session = await window.AuthAPI.ensureSession();
    if (!session) {
        status.classList.add("error");
        status.textContent = "Session absente ou expirée. Redirection vers la connexion.";
        window.setTimeout(() => {
            window.location.href = "/login.html";
        }, 1200);
        return;
    }

    let stations = [];
    let savedRfidValue = "";

    function roundToHalfHour(date, stepMinutes = 30) {
        const rounded = new Date(date);
        rounded.setSeconds(0, 0);
        const minutes = rounded.getMinutes();
        const remainder = minutes % stepMinutes;
        if (remainder !== 0) {
            rounded.setMinutes(minutes + (stepMinutes - remainder));
        }
        return rounded;
    }

    function toLocalInputValue(date) {
        const rounded = roundToHalfHour(date);
        const offset = rounded.getTimezoneOffset() * 60000;
        return new Date(rounded.getTime() - offset).toISOString().slice(0, 16);
    }

    function getStartDate() {
        return localToDate(startInput.value);
    }

    function getEndDate() {
        const start = getStartDate();
        return start ? addMinutes(start, SESSION_MINUTES) : null;
    }

    function updateEndDisplay() {
        const end = getEndDate();
        endDisplay.textContent = end ? end.toLocaleString("fr-FR") : "-";
    }

    function appendAuthOption(value) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = AUTH_OPTIONS[value];
        authModeSelect.appendChild(option);
    }

    function configureAuthOptions() {
        authModeSelect.innerHTML = "";

        if (savedRfidValue) {
            appendAuthOption("rfid");
        }

        appendAuthOption("qr");
        appendAuthOption("code");
        authModeSelect.value = savedRfidValue ? "rfid" : "qr";
        updateAuthFieldVisibility();
    }

    function updateAuthFieldVisibility() {
        const isRfid = authModeSelect.value === "rfid";
        authValueField.hidden = !isRfid;
        authValueField.style.display = isRfid ? "" : "none";
        authValueInput.required = isRfid;
        authValueInput.readOnly = true;
        authValueInput.value = isRfid ? savedRfidValue : "";
    }

    async function loadSavedRfid() {
        const result = await window.AuthAPI.getAuthMethods();
        const methods = result.results || [];
        const rfid = methods.find((method) => String(method.type_label || "").toUpperCase() === "RFID");
        savedRfidValue = rfid?.display_value || "";
        configureAuthOptions();
    }

    async function loadReservations() {
        const result = await window.AuthAPI.getReservations();
        renderReservations(reservationsList, result.results || []);
    }

    async function loadStations() {
        const result = await window.AuthAPI.getStations();
        stations = result.results || [];
        stationSelect.innerHTML = "";

        stations.forEach((station) => {
            const option = document.createElement("option");
            option.value = station.id_station;
            option.textContent = `${station.nom} - ${station.localisation_text}`;
            stationSelect.appendChild(option);
        });
    }

    async function refreshAvailability() {
        const stationId = stationSelect.value;
        const start = getStartDate();
        const end = getEndDate();
        updateEndDisplay();

        if (!stationId || !start || !end) {
            renderAvailability(availabilityBox, null, []);
            return;
        }

        try {
            const result = await window.AuthAPI.getReservationAvailability({
                station: stationId,
                date_debut: dateToIso(start),
                date_fin: dateToIso(end),
            });
            renderAvailability(availabilityBox, result.station, result.available_emplacements || []);
            emplacementSelect.innerHTML = "";
            (result.available_emplacements || []).forEach((emplacement) => {
                const option = document.createElement("option");
                option.value = emplacement.id_emplacement;
                option.textContent = `Emplacement ${emplacement.numero}`;
                emplacementSelect.appendChild(option);
            });
        } catch (error) {
            availabilityBox.className = "empty-state";
            availabilityBox.textContent = error.message || "Impossible de charger les disponibilités.";
        }
    }

    try {
        await Promise.all([loadStations(), loadReservations(), loadSavedRfid()]);
        const startDefault = new Date();
        startInput.value = toLocalInputValue(startDefault);
        updateEndDisplay();
        status.textContent = savedRfidValue
            ? "Badge RFID détecté. Il est sélectionné par défaut pour la réservation."
            : "Aucun badge RFID enregistré. QR code et code temporaire restent disponibles.";
    } catch (_error) {
        status.classList.add("error");
        status.textContent = "Impossible de charger la réservation.";
        return;
    }

    stationSelect.addEventListener("change", refreshAvailability);
    startInput.addEventListener("change", refreshAvailability);
    authModeSelect.addEventListener("change", updateAuthFieldVisibility);

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        status.classList.remove("error");
        const submitButton = form.querySelector('button[type="submit"]');
        submitButton.disabled = true;

        const start = getStartDate();
        const end = getEndDate();
        if (!start || !end) {
            status.classList.add("error");
            status.textContent = "Choisissez une date et une heure de début.";
            submitButton.disabled = false;
            return;
        }

        if (authModeSelect.value === "rfid" && !savedRfidValue) {
            status.classList.add("error");
            status.textContent = "Ajoutez d’abord un badge RFID dans votre profil.";
            submitButton.disabled = false;
            return;
        }

        const payload = {
            station: stationSelect.value,
            emplacement: emplacementSelect.value,
            date_debut: dateToIso(start),
            date_fin: dateToIso(end),
            auth_mode: authModeSelect.value,
            auth_value: authModeSelect.value === "rfid" ? savedRfidValue : "",
        };

        try {
            const result = await window.AuthAPI.createReservation(payload);
            status.textContent = "Réservation créée avec succès.";
            availabilityBox.innerHTML = "";
            if (result.reservation_code) {
                reservationCodeBox.className = "empty-state";
                reservationCodeBox.textContent = `Code de réservation : ${result.reservation_code}`;
                availabilityBox.appendChild(reservationCodeBox);
            }
            if (result.reservation?.auth_display_value) {
                const codeLine = document.createElement("div");
                codeLine.className = "empty-state";
                codeLine.textContent = `Valeur d’authentification (${result.reservation.auth_mode}) : ${result.reservation.auth_display_value}`;
                availabilityBox.appendChild(codeLine);
                const hint = document.createElement("div");
                hint.className = "empty-state";
                hint.textContent = "Le kiosque demande le code de réservation, puis la valeur QR/RFID/code selon le mode choisi.";
                availabilityBox.appendChild(hint);
            }
            form.reset();
            startInput.value = toLocalInputValue(new Date());
            configureAuthOptions();
            updateEndDisplay();
            await loadReservations();
            await refreshAvailability();
        } catch (error) {
            status.classList.add("error");
            status.textContent = error.message || "Erreur lors de la création de la réservation.";
        } finally {
            submitButton.disabled = false;
        }
    });

    if (stations.length) {
        await refreshAvailability();
    }
});
