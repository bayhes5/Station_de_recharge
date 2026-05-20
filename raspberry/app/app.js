function resolveApiBaseUrl() {
    window.localStorage.removeItem("terminalApiBaseUrl");
    return `${window.location.origin}${KIOSK_BASE_PATH}/backend-api`;
}

function safeSessionToken(token) {
    const normalized = String(token || "").trim();
    return SESSION_TOKEN_PATTERN.test(normalized) ? normalized : "";
}

function terminalApiUrl(path) {
    const allowedStaticPaths = new Set([
        "/terminal/authenticate/",
        "/terminal/link-rfid/",
        "/terminal/mobile-sessions/",
        "/terminal/mobile-sessions/status/",
        "/terminal/mobile-sessions/consume/",
        "/terminal/sessions/stop/",
    ]);
    if (allowedStaticPaths.has(path)) {
        return `${API_BASE_URL}${path}`;
    }

    throw new Error("Chemin API locale refusé.");
}

function isSafeSvgReference(value) {
    const trimmed = String(value || "").trim();
    if (!trimmed) {
        return false;
    }
    if (trimmed.startsWith("#")) {
        return true;
    }
    try {
        const url = new URL(trimmed, window.location.origin);
        return url.protocol === "https:" || url.protocol === "http:";
    } catch (_error) {
        return false;
    }
}

function renderQrSvg(container, svgText) {
    container.replaceChildren();

    if (!svgText) {
        return false;
    }

    const documentParser = new DOMParser();
    const parsedDocument = documentParser.parseFromString(svgText, "image/svg+xml");
    const svg = parsedDocument.documentElement;

    if (!svg || svg.tagName.toLowerCase() !== "svg" || svg.querySelector("script, foreignObject")) {
        return false;
    }

    svg.querySelectorAll("*").forEach((element) => {
        [...element.attributes].forEach((attribute) => {
            const name = attribute.name.toLowerCase();
            if (
                name.startsWith("on")
                || ((name === "href" || name === "xlink:href") && !isSafeSvgReference(attribute.value))
            ) {
                element.removeAttribute(attribute.name);
            }
        });
    });

    container.appendChild(document.importNode(svg, true));
    return true;
}

const KIOSK_BASE_PATH = window.location.pathname.startsWith("/kiosk/") ? "/kiosk" : "";
const API_BASE_URL = resolveApiBaseUrl();
const EDGE_BASE_URL = `${window.location.origin}${KIOSK_BASE_PATH}`;
const MOBILE_FRONTEND_BASE_URL = resolveMobileFrontendBaseUrl();
const KEYPAD_PATTERN = /^[0-9A-D]$/;
const SESSION_TOKEN_PATTERN = /^[A-Za-z0-9_-]{8,128}$/;
const RESERVATION_CODE_LENGTH = 8;
const SMS_ACCESS_CODE_LENGTH = 8;
const TERMINAL_STATION_ID =
    new URLSearchParams(window.location.search).get("station_id")
    || window.localStorage.getItem("terminalStationId")
    || "";
const TERMINAL_BORNE_ID =
    new URLSearchParams(window.location.search).get("borne_id")
    || window.localStorage.getItem("terminalBorneId")
    || "";
const RFID_POLL_INTERVAL_MS = 700;
const DEFAULT_IDLE_RETURN_SECONDS = 120;
const idleTimeoutParam = Number(new URLSearchParams(window.location.search).get("idle_timeout"));
const idleTimeoutStorage = Number(window.localStorage.getItem("terminalIdleTimeoutSeconds"));
const IDLE_RETURN_MS = (
    Number.isFinite(idleTimeoutParam) && idleTimeoutParam > 0
        ? idleTimeoutParam
        : Number.isFinite(idleTimeoutStorage) && idleTimeoutStorage > 0
            ? idleTimeoutStorage
            : DEFAULT_IDLE_RETURN_SECONDS
) * 1000;

const screens = [...document.querySelectorAll(".screen")];
const routeButtons = [...document.querySelectorAll("[data-go]")];
const backHomeButtons = [...document.querySelectorAll(".back-home")];
const keypadButtons = [...document.querySelectorAll(".keypad-key")];
const codeFieldButtons = [...document.querySelectorAll(".code-field")];

