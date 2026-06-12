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

const CLOSED_ALERT_STATUSES = new Set(["resolue", "resolved", "closed", "fermee"]);

function cleanDisplayText(value) {
    if (value === null || value === undefined || value === "") return "-";
    return String(value)
        .replaceAll("\u00c3\u00a9", "é")
        .replaceAll("\u00c3\u00a8", "è")
        .replaceAll("\u00c3\u00aa", "ê")
        .replaceAll("\u00c3\u00b4", "ô")
        .replaceAll("\u00c3\u00a2", "â")
        .replaceAll("\u00c3\u00a0", "à")
        .replaceAll("\u00c3\u00a7", "ç")
        .replaceAll("\u00c3\u2030", "É")
        .replaceAll("\u00e2\u20ac\u2122", "’")
        .replaceAll("\u00e2\u20ac\u201c", "–");
}

function formatMaintenanceStatus(status) {
    const labels = {
        planifiee: "Planifiée",
        en_cours: "En cours",
        realisee: "Réalisée",
        annulee: "Annulée",
    };
    return labels[status] || cleanDisplayText(status);
}

function formatLockState(lockState) {
    const labels = {
        verrouille: "Verrouillée",
        deverrouille: "Déverrouillée",
        bloque: "Bloquée",
    };
    return labels[lockState] || cleanDisplayText(lockState);
}

function formatAlertStatus(status) {
    const labels = {
        nouvelle: "Nouvelle",
        active: "Active",
        prise_en_charge: "Prise en charge",
        resolue: "Résolue",
        closed: "Fermée",
        fermee: "Fermée",
    };
    return labels[status] || cleanDisplayText(status);
}

function alertStatusVariant(status) {
    if (CLOSED_ALERT_STATUSES.has(status)) return "success";
    if (status === "prise_en_charge") return "warning";
    return "danger";
}

function promptResolutionNote() {
    return new Promise((resolve) => {
        const previousFocus = document.activeElement;
        const backdrop = document.createElement("div");
        backdrop.className = "modal-backdrop";

        const dialog = document.createElement("section");
        dialog.className = "modal-dialog confirm-dialog";
        dialog.setAttribute("role", "dialog");
        dialog.setAttribute("aria-modal", "true");
        dialog.setAttribute("aria-labelledby", "resolution-dialog-title");

        const heading = document.createElement("div");
        heading.className = "modal-heading";
        const title = document.createElement("h2");
        title.id = "resolution-dialog-title";
        title.textContent = "Résoudre l'alerte";
        heading.appendChild(title);

        const field = document.createElement("label");
        field.className = "field admin-field-wide";
        const label = document.createElement("span");
        label.textContent = "Note d'intervention";
        const textarea = document.createElement("textarea");
        textarea.rows = 4;
        textarea.placeholder = "Exemple : boîtier contrôlé, température revenue à la normale.";
        field.append(label, textarea);

        const actions = document.createElement("div");
        actions.className = "cta-row confirm-actions";
        const cancelButton = document.createElement("button");
        cancelButton.type = "button";
        cancelButton.className = "btn btn-secondary";
        cancelButton.textContent = "Annuler";
        const confirmButton = document.createElement("button");
        confirmButton.type = "button";
        confirmButton.className = "btn btn-primary";
        confirmButton.textContent = "Résoudre";
        actions.append(cancelButton, confirmButton);

        dialog.append(heading, field, actions);
        backdrop.appendChild(dialog);
        document.body.appendChild(backdrop);

        function close(value) {
            backdrop.remove();
            document.removeEventListener("keydown", onKeyDown);
            if (previousFocus?.focus) previousFocus.focus();
            resolve(value);
        }

        function onKeyDown(event) {
            if (event.key === "Escape") close(null);
        }

        cancelButton.addEventListener("click", () => close(null));
        confirmButton.addEventListener("click", () => close(textarea.value.trim()));
        backdrop.addEventListener("click", (event) => {
            if (event.target === backdrop) close(null);
        });
        document.addEventListener("keydown", onKeyDown);
        textarea.focus();
    });
}

