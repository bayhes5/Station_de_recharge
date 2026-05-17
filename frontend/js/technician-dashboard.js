function formatDateTime(value) {
    if (!value) return "-";
    return new Date(value).toLocaleString("fr-FR");
}

function createStatusBadge(label, variant = "") {
    const badge = document.createElement("span");
    badge.className = `badge status-badge${variant ? ` ${variant}` : ""}`;
    badge.textContent = label;
    return badge;
}

function createDataTable(container, columns, rows, emptyMessage) {
    container.innerHTML = "";

    if (!rows.length) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = emptyMessage;
        container.appendChild(empty);
        return;
    }

    const tableWrap = document.createElement("div");
    tableWrap.className = "data-table-wrap admin-data-table-wrap";
    const table = document.createElement("table");
    table.className = "data-table admin-data-table";
    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");

    columns.forEach((column) => {
        const th = document.createElement("th");
        th.textContent = column.label;
        headRow.appendChild(th);
    });
    thead.appendChild(headRow);

    const tbody = document.createElement("tbody");
    rows.forEach((row) => {
        const tr = document.createElement("tr");
        columns.forEach((column) => {
            const td = document.createElement("td");
            const value = column.render ? column.render(row) : row[column.key];
            if (value instanceof Node) {
                td.appendChild(value);
            } else {
                td.textContent = value ?? "-";
            }
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });

    table.appendChild(thead);
    table.appendChild(tbody);
    tableWrap.appendChild(table);
    container.appendChild(tableWrap);
}

function renderMaintenances(container, maintenances) {
    container.innerHTML = "";

    if (!maintenances.length) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = "Aucune maintenance assignée.";
        container.appendChild(empty);
        return;
    }

    maintenances.forEach((maintenance) => {
        const item = document.createElement("article");
        item.className = "list-item";

        const title = document.createElement("strong");
        title.textContent = `${maintenance.station_nom} - ${maintenance.type}`;

        const details = document.createElement("p");
        details.textContent = `${maintenance.status} | ${formatDateTime(maintenance.date_planifiee)}`;

        const description = document.createElement("p");
        description.textContent = maintenance.description || "";

        item.appendChild(title);
        item.appendChild(details);
        item.appendChild(description);
        container.appendChild(item);
    });
}

function renderSupervision(supervision) {
    const stats = supervision.stats || {};
    document.getElementById("tech-stat-online").textContent = stats.devices_online ?? "-";
    document.getElementById("tech-stat-offline").textContent = stats.devices_offline ?? "-";
    document.getElementById("tech-stat-alerts").textContent = stats.active_alerts ?? "-";
    document.getElementById("tech-stat-telemetry").textContent = stats.telemetry_samples_24h ?? "-";

    createDataTable(
        document.getElementById("tech-devices-list"),
        [
            { label: "Emplacement", render: (device) => device.slot_label || device.slot_id || "-" },
            {
                label: "Connexion",
                render: (device) => createStatusBadge(
                    device.online ? "En ligne" : "Hors ligne",
                    device.online ? "success" : "danger"
                ),
            },
            { label: "Dernier état", render: (device) => device.status_display || device.status || "-" },
            { label: "Serrure", render: (device) => device.lock_state || "-" },
            { label: "Firmware", render: (device) => device.firmware_version || "-" },
            { label: "IP", render: (device) => device.ip_address || "-" },
            { label: "Dernier signal", render: (device) => formatDateTime(device.last_seen) },
        ],
        supervision.devices || [],
        "Aucun ESP32 visible sur vos stations."
    );

    createDataTable(
        document.getElementById("tech-alerts-list"),
        [
            { label: "Date", render: (alert) => formatDateTime(alert.timestamp) },
            { label: "Type", render: (alert) => alert.type || "-" },
            {
                label: "Sévérité",
                render: (alert) => createStatusBadge(
                    alert.niveau_severite || "-",
                    ["critical", "critique"].includes(alert.niveau_severite) ? "danger" : "warning"
                ),
            },
            { label: "Emplacement", render: (alert) => `${alert.borne_nom || "-"} / ${alert.emplacement_numero ?? "-"}` },
            { label: "Message", render: (alert) => alert.message || "-" },
        ],
        supervision.alerts || [],
        "Aucune alerte récente sur vos stations."
    );

    createDataTable(
        document.getElementById("tech-commands-list"),
        [
            { label: "Date", render: (command) => formatDateTime(command.timestamp) },
            { label: "Emplacement", render: (command) => command.slot_label || command.slot_id || "-" },
            { label: "Action", render: (command) => command.action || "-" },
            { label: "Statut", render: (command) => command.status || "-" },
            { label: "Message", render: (command) => command.message || "-" },
        ],
        supervision.commands || [],
        "Aucune commande récente sur vos stations."
    );
}