const statusBox = document.getElementById("status");
const eventsBox = document.getElementById("events");
const reservationCodeInput = document.getElementById("reservation-code");
const authValueInput = document.getElementById("auth-value");
const reservationDisplay = document.getElementById("reservation-display");
const authDisplay = document.getElementById("auth-display");
const qrForm = document.getElementById("qr-form");
const qrPayloadInput = document.getElementById("qr-payload");
const rfidValueInput = document.getElementById("rfid-value");
const rfidStatusBox = document.getElementById("rfid-status");
const linkCodeInput = document.getElementById("link-code");
const linkCodeDisplay = document.getElementById("link-code-display");
const linkRfidValueInput = document.getElementById("link-rfid-value");
const linkStatusBox = document.getElementById("link-status");
const mobileStatusBox = document.getElementById("mobile-status");
const mobileQrBox = document.getElementById("mobile-qr");
const mobileUrlOutput = document.getElementById("mobile-url");
const mobileRefreshButton = document.getElementById("mobile-refresh");
const mobileCancelButton = document.getElementById("mobile-cancel");
const resultScreen = document.getElementById("screen-result");
const resultBadge = document.getElementById("result-badge");
const resultTitle = document.getElementById("result-title");
const resultMessage = document.getElementById("result-message");
const resultDetails = document.getElementById("result-details");
const readySlot = document.getElementById("ready-slot");
const readyMessage = document.getElementById("ready-message");
const readyDetails = document.getElementById("ready-details");
const readyStartButton = document.getElementById("ready-start");
const readyCancelButton = document.getElementById("ready-cancel");
const chargingSlot = document.getElementById("charging-slot");
const chargingMessage = document.getElementById("charging-message");
const chargingDetails = document.getElementById("charging-details");
const chargingStopButton = document.getElementById("charging-stop");

let activeScreen = "home";
let activeCodeField = "reservation";
let submitting = false;
let homeTimer = null;
let inactivityTimer = null;
let lastRfidScanId = Number(window.sessionStorage.getItem("lastRfidScanId") || "0");
let mobileSessionToken = "";
let mobileSessionTimer = null;
let currentCharge = null;

function showScreen(name) {
    activeScreen = name;
    screens.forEach((screen) => {
        screen.classList.toggle("active", screen.id === `screen-${name}`);
    });
    window.clearTimeout(homeTimer);
    armInactivityTimer();

    if (name === "qr") {
        qrPayloadInput.focus();
    }
    if (name === "rfid") {
        rfidValueInput.value = "";
        setRfidStatus("En attente du badge.");
        rfidValueInput.focus();
    }
    if (name === "code") {
        setActiveCodeField("reservation");
        updateDisplays();
    }
    if (name === "link") {
        linkCodeInput.value = "";
        linkRfidValueInput.value = "";
        setLinkStatus("En attente du code association.");
        updateLinkDisplay();
    }
    if (name === "mobile") {
        startMobilePairing();
    } else {
        stopMobilePairing();
    }
}

function armInactivityTimer() {
    window.clearTimeout(inactivityTimer);
    if (activeScreen === "home" || activeScreen === "charging") {
        return;
    }
    inactivityTimer = window.setTimeout(resetToHome, IDLE_RETURN_MS);
}

function registerActivity() {
    armInactivityTimer();
}

function pushEvent(message, error = false) {
    const time = new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
    eventsBox.textContent = `${time} - ${message}`;
    eventsBox.style.color = error ? "var(--danger)" : "var(--muted)";
}

function setStatus(message, error = false) {
    if (!statusBox) {
        return;
    }
    statusBox.textContent = message;
    statusBox.classList.toggle("error", error);
}

function setRfidStatus(message, error = false) {
    if (!rfidStatusBox) {
        return;
    }
    rfidStatusBox.textContent = message;
    rfidStatusBox.classList.toggle("error", error);
}

