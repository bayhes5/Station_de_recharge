function resolveApiBaseUrl() {
    window.localStorage.removeItem("terminalApiBaseUrl");
    return `${window.location.origin}/backend-api`;
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
    ]);
    if (allowedStaticPaths.has(path)) {
        return `${API_BASE_URL}${path}`;
    }

    const sessionMatch = path.match(/^\/terminal\/mobile-sessions\/([A-Za-z0-9_-]{8,128})\/(consume\/)?$/);
    if (sessionMatch) {
        const suffix = sessionMatch[2] || "";
        return `${API_BASE_URL}/terminal/mobile-sessions/${sessionMatch[1]}/${suffix}`;
    }

    throw new Error("Chemin API locale refuse.");
}

const API_BASE_URL = resolveApiBaseUrl();
const EDGE_BASE_URL = window.location.origin;
const KEYPAD_PATTERN = /^[0-9A-D]$/;
const SESSION_TOKEN_PATTERN = /^[A-Za-z0-9_-]{8,128}$/;
const TERMINAL_STATION_ID =
    new URLSearchParams(window.location.search).get("station_id")
    || window.localStorage.getItem("terminalStationId")
    || "";
const RFID_POLL_INTERVAL_MS = 700;

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

let activeScreen = "home";
let activeCodeField = "reservation";
let submitting = false;
let homeTimer = null;
let lastRfidScanId = Number(window.sessionStorage.getItem("lastRfidScanId") || "0");
let mobileSessionToken = "";
let mobileSessionTimer = null;

function showScreen(name) {
    activeScreen = name;
    screens.forEach((screen) => {
        screen.classList.toggle("active", screen.id === `screen-${name}`);
    });
    window.clearTimeout(homeTimer);

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
    reservationDisplay.textContent = maskValue(reservationCodeInput.value, 8);
    authDisplay.textContent = maskValue(authValueInput.value, 12);
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
    const maxLength = input === authValueInput ? 12 : 8;
    input.value = `${input.value}${key}`.slice(0, maxLength);
    updateDisplays();
    if (input === reservationCodeInput && input.value.length === 8) {
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
        throw new Error(data.detail || "Authentification offline refusee.");
    }
    return data;
}

async function createMobileSession() {
    return sendApi("/terminal/mobile-sessions/", TERMINAL_STATION_ID ? { station_id: TERMINAL_STATION_ID } : {});
}

async function consumeMobileSession(token) {
    const safeToken = safeSessionToken(token);
    if (!safeToken) {
        throw new Error("Session mobile invalide.");
    }
    return sendApi(
        `/terminal/mobile-sessions/${safeToken}/consume/`,
        TERMINAL_STATION_ID ? { station_id: TERMINAL_STATION_ID } : {},
    );
}

async function readMobileSession(token) {
    const safeToken = safeSessionToken(token);
    if (!safeToken) {
        throw new Error("Session mobile invalide.");
    }
    let response;
    try {
        response = await fetch(terminalApiUrl(`/terminal/mobile-sessions/${safeToken}/`), {
            method: "GET",
            headers: {
                Accept: "application/json",
            },
        });
    } catch (_error) {
        throw new Error("Session mobile indisponible.");
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
        throw new Error(data.detail || "Session mobile refusee.");
    }

    return data;
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
        throw new Error(data.detail || "Commande MQTT refusee.");
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
    return `ESP32 ${status}${message}`;
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
        throw new Error(data.detail || "Authentification refusee.");
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
        pushEvent("Badge RFID detecte.");
        submitRfid();
        return;
    }

    if (activeScreen === "rfid") {
        rfidValueInput.value = uid;
        setRfidStatus("Badge lu. Verification...");
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
    resultTitle.textContent = success ? "Acces valide" : "Acces refuse";
    resultMessage.textContent = message;
    resultDetails.textContent = details;
    showScreen("result");
    homeTimer = window.setTimeout(resetToHome, success ? 9000 : 12000);
}

function resetToHome() {
    stopMobilePairing();
    reservationCodeInput.value = "";
    authValueInput.value = "";
    qrPayloadInput.value = "";
    rfidValueInput.value = "";
    if (linkCodeInput) {
        linkCodeInput.value = "";
        linkRfidValueInput.value = "";
        updateLinkDisplay();
    }
    setStatus("Pret.");
    setRfidStatus("En attente du badge.");
    setLinkStatus("En attente du code association.");
    updateDisplays();
    showScreen("home");
}

function sessionDetails(result) {
    const session = result.session || {};
    if (!session.station && !session.emplacement) {
        return "";
    }
    return `Station ${session.station || "-"} - emplacement ${session.emplacement || "-"}`;
}

function slotIdFromSession(session) {
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
    });
}

