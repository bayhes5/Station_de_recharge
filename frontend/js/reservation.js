const RESERVATION_DURATIONS = [
    { minutes: 30, label: "30 min" },
    { minutes: 60, label: "1 h" },
    { minutes: 120, label: "2 h" },
    { minutes: 240, label: "4 h" },
];
const DEFAULT_RESERVATION_DURATION_MINUTES = 60;
const RESERVATION_STEP_MINUTES = 5;
const AUTH_OPTIONS = {
    rfid: "Badge RFID",
    qr: "QR code temporaire",
    code: "Code SMS temporaire",
};
const OSM_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const OSM_RENDER_TIMEOUT_MS = 6500;

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
    if (!value) return "-";
    return new Date(value).toLocaleString("fr-FR");
}

function normalizeSearchValue(value) {
    return String(value ?? "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .trim();
}

function stationSearchText(station) {
    return [
        station.nom,
        station.localisation_text,
        station.latitude,
        station.longitude,
        station.statut,
    ].filter(Boolean).join(" ");
}

function renderReservations(container, reservations, onCancel, onAccess) {
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
        title.textContent = `${reservation.station_nom || reservation.station} - emplacement ${reservation.emplacement_numero || reservation.emplacement}`;

        const details = document.createElement("p");
        details.textContent = `${formatDateTime(reservation.date_debut)} → ${formatDateTime(reservation.date_fin)} | ${reservation.statut} | ${reservation.auth_mode || "-"}`;

        const code = document.createElement("p");
        code.textContent = `Code de réservation : ${reservation.reference_code || "-"}`;

        item.appendChild(title);
        item.appendChild(details);
        item.appendChild(code);

        const canShowAccess = ["qr", "code"].includes(reservation.auth_mode)
            && !["annulee", "terminee"].includes(reservation.statut)
            && (!reservation.date_fin || new Date(reservation.date_fin) >= new Date());

        if ((reservation.can_cancel && onCancel) || (canShowAccess && onAccess)) {
            const actions = document.createElement("div");
            actions.className = "cta-row";

            if (canShowAccess && onAccess) {
                const accessButton = document.createElement("button");
                accessButton.className = "btn btn-secondary";
                accessButton.type = "button";
                accessButton.dataset.accessToggle = reservation.id_reservation;
                accessButton.textContent = reservation.auth_mode === "qr" ? "Afficher le QR" : "Recevoir le code SMS";
                accessButton.addEventListener("click", () => onAccess(reservation, item, accessButton));
                actions.appendChild(accessButton);
            }

            if (reservation.can_cancel && onCancel) {
                const cancelButton = document.createElement("button");
                cancelButton.className = "btn btn-secondary";
                cancelButton.type = "button";
                cancelButton.textContent = "Annuler";
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
        container.appendChild(item);
    });
}

function renderAvailability(container, station, availability) {
    return renderStationAvailability(container, station, availability);

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

function renderStationAvailability(container, station, availability) {
    if (!station) {
        container.className = "empty-state";
        container.textContent = "Sélectionnez une station pour voir les disponibilités.";
        return;
    }

    const availableCount = Number(availability?.available_count ?? 0);
    const totalCount = Number(availability?.total_count ?? 0);

    if (!availableCount) {
        container.className = "empty-state";
        container.textContent = "Aucun emplacement disponible dans cette station sur cette plage.";
        return;
    }

    container.className = "stacked-list";
    container.innerHTML = "";

    const item = document.createElement("article");
    item.className = "list-item";

    const title = document.createElement("strong");
    title.textContent = availableCount === 1
        ? "1 emplacement disponible"
        : `${availableCount} emplacements disponibles`;

    const meta = document.createElement("p");
    meta.textContent = totalCount
        ? `${station.nom} dispose de ${totalCount} emplacement${totalCount > 1 ? "s" : ""}. L'application attribuera automatiquement une place libre pour la durée choisie.`
        : "L'application attribuera automatiquement une place libre.";

    item.appendChild(title);
    item.appendChild(meta);
    container.appendChild(item);
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
            qrFrame.textContent = "QR indisponible pour le moment.";
        }

        const meta = document.createElement("p");
        meta.textContent = `Valide jusqu'à ${formatDateTime(access.expires_at)}. Présentez ce QR code à la borne pendant votre créneau.`;

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

async function initReservationPage() {
    const status = document.getElementById("reservation-status");
    const logoutButton = document.getElementById("reservation-logout");
    const adminLink = document.getElementById("reservation-admin-link");
    const form = document.getElementById("reservation-form");
    const stationInput = document.getElementById("reservation-station");
    const stationSearch = document.getElementById("station-search");
    const stationMap = document.getElementById("station-map");
    const stationResults = document.getElementById("station-results");
    const selectedStationName = document.getElementById("selected-station-name");
    const selectedStationLocation = document.getElementById("selected-station-location");
    const startInput = document.getElementById("reservation-start");
    const durationSelect = document.getElementById("reservation-duration");
    const endDisplay = document.getElementById("reservation-end-display");
    const authModeSelect = document.getElementById("reservation-auth-mode");
    const authValueField = document.getElementById("reservation-auth-value-field");
    const authValueInput = document.getElementById("reservation-auth-value");
    const availabilityBox = document.getElementById("availability-box");
    const reservationsList = document.getElementById("reservations-list");
    logoutButton?.addEventListener("click", () => window.AuthAPI.logout());

    const session = await window.AuthAPI.ensureSession();
    if (!session) {
        status.classList.add("error");
        status.textContent = "Session absente ou expirée. Redirection vers la connexion.";
        window.setTimeout(() => {
            window.location.href = "/login.html";
        }, 1200);
        return;
    }
    if (adminLink) {
        adminLink.hidden = !session.user?.is_staff;
    }

    window.AppNavigation.render(session, { active: "reservation" });

    const userHasPhoneNumber = Boolean(String(session.user?.telephone || "").trim());
    let stations = [];
    let savedRfidValue = "";
    let selectedStation = null;
    let leafletMap = null;
    let leafletMarkers = [];
    let leafletTileLayer = null;
    let leafletTileErrorCount = 0;
    let leafletTileLoadCount = 0;
    let leafletTileReadinessTimer = null;
    let leafletDisabledForSession = false;
    let mapRenderVersion = 0;

    function roundToReservationStep(date, stepMinutes = RESERVATION_STEP_MINUTES) {
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
        const rounded = roundToReservationStep(date);
        const offset = rounded.getTimezoneOffset() * 60000;
        return new Date(rounded.getTime() - offset).toISOString().slice(0, 16);
    }

    function getStartDate() {
        return localToDate(startInput.value);
    }

    function getNextBookableStartDate() {
        return roundToReservationStep(addMinutes(new Date(), RESERVATION_STEP_MINUTES));
    }

    function ensureFutureStartDate() {
        const start = getStartDate();
        const nextBookableStart = getNextBookableStartDate();
        if (!start || start < nextBookableStart) {
            startInput.value = toLocalInputValue(nextBookableStart);
            updateEndDisplay();
            return nextBookableStart;
        }
        return start;
    }

    function getSelectedDurationMinutes() {
        const selected = Number(durationSelect.value || DEFAULT_RESERVATION_DURATION_MINUTES);
        return RESERVATION_DURATIONS.some((duration) => duration.minutes === selected)
            ? selected
            : DEFAULT_RESERVATION_DURATION_MINUTES;
    }

    function getEndDate() {
        const start = getStartDate();
        return start ? addMinutes(start, getSelectedDurationMinutes()) : null;
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

    function configureDurationOptions() {
        durationSelect.innerHTML = "";
        RESERVATION_DURATIONS.forEach((duration) => {
            const option = document.createElement("option");
            option.value = String(duration.minutes);
            option.textContent = duration.label;
            durationSelect.appendChild(option);
        });
        durationSelect.value = String(DEFAULT_RESERVATION_DURATION_MINUTES);
    }

    function configureAuthOptions() {
        authModeSelect.innerHTML = "";

        if (savedRfidValue) {
            appendAuthOption("rfid");
        }

        appendAuthOption("qr");
        if (userHasPhoneNumber) {
            appendAuthOption("code");
        }
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

    function getFilteredStations() {
        const query = normalizeSearchValue(stationSearch.value);
        if (!query) return stations;

        const terms = query.split(/\s+/).filter(Boolean);
        return stations.filter((station) => {
            const haystack = normalizeSearchValue(stationSearchText(station));
            return terms.every((term) => haystack.includes(term));
        });
    }

    function getMapPosition(station, axis, fallbackIndex) {
        const numericValues = stations
            .map((item) => Number(axis === "x" ? item.longitude : item.latitude))
            .filter((value) => Number.isFinite(value));
        const value = Number(axis === "x" ? station.longitude : station.latitude);
        if (!Number.isFinite(value) || !numericValues.length) {
            return 18 + ((fallbackIndex * 23) % 64);
        }

        const min = Math.min(...numericValues);
        const max = Math.max(...numericValues);
        if (min === max) return 50;

        const ratio = (value - min) / (max - min);
        const normalized = axis === "x" ? ratio : 1 - ratio;
        return 10 + normalized * 80;
    }

    function selectStation(station) {
        selectedStation = station;
        stationInput.value = station?.id_station || "";
        selectedStationName.textContent = station?.nom || "Aucune station";
        selectedStationLocation.textContent = station?.localisation_text || "Sélectionnez une station sur la carte.";
        renderStationPicker();
        refreshAvailability();
    }

    function shouldUseLeaflet() {
        if (leafletDisabledForSession) return false;
        if (window.__ENABLE_EXTERNAL_MAP__ === false) return false;
        if (window.__ENABLE_EXTERNAL_MAP__ === true) return true;
        return stationMap.dataset.mapProvider === "leaflet";
    }

    function canUseLeaflet() {
        return Boolean(window.L && typeof window.L.map === "function");
    }

    function loadLeafletAssets() {
        return Promise.resolve(shouldUseLeaflet() && canUseLeaflet());
    }

    function getStationCoordinates(station) {
        const latitude = Number(station.latitude);
        const longitude = Number(station.longitude);
        if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
            return null;
        }
        return [latitude, longitude];
    }

    function clearLeafletMarkers() {
        leafletMarkers.forEach((marker) => marker.remove());
        leafletMarkers = [];
    }

    function resetLeafletMap() {
        if (leafletTileReadinessTimer) {
            window.clearTimeout(leafletTileReadinessTimer);
        }
        clearLeafletMarkers();
        if (leafletMap && typeof leafletMap.remove === "function") {
            leafletMap.remove();
        }
        leafletMap = null;
        leafletTileLayer = null;
        leafletTileErrorCount = 0;
        leafletTileLoadCount = 0;
        leafletTileReadinessTimer = null;
        stationMap.classList.remove("leaflet-station-map");
    }

    function renderLeafletMap(filteredStations) {
        const stationsWithCoordinates = filteredStations
            .map((station) => ({ station, coordinates: getStationCoordinates(station) }))
            .filter((entry) => entry.coordinates);

        if (!shouldUseLeaflet() || !canUseLeaflet() || !stationsWithCoordinates.length) {
            resetLeafletMap();
            return false;
        }

        try {
            stationMap.classList.add("leaflet-station-map");

            if (!leafletMap) {
                stationMap.innerHTML = "";
                leafletMap = window.L.map(stationMap, {
                    scrollWheelZoom: false,
                });
                leafletTileLayer = window.L.tileLayer(OSM_TILE_URL, {
                    attribution: "&copy; OpenStreetMap contributors",
                    maxZoom: 19,
                });
                leafletTileLayer.on("tileload", () => {
                    leafletTileLoadCount += 1;
                    leafletTileErrorCount = 0;
                    if (leafletTileReadinessTimer) {
                        window.clearTimeout(leafletTileReadinessTimer);
                        leafletTileReadinessTimer = null;
                    }
                });
                leafletTileLayer.on("tileerror", () => {
                    leafletTileErrorCount += 1;
                    if (leafletTileErrorCount >= 3) {
                        leafletDisabledForSession = true;
                        renderFallbackMap(getFilteredStations());
                    }
                });
                leafletTileLayer.addTo(leafletMap);
                leafletTileReadinessTimer = window.setTimeout(() => {
                    if (leafletTileLoadCount === 0) {
                        leafletDisabledForSession = true;
                        renderFallbackMap(getFilteredStations());
                    }
                }, OSM_RENDER_TIMEOUT_MS);
            }

            clearLeafletMarkers();
            const bounds = [];
            stationsWithCoordinates.forEach(({ station, coordinates }, index) => {
                const popup = document.createElement("div");
                const name = document.createElement("strong");
                const location = document.createElement("span");
                name.textContent = station.nom;
                location.textContent = station.localisation_text || "";
                popup.append(name, document.createElement("br"), location);

                const isSelected = selectedStation?.id_station === station.id_station;
                const markerIcon = window.L.divIcon({
                    className: `station-leaflet-marker${isSelected ? " active" : ""}`,
                    html: `<span>${index + 1}</span>`,
                    iconSize: [38, 38],
                    iconAnchor: [19, 19],
                });

                const marker = window.L.marker(coordinates, { icon: markerIcon })
                    .addTo(leafletMap)
                    .bindPopup(popup);
                marker.on("click", () => selectStation(station));
                leafletMarkers.push(marker);
                bounds.push(coordinates);
            });

            if (bounds.length === 1) {
                leafletMap.setView(bounds[0], 14);
            } else {
                leafletMap.fitBounds(bounds, { padding: [28, 28] });
            }

            [0, 120, 450, 1000].forEach((delay) => {
                window.setTimeout(() => leafletMap?.invalidateSize(), delay);
            });
            return true;
        } catch (_error) {
            leafletDisabledForSession = true;
            resetLeafletMap();
            return false;
        }
    }

    function renderFallbackMap(filteredStations) {
        resetLeafletMap();
        stationMap.classList.remove("leaflet-station-map");
        stationMap.innerHTML = "";

        if (!filteredStations.length) {
            const placeholder = document.createElement("span");
            placeholder.className = "map-placeholder";
            placeholder.textContent = "Aucune station disponible";
            stationMap.appendChild(placeholder);
            return;
        }

        filteredStations.forEach((station, index) => {
            const isSelected = selectedStation?.id_station === station.id_station;

            const pin = document.createElement("button");
            pin.type = "button";
            pin.className = `station-pin${isSelected ? " active" : ""}`;
            pin.style.left = `${getMapPosition(station, "x", index)}%`;
            pin.style.top = `${getMapPosition(station, "y", index)}%`;
            pin.setAttribute("aria-label", `Sélectionner ${station.nom}`);
            pin.textContent = String(index + 1);
            pin.addEventListener("click", () => selectStation(station));
            stationMap.appendChild(pin);
        });
    }

    function renderStationPicker() {
        const filteredStations = getFilteredStations();
        const renderVersion = ++mapRenderVersion;
        const useLeafletMap = renderLeafletMap(filteredStations);
        if (!useLeafletMap) {
            renderFallbackMap(filteredStations);
            loadLeafletAssets().then((ready) => {
                if (ready && renderVersion === mapRenderVersion) {
                    renderLeafletMap(getFilteredStations());
                }
            });
        }
        stationResults.innerHTML = "";

        if (!filteredStations.length) {
            stationResults.className = "empty-state";
            stationResults.textContent = "Aucune station ne correspond à la recherche.";
            return;
        }

        stationResults.className = "station-results";

        filteredStations.forEach((station) => {
            const isSelected = selectedStation?.id_station === station.id_station;

            const item = document.createElement("button");
            item.type = "button";
            item.className = `station-result${isSelected ? " active" : ""}`;
            const name = document.createElement("strong");
            name.textContent = station.nom || "-";
            const location = document.createElement("span");
            location.textContent = station.localisation_text || "Localisation non renseignée";
            item.appendChild(name);
            item.appendChild(location);
            item.addEventListener("click", () => selectStation(station));
            stationResults.appendChild(item);
        });
    }

    async function cancelReservation(reservation) {
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
            status.classList.remove("error");
            status.textContent = "Réservation annulée.";
            await loadReservations();
            await refreshAvailability();
        } catch (error) {
            status.classList.add("error");
            status.textContent = error.message || "Impossible d’annuler la réservation.";
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
                status.classList.remove("error");
                status.textContent = "Code SMS temporaire envoyé.";
            } catch (error) {
                status.classList.add("error");
                status.textContent = error.message || "Impossible d'envoyer le code SMS temporaire.";
            } finally {
                if (triggerButton) triggerButton.disabled = false;
            }
            return;
        }

        if (accessContainer.dataset.visible === "true") {
            accessContainer.innerHTML = "";
            accessContainer.dataset.visible = "false";
            if (triggerButton) {
                triggerButton.textContent = "Afficher le QR";
            }
            return;
        }

        try {
            const result = await window.AuthAPI.getReservationAccessPayload(reservation.id_reservation);
            accessContainer.innerHTML = "";
            appendAccessPayload(accessContainer, result);
            accessContainer.dataset.visible = "true";
            if (triggerButton) {
                triggerButton.textContent = "Masquer le QR";
            }
            status.classList.remove("error");
            status.textContent = "";
        } catch (error) {
            status.classList.add("error");
            status.textContent = error.message || "Impossible d'afficher l'accès temporaire.";
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
                    toggleButton.textContent = "Afficher le QR";
                }
            }
        }
    }

    async function loadSavedRfid() {
        const result = await window.AuthAPI.getAuthMethods();
        const methods = result.results || [];
        const rfid = methods.find((method) => String(method.type_label || "").toUpperCase() === "RFID");
        savedRfidValue = rfid?.display_value || "";
        configureAuthOptions();
    }

    async function loadReservations() {
        if (!reservationsList) return;
        const result = await window.AuthAPI.getReservations();
        renderReservations(reservationsList, result.results || [], cancelReservation, showReservationAccess);
    }

    async function loadStations() {
        const result = await window.AuthAPI.getStations();
        stations = result.results || [];
        renderStationPicker();
        if (stations.length) {
            selectStation(stations[0]);
        }
    }

    async function refreshAvailability() {
        const stationId = stationInput.value;
        const start = ensureFutureStartDate();
        const end = getEndDate();
        updateEndDisplay();

        if (!stationId || !start || !end) {
            renderStationAvailability(availabilityBox, selectedStation, null);
            return;
        }

        try {
            const result = await window.AuthAPI.getReservationAvailability({
                station: stationId,
                date_debut: dateToIso(start),
                date_fin: dateToIso(end),
            });
            renderStationAvailability(availabilityBox, result.station, result);
        } catch (error) {
            availabilityBox.className = "empty-state";
            availabilityBox.textContent = error.message || "Impossible de charger les disponibilités.";
        }
    }

    try {
        configureDurationOptions();
        await Promise.all([loadStations(), loadReservations(), loadSavedRfid()]);
        startInput.value = toLocalInputValue(new Date());
        updateEndDisplay();
        status.textContent = savedRfidValue
            ? "Badge RFID détecté. Il est sélectionné par défaut pour la réservation."
            : "QR code disponible pour cette réservation.";
        if (!userHasPhoneNumber) {
            status.textContent = savedRfidValue
                ? "Badge RFID détecté. Il est sélectionné par défaut pour la réservation."
                : "QR code disponible pour cette réservation.";
        }
        window.setInterval(refreshVisibleAccesses, 15000);
        document.addEventListener("visibilitychange", () => {
            if (!document.hidden) refreshVisibleAccesses();
        });
    } catch (_error) {
        status.classList.add("error");
        status.textContent = "Impossible de charger la réservation.";
        return;
    }

    stationSearch.addEventListener("input", renderStationPicker);
    startInput.addEventListener("change", refreshAvailability);
    durationSelect.addEventListener("change", refreshAvailability);
    authModeSelect.addEventListener("change", updateAuthFieldVisibility);

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        status.classList.remove("error");
        const submitButton = form.querySelector('button[type="submit"]');
        submitButton.disabled = true;

        const start = ensureFutureStartDate();
        const end = getEndDate();
        if (!start || !end) {
            status.classList.add("error");
            status.textContent = "Choisissez une date et une heure de début.";
            submitButton.disabled = false;
            return;
        }

        if (!stationInput.value) {
            status.classList.add("error");
            status.textContent = "Choisissez une station sur la carte.";
            submitButton.disabled = false;
            return;
        }

        if (authModeSelect.value === "rfid" && !savedRfidValue) {
            status.classList.add("error");
            status.textContent = "Ajoutez d’abord un badge RFID dans votre profil.";
            submitButton.disabled = false;
            return;
        }

        if (authModeSelect.value === "code" && !userHasPhoneNumber) {
            status.classList.add("error");
            status.textContent = "Ajoutez un numéro de téléphone dans votre profil pour utiliser le code SMS temporaire.";
            submitButton.disabled = false;
            return;
        }

        const payload = {
            station: stationInput.value,
            date_debut: dateToIso(start),
            date_fin: dateToIso(end),
            duration_minutes: getSelectedDurationMinutes(),
            auth_mode: authModeSelect.value,
            auth_value: authModeSelect.value === "rfid" ? savedRfidValue : "",
        };

        try {
            await window.AuthAPI.createReservation(payload);
            status.textContent = "Réservation créée avec succès. Le QR est disponible dans vos réservations, le code SMS peut y être envoyé.";
            form.reset();
            stationInput.value = selectedStation?.id_station || "";
            startInput.value = toLocalInputValue(new Date());
            durationSelect.value = String(DEFAULT_RESERVATION_DURATION_MINUTES);
            configureAuthOptions();
            updateEndDisplay();
            await loadReservations();
            await refreshAvailability();
            window.setTimeout(() => {
                window.location.href = "/dashboard.html#reservations";
            }, 900);
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
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initReservationPage, { once: true });
} else {
    initReservationPage();
}