function setLinkStatus(message, error = false) {
    if (!linkStatusBox) {
        return;
    }
    linkStatusBox.textContent = message;
    linkStatusBox.classList.toggle("error", error);
}

function setMobileStatus(message, error = false) {
    if (!mobileStatusBox) {
        return;
    }
    mobileStatusBox.textContent = message;
    mobileStatusBox.classList.toggle("error", error);
}

function setActiveCodeField(field) {
    activeCodeField = field;
    codeFieldButtons.forEach((button) => {
        button.classList.toggle("active", button.dataset.field === field);
    });
}

function maskValue(value, length) {
    return value.padEnd(length, "-");
}

function updateDisplays() {
    reservationDisplay.textContent = maskValue(reservationCodeInput.value, RESERVATION_CODE_LENGTH);
    authDisplay.textContent = maskValue(authValueInput.value, SMS_ACCESS_CODE_LENGTH);
}

function updateLinkDisplay() {
    if (linkCodeDisplay) {
        linkCodeDisplay.textContent = maskValue(linkCodeInput.value, 4);
    }
}

function activeInput() {
    return activeCodeField === "reservation" ? reservationCodeInput : authValueInput;
}

function appendLinkKey(key) {
    if (!KEYPAD_PATTERN.test(key)) {
        return;
    }
    linkCodeInput.value = `${linkCodeInput.value}${key}`.slice(0, 4);
    updateLinkDisplay();
    if (linkCodeInput.value.length === 4) {
        linkRfidValueInput.focus();
        setLinkStatus("Code saisi. Passez votre badge.");
    }
}

function backspaceLinkKey() {
    linkCodeInput.value = linkCodeInput.value.slice(0, -1);
    updateLinkDisplay();
}

function appendKey(key) {
    if (!KEYPAD_PATTERN.test(key)) {
        return;
    }
    const input = activeInput();
    const maxLength = input === authValueInput ? SMS_ACCESS_CODE_LENGTH : RESERVATION_CODE_LENGTH;
    input.value = `${input.value}${key}`.slice(0, maxLength);
    updateDisplays();
    if (input === reservationCodeInput && input.value.length === RESERVATION_CODE_LENGTH) {
        setActiveCodeField("auth");
    }
}

function backspaceKey() {
    const input = activeInput();
    input.value = input.value.slice(0, -1);
    updateDisplays();
}

function clearActiveField() {
    activeInput().value = "";
    updateDisplays();
}

async function sendAuthentication(payload) {
    return sendApi("/terminal/authenticate/", payload);
}

function terminalContextPayload() {
    return {
        ...(TERMINAL_STATION_ID ? { station_id: TERMINAL_STATION_ID } : {}),
        ...(TERMINAL_BORNE_ID ? { borne_id: TERMINAL_BORNE_ID } : {}),
    };
}

function resolveMobileFrontendBaseUrl() {
    if (window.__MOBILE_FRONTEND_BASE_URL__) {
        return String(window.__MOBILE_FRONTEND_BASE_URL__).replace(/\/$/, "");
    }

    if (KIOSK_BASE_PATH) {
        return window.location.origin;
    }

    const frontendUrl = new URL(window.location.origin);
    if (frontendUrl.port === "9000") {
        frontendUrl.port = "5173";
    }
    return frontendUrl.toString().replace(/\/$/, "");
}

async function sendRfidLink(payload) {
    return sendApi("/terminal/link-rfid/", payload);
}

async function sendOfflineAuthentication(payload) {
    let response;
    try {
        response = await fetch(`${EDGE_BASE_URL}/offline/authenticate`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Accept: "application/json",
            },
            body: JSON.stringify(payload),
        });
    } catch (_error) {
        throw new Error("Cache offline local indisponible.");
    }

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.detail || "Authentification offline refusée.");
    }
    return data;
}

async function createMobileSession() {
    return sendApi(
        "/terminal/mobile-sessions/",
        {
            ...terminalContextPayload(),
            frontend_origin: MOBILE_FRONTEND_BASE_URL,
        },
    );
}