function accessDetails(sessionResult, mqttResult) {
    return [sessionDetails(sessionResult), mqttDetails(mqttResult)].filter(Boolean).join(" | ");
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
            setMobileStatus("Autorisation recue. Demarrage...");
            const consumed = await consumeMobileSession(mobileSessionToken);
            const mqttResult = await startSlotFromSession(consumed);
            pushEvent("Charge demarree depuis le mobile.");
            showResult(true, "Charge demarree depuis le mobile.", accessDetails(consumed, mqttResult));
            return;
        }

        if (session.status === "consumed") {
            stopMobilePairing();
            showResult(true, "Session mobile deja utilisee.", "");
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
    setMobileStatus("Creation de la session mobile...");

    try {
        const result = await createMobileSession();
        const session = result.mobile_session || {};
        mobileSessionToken = session.token || "";
        mobileQrBox.innerHTML = result.qr_svg || "";
        mobileUrlOutput.textContent = result.url || "";
        setMobileStatus("Scannez le QR code avec votre telephone.");
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
    setStatus("Verification en cours...");
    if (payload.auth_mode === "rfid") {
        setRfidStatus("Verification du badge...");
    }
    try {
        const enrichedPayload = TERMINAL_STATION_ID
            ? { ...payload, station_id: TERMINAL_STATION_ID }
            : payload;
        const result = await sendAuthentication(enrichedPayload);
        const mqttResult = await startSlotFromSession(result);
        const details = accessDetails(result, mqttResult);
        pushEvent(successMessage);
        if (payload.auth_mode === "rfid") {
            setRfidStatus("Badge valide.");
        }
        showResult(true, successMessage, details);
    } catch (error) {
        if (error.networkUnavailable) {
            try {
                const offlinePayload = TERMINAL_STATION_ID
                    ? { ...payload, station_id: TERMINAL_STATION_ID }
                    : payload;
                const offlineResult = await sendOfflineAuthentication(offlinePayload);
                const mqttResult = await startSlotFromSession(offlineResult);
                const details = accessDetails(offlineResult, mqttResult);
                const offlineMessage = `${successMessage} Mode degrade offline.`;
                pushEvent(offlineMessage);
                showResult(true, offlineMessage, details);
                return;
            } catch (offlineError) {
                setStatus(offlineError.message, true);
                if (payload.auth_mode === "rfid") {
                    setRfidStatus(offlineError.message, true);
                }
                pushEvent(offlineError.message, true);
                showResult(false, offlineError.message, "Le backend est indisponible et le cache local ne valide pas cet acces.");
                return;
            }
        }
        setStatus(error.message, true);
        if (payload.auth_mode === "rfid") {
            setRfidStatus(error.message, true);
        }
        pushEvent(error.message, true);
        showResult(false, error.message, "Verifiez votre reservation ou choisissez un autre moyen d'acces.");
    } finally {
        submitting = false;
    }
}

function submitCode() {
    const reservationCode = reservationCodeInput.value.trim().toUpperCase();
    const authValue = authValueInput.value.trim().toUpperCase();
    if (reservationCode.length < 8) {
        setActiveCodeField("reservation");
        setStatus("Completez le code reservation.", true);
        return;
    }
    if (authValue.length < 12) {
        setActiveCodeField("auth");
        setStatus("Completez le code SMS temporaire.", true);
        return;
    }
    submitPayload(
        {
            reservation_code: reservationCode,
            auth_mode: "code",
            auth_value: authValue,
        },
        "Charge demarree avec code SMS temporaire.",
    );
}

function submitRfid() {
    const authValue = rfidValueInput.value.trim();
    if (!authValue) {
        setRfidStatus("Presentez le badge RFID.", true);
        rfidValueInput.focus();
        return;
    }
    submitPayload(
        {
            auth_mode: "rfid",
            auth_value: authValue,
        },
        "Charge demarree avec badge RFID.",
    );
}

async function submitLink() {
    const linkCode = linkCodeInput.value.trim().toUpperCase();
    const uid = linkRfidValueInput.value.trim();
    if (linkCode.length < 4) {
        setLinkStatus("Completez le code association.", true);
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
        pushEvent(`Badge RFID associe${pseudo}.`);
        showResult(true, "Badge RFID associe.", "Vous pouvez maintenant utiliser ce badge pour vos reservations.");
    } catch (error) {
        setLinkStatus(error.message, true);
        pushEvent(error.message, true);
        showResult(false, error.message, "Generez un nouveau code depuis votre profil si necessaire.");
    } finally {
        submitting = false;
    }
}

routeButtons.forEach((button) => {
    button.addEventListener("click", () => showScreen(button.dataset.go));
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

qrForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const authValue = qrPayloadInput.value.trim();
    if (!authValue) {
        showResult(false, "Aucun QR code detecte.", "Scannez a nouveau le QR code depuis l'application.");
        return;
    }
    submitPayload(
        {
            auth_mode: "qr",
            auth_value: authValue,
        },
        "Charge demarree avec QR code.",
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