function setRealtimeStatus(element, label, state = "") {
    if (!element) return;
    element.textContent = label;
    element.classList.toggle("connected", state === "connected");
    element.classList.toggle("fallback", state === "fallback");
}

function buildTechnicianSupervisionWebSocketUrl(token) {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}/ws/technician/supervision/?token=${encodeURIComponent(token)}`;
}

document.addEventListener("DOMContentLoaded", async () => {
    const AUTO_REFRESH_MS = 30000;
    const status = document.getElementById("tech-status");
    const realtimeStatus = document.getElementById("tech-realtime-status");
    const logoutBtn = document.getElementById("logout-tech");
    const list = document.getElementById("maintenances-list");
    let isLoading = false;
    let supervisionSocket = null;
    let supervisionReconnectTimer = null;
    let supervisionRealtimeStarted = false;
    let supervisionReconnectAttempts = 0;

    logoutBtn.addEventListener("click", () => window.AuthAPI.logout());

    const session = await window.AuthAPI.ensureSession();
    if (!session) {
        status.classList.add("error");
        status.textContent = "Session absente ou expirée. Redirection vers la connexion.";
        window.setTimeout(() => {
            window.location.href = "/login.html";
        }, 1200);
        return;
    }

    if (!session.user?.is_technician && !session.user?.is_staff) {
        status.classList.add("error");
        status.textContent = "Accès réservé aux techniciens.";
        window.setTimeout(() => {
            window.location.href = "/dashboard.html";
        }, 1200);
        return;
    }

    async function loadDashboard() {
        if (isLoading) return;
        isLoading = true;

        try {
            const [maintenances, supervision] = await Promise.all([
                window.AuthAPI.getTechnicianMaintenances(),
                window.AuthAPI.getTechnicianSupervision(),
            ]);
            renderMaintenances(list, maintenances.results || []);
            renderSupervision(supervision || {});
            status.classList.remove("error");
            status.textContent = "";
        } finally {
            isLoading = false;
        }
    }

    try {
        await loadDashboard();
        window.setInterval(async () => {
            try {
                await loadDashboard();
            } catch (_error) {
                status.classList.add("error");
                status.textContent = "Impossible de rafraîchir le tableau de bord technicien.";
            }
        }, AUTO_REFRESH_MS);
    } catch (error) {
        status.classList.add("error");
        status.textContent = error.message || "Impossible de charger le tableau de bord technicien.";
    }

    function scheduleSupervisionReconnect() {
        if (!supervisionRealtimeStarted) return;
        window.clearTimeout(supervisionReconnectTimer);
        const delay = Math.min(30000, 3000 * 2 ** Math.min(supervisionReconnectAttempts, 3));
        supervisionReconnectAttempts += 1;
        supervisionReconnectTimer = window.setTimeout(() => {
            connectSupervisionSocket();
        }, delay);
    }

    async function connectSupervisionSocket() {
        if (!("WebSocket" in window)) {
            setRealtimeStatus(realtimeStatus, "Polling de secours", "fallback");
            return;
        }
        if (
            supervisionSocket &&
            [WebSocket.CONNECTING, WebSocket.OPEN].includes(supervisionSocket.readyState)
        ) {
            return;
        }

        const token = window.AuthAPI.getAccessToken();
        if (!token) {
            setRealtimeStatus(realtimeStatus, "Polling de secours", "fallback");
            return;
        }

        setRealtimeStatus(realtimeStatus, "Connexion temps réel", "fallback");
        const socket = new WebSocket(buildTechnicianSupervisionWebSocketUrl(token));
        supervisionSocket = socket;

        socket.addEventListener("open", () => {
            supervisionReconnectAttempts = 0;
            setRealtimeStatus(realtimeStatus, "Temps réel actif", "connected");
        });

        socket.addEventListener("message", (event) => {
            let message = null;
            try {
                message = JSON.parse(event.data);
            } catch (_error) {
                return;
            }
            if (message?.type !== "supervision.snapshot" || !message.payload) return;
            renderSupervision(message.payload);
        });

        socket.addEventListener("close", async (event) => {
            if (supervisionSocket !== socket) return;
            supervisionSocket = null;
            setRealtimeStatus(realtimeStatus, "Polling de secours", "fallback");
            if (event.code === 4401) {
                try {
                    await window.AuthAPI.refreshAccessToken();
                } catch (_error) {
                    return;
                }
            }
            scheduleSupervisionReconnect();
        });

        socket.addEventListener("error", () => {
            setRealtimeStatus(realtimeStatus, "Polling de secours", "fallback");
        });
    }

    supervisionRealtimeStarted = true;
    connectSupervisionSocket();
    window.addEventListener("beforeunload", () => {
        supervisionRealtimeStarted = false;
        window.clearTimeout(supervisionReconnectTimer);
        if (supervisionSocket) {
            supervisionSocket.close();
        }
    });
});