async function consumeMobileSession(token) {
    const safeToken = safeSessionToken(token);
    if (!safeToken) {
        throw new Error("Session mobile invalide.");
    }
    return sendApi(
        "/terminal/mobile-sessions/consume/",
        {
            token: safeToken,
            ...terminalContextPayload(),
        },
    );
}

async function readMobileSession(token) {
    const safeToken = safeSessionToken(token);
    if (!safeToken) {
        throw new Error("Session mobile invalide.");
    }
    return sendApi(
        "/terminal/mobile-sessions/status/",
        {
            token: safeToken,
            ...terminalContextPayload(),
        },
    );
}

async function sendEdgeMqttCommand(payload) {
    let response;
    try {
        response = await fetch(`${EDGE_BASE_URL}/mqtt/command`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Accept: "application/json",
            },
            body: JSON.stringify(payload),
        });
    } catch (_error) {
        throw new Error("Commande MQTT locale indisponible.");
    }

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.detail || "Commande MQTT refusée.");
    }
    return data;
}

function mqttDetails(result) {
    const mqtt = result?.mqtt || {};
    if (!mqtt.ack_received) {
        return "";
    }
    const ackPayload = mqtt.ack?.payload || {};
    const status = ackPayload.status || ackPayload.state || "confirme";
    const message = ackPayload.message ? ` - ${ackPayload.message}` : "";
    const prefix = mqtt.command_confirmed === false ? "ESP32 non confirmé" : "ESP32";
    return `${prefix} ${status}${message}`;
}

function chargeStateDetails(result) {
    const state = result?.charge_state?.state || "";
    if (!state) {
        return "";
    }
    const labels = {
        reserved: "réservation connue localement",
        access_validated: "accès validé",
        waiting_plug: "en attente du câble et du boîtier fermé",
        charging: "charge confirmée",
        stopping: "arrêt en cours",
        stopped: "charge arrêtée",
        error: "état local en erreur",
    };
    return `Raspberry: ${labels[state] || state}`;
}

async function readLatestRfidScan() {
    let response;
    try {
        response = await fetch(`${EDGE_BASE_URL}/rfid/scan?since=${lastRfidScanId}`, {
            method: "GET",
            headers: {
                Accept: "application/json",
            },
        });
    } catch (_error) {
        return null;
    }

    if (!response.ok) {
        return null;
    }

    const data = await response.json().catch(() => ({}));
    return data.scan || null;
}

async function sendApi(path, payload) {
    let response;
    try {
        response = await fetch(terminalApiUrl(path), {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Accept: "application/json",
            },
            body: JSON.stringify(payload),
        });
    } catch (_error) {
        const error = new Error("Impossible de joindre l'API locale.");
        error.networkUnavailable = true;
        throw error;
    }

    const text = await response.text();
    let data = {};
    if (text) {
        try {
            data = JSON.parse(text);
        } catch (_error) {
            data = { detail: text };
        }
    }

    if (!response.ok) {
        throw new Error(data.detail || "Authentification refusée.");
    }

    return data;
}

function rememberRfidScan(scan) {
    lastRfidScanId = Number(scan.id || lastRfidScanId);
    window.sessionStorage.setItem("lastRfidScanId", String(lastRfidScanId));
}

function handleRfidScan(scan) {
    const uid = String(scan.uid || "").trim();
    if (!uid || submitting) {
        return;
    }

    rememberRfidScan(scan);

    if (activeScreen === "home") {
        showScreen("rfid");
        rfidValueInput.value = uid;
        pushEvent("Badge RFID détecté.");
        submitRfid();
        return;
    }

    if (activeScreen === "rfid") {
        rfidValueInput.value = uid;
        setRfidStatus("Badge lu. Vérification...");
        submitRfid();
        return;
    }

    if (activeScreen === "link") {
        linkRfidValueInput.value = uid;
        if (linkCodeInput.value.length === 4) {
            setLinkStatus("Badge lu. Association...");
            submitLink();
        } else {
            setLinkStatus("Badge lu. Entrez le code association.");
        }
    }
}

async function pollRfidScans() {
    const scan = await readLatestRfidScan();
    if (scan) {
        handleRfidScan(scan);
    }
}