function createDataTable(container, columns, rows, emptyMessage) {
    container.replaceChildren();

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
                if (column.renderNode) {
                    td.appendChild(column.renderNode(row));
                } else {
                    const value = column.render ? column.render(row) : row[column.key];
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

function normalizeValue(value) {
    if (value === null || value === undefined) return "";
    return String(value).trim();
}

function stationIdFromRow(row = {}) {
    return normalizeValue(row.station_id || row.station || row.id_station);
}

function stationLabelFromRow(row = {}) {
    return normalizeValue(row.station_nom || row.station_name || row.station_label || row.station);
}

function collectStations(supervision = {}, maintenances = []) {
    const stations = new Map();

    function add(row) {
        const stationId = stationIdFromRow(row);
        const stationLabel = stationLabelFromRow(row);
        const key = stationId || stationLabel;
        if (!key || key === "-") return;
        stations.set(key, {
            id: key,
            label: stationLabel || key,
        });
    }

    [
        supervision.devices || [],
        supervision.alerts || [],
        supervision.measurements || [],
        supervision.commands || [],
        maintenances || [],
    ].forEach((rows) => rows.forEach(add));

    return [...stations.values()].sort((left, right) => left.label.localeCompare(right.label, "fr"));
}

function populateStationFilter(select, stations) {
    if (!select) return;
    const previousValue = select.value;
    select.replaceChildren();

    const allOption = document.createElement("option");
    allOption.value = "";
    allOption.textContent = "Toutes mes stations";
    select.appendChild(allOption);

    stations.forEach((station) => {
        const option = document.createElement("option");
        option.value = station.id;
        option.textContent = station.label;
        select.appendChild(option);
    });

    select.value = stations.some((station) => station.id === previousValue) ? previousValue : "";
}

function matchesSelectedStation(row, stationId) {
    if (!stationId) return true;
    return stationIdFromRow(row) === stationId || stationLabelFromRow(row) === stationId;
}

function filterByStation(rows, stationId) {
    return (rows || []).filter((row) => matchesSelectedStation(row, stationId));
}

function computeVisibleStats(supervision, stationId) {
    const backendStats = supervision.stats || {};
    if (!stationId) return backendStats;

    const devices = supervision.devices || [];
    const alerts = supervision.alerts || [];
    const measurements = supervision.measurements || [];
    const activeAlerts = alerts.filter((alert) => !CLOSED_ALERT_STATUSES.has(alert.status));

    return {
        ...backendStats,
        devices_total: devices.length,
        devices_online: devices.filter((device) => device.online).length,
        devices_offline: devices.filter((device) => !device.online).length,
        active_alerts: activeAlerts.length,
        critical_alerts: activeAlerts.filter((alert) => ["critical", "critique"].includes(alert.niveau_severite)).length,
        telemetry_samples_24h: measurements.length,
    };
}

function filterSupervision(supervision = {}, stationId = "") {
    const filtered = {
        ...supervision,
        devices: filterByStation(supervision.devices, stationId),
        alerts: filterByStation(supervision.alerts, stationId),
        measurements: filterByStation(supervision.measurements, stationId),
        commands: filterByStation(supervision.commands, stationId),
    };
    filtered.stats = computeVisibleStats(filtered, stationId);
    return filtered;
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
        details.textContent = `${formatMaintenanceStatus(maintenance.status)} | ${formatDateTime(maintenance.date_planifiee)}`;

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
                renderNode: (device) => createStatusBadge(
                    device.online ? "En ligne" : "Hors ligne",
                    device.online ? "success" : "danger"
                ),
            },
            { label: "Dernier état", render: (device) => cleanDisplayText(device.status_display || device.status) },
            { label: "Serrure", render: (device) => formatLockState(device.lock_state) },
            { label: "Version", render: (device) => device.firmware_version || "-" },
            { label: "IP", render: (device) => device.ip_address || "-" },
            { label: "Dernier signal", render: (device) => formatDateTime(device.last_seen) },
        ],
        supervision.devices || [],
        "Aucun contrôleur visible sur vos stations."
    );

    createDataTable(
        document.getElementById("tech-alerts-list"),
        [
            { label: "Date", render: (alert) => formatDateTime(alert.timestamp) },
            { label: "Type", render: (alert) => alert.type || "-" },
            {
                label: "Sévérité",
                renderNode: (alert) => createStatusBadge(
                    alert.niveau_severite || "-",
                    ["critical", "critique"].includes(alert.niveau_severite) ? "danger" : "warning"
                ),
            },
            {
                label: "Statut",
                renderNode: (alert) => createStatusBadge(
                    cleanDisplayText(alert.status_display || formatAlertStatus(alert.status)),
                    alertStatusVariant(alert.status)
                ),
            },
            { label: "Emplacement", render: (alert) => `${alert.borne_nom || "-"} / ${alert.emplacement_numero ?? "-"}` },
            { label: "Message", render: (alert) => alert.message || "-" },
            {
                label: "Intervention",
                render: (alert) => alert.acknowledged_by_nom || alert.resolved_by_nom || "-",
            },
            {
                label: "Actions",
                renderNode: (alert) => {
                    const actions = document.createElement("div");
                    actions.className = "table-actions";
                    if (CLOSED_ALERT_STATUSES.has(alert.status)) {
                        actions.textContent = alert.resolution_note || "-";
                        return actions;
                    }

                    if (alert.status !== "prise_en_charge") {
                        const acknowledgeButton = document.createElement("button");
                        acknowledgeButton.type = "button";
                        acknowledgeButton.className = "table-action";
                        acknowledgeButton.textContent = "Prendre en charge";
                        acknowledgeButton.addEventListener("click", () => {
                            window.dispatchEvent(new CustomEvent("technician-alert-action", {
                                detail: { action: "acknowledge", alertId: alert.id_alerte },
                            }));
                        });
                        actions.appendChild(acknowledgeButton);
                    }

                    const resolveButton = document.createElement("button");
                    resolveButton.type = "button";
                    resolveButton.className = "table-action";
                    resolveButton.textContent = "Résoudre";
                    resolveButton.addEventListener("click", () => {
                        window.dispatchEvent(new CustomEvent("technician-alert-action", {
                            detail: { action: "resolve", alertId: alert.id_alerte },
                        }));
                    });
                    actions.appendChild(resolveButton);
                    return actions;
                },
            },
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
    const stationFilter = document.getElementById("tech-station-filter");
    let isLoading = false;
    let supervisionSocket = null;
    let supervisionReconnectTimer = null;
    let supervisionRealtimeStarted = false;
    let supervisionReconnectAttempts = 0;
    let currentMaintenances = [];
    let currentSupervision = {};

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

    window.AppNavigation.render(session, { active: "technician", preferredRole: "technician" });

    function renderCurrentDashboard() {
        const stationId = stationFilter?.value || "";
        renderMaintenances(list, filterByStation(currentMaintenances, stationId));
        renderSupervision(filterSupervision(currentSupervision, stationId));
    }

    function syncStationFilter() {
        populateStationFilter(stationFilter, collectStations(currentSupervision, currentMaintenances));
    }

    stationFilter?.addEventListener("change", renderCurrentDashboard);

    async function loadDashboard() {
        if (isLoading) return;
        isLoading = true;

        try {
            const [maintenances, supervision] = await Promise.all([
                window.AuthAPI.getTechnicianMaintenances(),
                window.AuthAPI.getTechnicianSupervision(),
            ]);
            currentMaintenances = maintenances.results || [];
            currentSupervision = supervision || {};
            syncStationFilter();
            renderCurrentDashboard();
            status.classList.remove("error");
            status.textContent = "";
        } finally {
            isLoading = false;
        }
    }

    window.addEventListener("technician-alert-action", async (event) => {
        const { action, alertId } = event.detail || {};
        if (!alertId || isLoading) return;

        try {
            if (action === "acknowledge") {
                const confirmed = await window.AuthAPI.confirmAction(
                    "Prendre en charge cette alerte ?",
                    { title: "Alerte", confirmLabel: "Prendre en charge" }
                );
                if (!confirmed) return;
                await window.AuthAPI.acknowledgeTechnicianAlert(alertId);
            } else if (action === "resolve") {
                const note = await promptResolutionNote();
                if (note === null) return;
                await window.AuthAPI.resolveTechnicianAlert(alertId, note);
            }
            await loadDashboard();
        } catch (error) {
            status.classList.add("error");
            status.textContent = error.message || "Action impossible sur cette alerte.";
        }
    });

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
            currentSupervision = message.payload;
            syncStationFilter();
            renderCurrentDashboard();
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
