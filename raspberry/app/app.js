const API_BASE_URL = "http://localhost:8000/api";

const modes = [...document.querySelectorAll(".mode-btn")];
const form = document.getElementById("auth-form");
const statusBox = document.getElementById("status");
const reservationCodeInput = document.getElementById("reservation-code");
const authValueInput = document.getElementById("auth-value");
const events = document.getElementById("events");
const keypadButtons = [...document.querySelectorAll(".keypad-key")];

let currentMode = "qr";

function pushEvent(message, error = false) {
    const entry = document.createElement("div");
    entry.className = `event${error ? " error" : ""}`;
    entry.textContent = `${new Date().toLocaleTimeString("fr-FR")} - ${message}`;
    if (events.firstChild && events.firstChild.classList.contains("empty")) {
        events.innerHTML = "";
    }
    events.prepend(entry);
}

function setMode(mode) {
    currentMode = mode;
    modes.forEach((button) => button.classList.toggle("active", button.dataset.mode === mode));

    if (mode === "rfid") {
        authValueInput.placeholder = "Lire le badge RFID";
    } else if (mode === "code") {
        authValueInput.placeholder = "Saisir le code alphanumérique";
    } else {
        authValueInput.placeholder = "Scanner ou coller le contenu du QR code";
    }

    statusBox.textContent = `Mode ${mode.toUpperCase()} sélectionné.`;
}

async function sendAuthentication(payload) {
    let response;
    try {
        response = await fetch(`${API_BASE_URL}/terminal/authenticate/`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Accept: "application/json",
            },
            body: JSON.stringify(payload),
        });
    } catch (_error) {
        throw new Error("Impossible de joindre l'API. Verifie que le backend tourne et que le CORS autorise le kiosk.");
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

function appendToFocusedInput(value) {
    const target = document.activeElement === reservationCodeInput ? reservationCodeInput : authValueInput;
    target.value += value;
    target.focus();
}

modes.forEach((button) => {
    button.addEventListener("click", () => setMode(button.dataset.mode));
});

keypadButtons.forEach((button) => {
    button.addEventListener("click", () => {
        if (button.dataset.action === "clear") {
            authValueInput.value = "";
            authValueInput.focus();
            return;
        }

        if (button.dataset.action === "backspace") {
            const target = document.activeElement === reservationCodeInput ? reservationCodeInput : authValueInput;
            target.value = target.value.slice(0, -1);
            target.focus();
            return;
        }

        appendToFocusedInput(button.dataset.key || "");
    });
});

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    statusBox.classList.remove("error");
    statusBox.textContent = "Vérification en cours...";

    const payload = {
        reservation_code: reservationCodeInput.value.trim(),
        auth_mode: currentMode,
        auth_value: authValueInput.value.trim(),
    };

    try {
        const result = await sendAuthentication(payload);
        statusBox.textContent = "Authentification réussie. Charge démarrée.";
        pushEvent(`Session ouverte pour ${result.session.station} / emplacement ${result.session.emplacement}`);
    } catch (error) {
        statusBox.classList.add("error");
        statusBox.textContent = error.message;
        pushEvent(error.message, true);
    }
});

setMode(currentMode);