function showResult(success, message, details = "") {
    resultScreen.classList.toggle("error", !success);
    resultBadge.textContent = success ? "OK" : "!";
    resultTitle.textContent = success ? "Accès valide" : "Accès refusé";
    resultMessage.textContent = message;
    resultDetails.textContent = details;
    showScreen("result");
    homeTimer = window.setTimeout(resetToHome, success ? 9000 : 12000);
}

async function closeTerminalSession(sessionId) {
    const safeSessionId = String(sessionId || "").trim();
    if (!safeSessionId) {
        throw new Error("Session de charge invalide.");
    }
    return sendApi(
        "/terminal/sessions/stop/",
        {
            session_id: safeSessionId,
            ...terminalContextPayload(),
        },
    );
}

function resetToHome() {
    stopMobilePairing();
    window.clearTimeout(inactivityTimer);
    reservationCodeInput.value = "";
    authValueInput.value = "";
    qrPayloadInput.value = "";
    rfidValueInput.value = "";
    if (linkCodeInput) {
        linkCodeInput.value = "";
        linkRfidValueInput.value = "";
        updateLinkDisplay();
    }
    setStatus("Prêt.");
    setRfidStatus("En attente du badge.");
    setLinkStatus("En attente du code association.");
    updateDisplays();
    showScreen("home");
}

function extractSession(result) {
    return result?.session || {};
}

function sessionDetails(result) {
    const session = extractSession(result);
    if (!session.station && !session.emplacement) {
        return "";
    }
    return `Station ${session.station || "-"} - borne ${session.borne || "-"} - emplacement ${session.emplacement || "-"}`;
}

function slotLabelFromSession(session) {
    if (!session?.emplacement) {
        return "-";
    }
    return session?.borne ? `${session.borne} / emplacement ${session.emplacement}` : session.emplacement;
}

function slotIdFromSession(session) {
    if (session?.slot_id) {
        return String(session.slot_id);
    }
    if (!session?.emplacement) {
        return "";
    }
    return `slot${session.emplacement}`;
}

async function startSlotFromSession(result) {
    const session = result.session || {};
    const slotId = slotIdFromSession(session);
    if (!slotId) {
        return null;
    }
    return sendEdgeMqttCommand({
        slot_id: slotId,
        action: "START",
        session_id: session.id || "",
        topic_prefix: session.mqtt_prefix || session.topic_prefix || "",
        station: session.station || "",
        borne: session.borne || "",
        emplacement: session.emplacement || "",
    });
}

function accessDetails(sessionResult, mqttResult) {
    return [
        sessionDetails(sessionResult),
        mqttDetails(mqttResult),
        chargeStateDetails(mqttResult),
    ].filter(Boolean).join(" | ");
}

function showChargeReady(result, message, details = "") {
    const session = extractSession(result);
    currentCharge = {
        session,
        message,
        details,
    };
    readySlot.textContent = slotLabelFromSession(session);
    readyMessage.textContent = message || "Votre réservation est validée. Branchez votre vélo puis démarrez la charge.";
    readyDetails.textContent = details || sessionDetails(result) || "Emplacement attribué.";
    pushEvent("Accès validé. En attente du démarrage de charge.");
    showScreen("ready");
}

function showCharging(mqttResult = null) {
    const session = currentCharge?.session || {};
    chargingSlot.textContent = slotLabelFromSession(session);
    chargingMessage.textContent = `La charge est active sur ${slotLabelFromSession(session)}.`;
    chargingDetails.textContent = [
        currentCharge?.details || sessionDetails({ session }),
        mqttDetails(mqttResult),
        chargeStateDetails(mqttResult),
        "Télémétrie ESP32 publiée vers MQTT pour la supervision Grafana.",
    ].filter(Boolean).join(" | ");
    pushEvent("Chargement en cours.");
    showScreen("charging");
}

async function startCurrentCharge() {
    if (!currentCharge || submitting) {
        return;
    }
    submitting = true;
    readyStartButton.disabled = true;
    readyStartButton.textContent = "Démarrage...";
    try {
        const mqttResult = await startSlotFromSession({ session: currentCharge.session });
        showCharging(mqttResult);
    } catch (error) {
        pushEvent(error.message, true);
        showResult(false, error.message, "La réservation est validée, mais l'ESP32 n'a pas accepté le démarrage.");
    } finally {
        submitting = false;
        readyStartButton.disabled = false;
        readyStartButton.textContent = "Démarrer la charge";
    }
}

async function stopCurrentCharge() {
    if (!currentCharge || submitting) {
        resetToHome();
        return;
    }

    const session = currentCharge.session || {};
    const slotId = slotIdFromSession(session);
    if (!slotId) {
        showResult(false, "Arrêt impossible.", "Aucun emplacement actif n'est associé à cette session.");
        return;
    }

    submitting = true;
    chargingStopButton.disabled = true;
    chargingStopButton.textContent = "Arrêt...";
    try {
        const mqttResult = await sendEdgeMqttCommand({
            slot_id: slotId,
            action: "STOP",
            session_id: session.id || "",
            topic_prefix: session.mqtt_prefix || session.topic_prefix || "",
            station: session.station || "",
            borne: session.borne || "",
            emplacement: session.emplacement || "",
        });
        let closeResult = null;
        try {
            closeResult = await closeTerminalSession(session.id);
        } catch (closeError) {
            pushEvent(`Charge arrêtée, clôture backend à reprendre: ${closeError.message}`, true);
        }
        const details = [
            sessionDetails(closeResult || { session }),
            mqttDetails(mqttResult),
            chargeStateDetails(mqttResult),
            closeResult ? "Session clôturée dans le backend." : "Session arrêtée côté ESP32, clôture backend non confirmée.",
        ].filter(Boolean).join(" | ");
        currentCharge = null;
        pushEvent("Charge arrêtée.");
        showResult(true, "Charge arrêtée.", details);
    } catch (error) {
        pushEvent(error.message, true);
        showResult(false, error.message, "La commande STOP n'a pas été confirmée par l'ESP32.");
    } finally {
        submitting = false;
        chargingStopButton.disabled = false;
        chargingStopButton.textContent = "Arrêter la charge";
    }
}

function stopMobilePairing() {
    window.clearInterval(mobileSessionTimer);
    mobileSessionTimer = null;
}

async function pollMobileSession() {
    if (!mobileSessionToken || submitting) {
        return;
    }

    try {
        const result = await readMobileSession(mobileSessionToken);
        const session = result.mobile_session || {};
        if (session.status === "pending") {
            setMobileStatus(`En attente de confirmation mobile (${session.expires_in || 0}s).`);
            return;
        }

        if (session.status === "authorized") {
            stopMobilePairing();
            submitting = true;
            setMobileStatus("Autorisation reçue.");
            const consumed = await consumeMobileSession(mobileSessionToken);
            const details = sessionDetails(consumed);
            showChargeReady(
                consumed,
                "Branchez votre vélo puis lancez la charge.",
                details,
            );
            return;
        }

        if (session.status === "consumed") {
            stopMobilePairing();
            showResult(true, "Session mobile déjà utilisée.", "");
        }
    } catch (error) {
        stopMobilePairing();
        setMobileStatus(error.message, true);
        pushEvent(error.message, true);
    } finally {
        submitting = false;
    }
}

async function startMobilePairing() {
    if (!mobileQrBox || !mobileUrlOutput) {
        return;
    }

    stopMobilePairing();
    mobileSessionToken = "";
    mobileQrBox.replaceChildren();
    mobileUrlOutput.textContent = "";
    setMobileStatus("Création de la session mobile...");

    try {
        const result = await createMobileSession();
        const session = result.mobile_session || {};
        mobileSessionToken = session.token || "";
        if (!renderQrSvg(mobileQrBox, result.qr_svg)) {
            mobileQrBox.textContent = "QR code indisponible.";
        }
        mobileUrlOutput.textContent = result.url || "";
        setMobileStatus("Scannez le QR code avec votre téléphone.");
        mobileSessionTimer = window.setInterval(pollMobileSession, 2000);
    } catch (error) {
        setMobileStatus(error.message, true);
        pushEvent(error.message, true);
    }
}

async function submitPayload(payload, successMessage) {
    if (submitting) {
        return;
    }
    submitting = true;
    setStatus("Vérification en cours...");
    if (payload.auth_mode === "rfid") {
        setRfidStatus("Vérification du badge...");
    }
    try {
        const enrichedPayload = { ...payload, ...terminalContextPayload() };
        const result = await sendAuthentication(enrichedPayload);
        const details = sessionDetails(result);
        pushEvent(successMessage);
        if (payload.auth_mode === "rfid") {
            setRfidStatus("Badge valide.");
        }
        showChargeReady(
            result,
            "Branchez votre vélo puis lancez la charge.",
            details,
        );
    } catch (error) {
        if (error.networkUnavailable) {
            try {
                const offlinePayload = { ...payload, ...terminalContextPayload() };
                const offlineResult = await sendOfflineAuthentication(offlinePayload);
                const details = `${sessionDetails(offlineResult)} | Mode dégradé offline.`;
                const offlineMessage = "Branchez votre vélo puis lancez la charge.";
                pushEvent(offlineMessage);
                showChargeReady(offlineResult, offlineMessage, details);
                return;
            } catch (offlineError) {
                setStatus(offlineError.message, true);
                if (payload.auth_mode === "rfid") {
                    setRfidStatus(offlineError.message, true);
                }
                pushEvent(offlineError.message, true);
                showResult(false, offlineError.message, "Le backend est indisponible et le cache local ne valide pas cet accès.");
                return;
            }
        }
        setStatus(error.message, true);
        if (payload.auth_mode === "rfid") {
            setRfidStatus(error.message, true);
        }
        pushEvent(error.message, true);
        showResult(false, error.message, "Vérifiez votre réservation ou choisissez un autre moyen d'accès.");
    } finally {
        submitting = false;
    }
}

function submitCode() {
    const reservationCode = reservationCodeInput.value.trim().toUpperCase();
    const authValue = authValueInput.value.trim().toUpperCase();
    if (reservationCode.length < RESERVATION_CODE_LENGTH) {
        setActiveCodeField("reservation");
        setStatus("Complétez le code réservation.", true);
        return;
    }
    if (authValue.length < SMS_ACCESS_CODE_LENGTH) {
        setActiveCodeField("auth");
        setStatus("Complétez le code SMS temporaire.", true);
        return;
    }
    submitPayload(
        {
            reservation_code: reservationCode,
            auth_mode: "code",
            auth_value: authValue,
        },
        "Accès validé avec code SMS temporaire.",
    );
}

function submitRfid() {
    const authValue = rfidValueInput.value.trim();
    if (!authValue) {
        setRfidStatus("Présentez le badge RFID.", true);
        rfidValueInput.focus();
        return;
    }
    submitPayload(
        {
            auth_mode: "rfid",
            auth_value: authValue,
        },
        "Accès validé avec badge RFID.",
    );
}

async function submitLink() {
    const linkCode = linkCodeInput.value.trim().toUpperCase();
    const uid = linkRfidValueInput.value.trim();
    if (linkCode.length < 4) {
        setLinkStatus("Complétez le code association.", true);
        return;
    }
    if (!uid) {
        setLinkStatus("Passez votre badge RFID.", true);
        linkRfidValueInput.focus();
        return;
    }
    if (submitting) {
        return;
    }
    submitting = true;
    setLinkStatus("Association du badge...");
    try {
        const result = await sendRfidLink({
            link_code: linkCode,
            uid,
        });
        const pseudo = result.user?.pseudo ? ` pour ${result.user.pseudo}` : "";
        pushEvent(`Badge RFID associé${pseudo}.`);
        showResult(true, "Badge RFID associé.", "Vous pouvez maintenant utiliser ce badge pour vos réservations.");
    } catch (error) {
        setLinkStatus(error.message, true);
        pushEvent(error.message, true);
        showResult(false, error.message, "Générez un nouveau code depuis votre profil si nécessaire.");
    } finally {
        submitting = false;
    }
}

routeButtons.forEach((button) => {
    button.addEventListener("click", () => showScreen(button.dataset.go));
});

["pointerdown", "keydown", "touchstart"].forEach((eventName) => {
    document.addEventListener(eventName, registerActivity, { passive: true });
});

backHomeButtons.forEach((button) => {
    button.addEventListener("click", resetToHome);
});

codeFieldButtons.forEach((button) => {
    button.addEventListener("click", () => setActiveCodeField(button.dataset.field));
});

keypadButtons.forEach((button) => {
    button.addEventListener("click", () => {
        if (button.dataset.action === "backspace") {
            activeScreen === "link" ? backspaceLinkKey() : backspaceKey();
            return;
        }
        if (button.dataset.action === "submit") {
            if (activeScreen === "rfid") {
                submitRfid();
                return;
            }
            if (activeScreen === "link") {
                submitLink();
                return;
            }
            submitCode();
            return;
        }
        if (activeScreen === "link") {
            appendLinkKey(button.dataset.key || "");
            return;
        }
        appendKey(button.dataset.key || "");
    });
});

document.getElementById("clear-field").addEventListener("click", clearActiveField);
document.getElementById("submit-code").addEventListener("click", submitCode);
const rfidClearButton = document.getElementById("rfid-clear");
const rfidSubmitButton = document.getElementById("submit-rfid");
if (rfidClearButton) {
    rfidClearButton.addEventListener("click", () => {
        rfidValueInput.value = "";
        setRfidStatus("En attente du badge.");
        updateDisplays();
        rfidValueInput.focus();
    });
}
if (rfidSubmitButton) {
    rfidSubmitButton.addEventListener("click", submitRfid);
}
const linkClearButton = document.getElementById("link-clear");
const linkSubmitButton = document.getElementById("submit-link");
if (linkClearButton) {
    linkClearButton.addEventListener("click", () => {
        linkCodeInput.value = "";
        linkRfidValueInput.value = "";
        updateLinkDisplay();
        setLinkStatus("En attente du code association.");
    });
}
if (linkSubmitButton) {
    linkSubmitButton.addEventListener("click", submitLink);
}
if (mobileRefreshButton) {
    mobileRefreshButton.addEventListener("click", startMobilePairing);
}
if (mobileCancelButton) {
    mobileCancelButton.addEventListener("click", resetToHome);
}
if (readyStartButton) {
    readyStartButton.addEventListener("click", startCurrentCharge);
}
if (readyCancelButton) {
    readyCancelButton.addEventListener("click", resetToHome);
}
if (chargingStopButton) {
    chargingStopButton.addEventListener("click", stopCurrentCharge);
}

qrForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const authValue = qrPayloadInput.value.trim();
    if (!authValue) {
        showResult(false, "Aucun QR code détecté.", "Scannez à nouveau le QR code depuis l'application.");
        return;
    }
    submitPayload(
        {
            auth_mode: "qr",
            auth_value: authValue,
        },
        "Accès validé avec QR code.",
    );
});

qrPayloadInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && qrPayloadInput.value.trim()) {
        event.preventDefault();
        qrForm.requestSubmit();
    }
});

rfidValueInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
        event.preventDefault();
        submitRfid();
    }
});

linkRfidValueInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
        event.preventDefault();
        submitLink();
    }
});

document.addEventListener("keydown", (event) => {
    if (activeScreen !== "code" && activeScreen !== "link") {
        return;
    }

    const key = event.key.toUpperCase();
    if (KEYPAD_PATTERN.test(key)) {
        event.preventDefault();
        if (activeScreen === "link") {
            appendLinkKey(key);
            return;
        }
        appendKey(key);
        return;
    }
    if (event.key === "*" || event.key === "Backspace") {
        event.preventDefault();
        if (activeScreen === "link") {
            backspaceLinkKey();
            return;
        }
        backspaceKey();
        return;
    }
    if (event.key === "#" || event.key === "Enter") {
        event.preventDefault();
        if (activeScreen === "link") {
            submitLink();
            return;
        }
        submitCode();
    }
});

showScreen("home");
window.setInterval(pollRfidScans, RFID_POLL_INTERVAL_MS);
