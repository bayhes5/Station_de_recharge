function formatDateTime(value) {
    if (!value) return "-";
    return new Date(value).toLocaleString("fr-FR");
}

function createActionLink(label, href) {
    const link = document.createElement("a");
    link.className = "table-action";
    link.href = href;
    link.textContent = label;
    return link;
}

function createActionButton(label, onClick, variant = "") {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `table-action${variant ? ` ${variant}` : ""}`;
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
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
        if (column.className) th.className = column.className;
        headRow.appendChild(th);
    });
    thead.appendChild(headRow);

    const tbody = document.createElement("tbody");
    rows.forEach((row) => {
        const tr = document.createElement("tr");
        columns.forEach((column) => {
            const td = document.createElement("td");
            if (column.className) td.className = column.className;
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

function parsePageNumber(url) {
    if (!url) return null;
    try {
        return Number(new URL(url).searchParams.get("page")) || null;
    } catch (_error) {
        return null;
    }
}

function normalizeSearchValue(value) {
    return String(value ?? "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .trim();
}

function collectSearchText(parts) {
    return parts
        .filter((part) => part !== null && part !== undefined && part !== "")
        .join(" ");
}

function createStatusBadge(label, variant = "") {
    const badge = document.createElement("span");
    badge.className = `badge status-badge${variant ? ` ${variant}` : ""}`;
    badge.textContent = label;
    return badge;
}

function isAnonymizedIdentity(value) {
    return /@anonymized\.invalid$/i.test(String(value || ""));
}

function formatUserDisplay(value) {
    if (!value || isAnonymizedIdentity(value)) {
        return "Compte supprimé";
    }
    return cleanDisplayText(value);
}

function createStackedCell(lines, className = "") {
    const cell = document.createElement("div");
    cell.className = `table-stacked-cell${className ? ` ${className}` : ""}`;
    lines.filter(Boolean).forEach((line, index) => {
        const element = document.createElement(index === 0 ? "strong" : "span");
        element.textContent = line;
        cell.appendChild(element);
    });
    return cell;
}

function formatReservationStatus(status) {
    const labels = {
        confirmee: "Confirmée",
        active: "Active",
        en_attente: "En attente",
        terminee: "Terminée",
        annulee: "Annulée",
    };
    return labels[status] || status || "-";
}

function formatAuthMode(mode) {
    const labels = {
        rfid: "Badge RFID",
        qr: "QR code",
        code: "Code SMS",
    };
    return labels[mode] || mode || "-";
}

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

function formatUserStatus(status) {
    const labels = {
        actif: "Actif",
        suspendu: "Suspendu",
        archive: "Archivé",
    };
    return labels[status] || cleanDisplayText(status);
}

function formatStationStatus(status) {
    const labels = {
        active: "Active",
        maintenance: "Maintenance",
        inactive: "Inactive",
    };
    return labels[status] || cleanDisplayText(status);
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

function formatFirmwareStatus(status) {
    const labels = {
        unknown: "Non renseigné",
        up_to_date: "À jour",
        update_required: "Mise à jour requise",
        update_scheduled: "Mise à jour planifiée",
        updating: "Mise à jour en cours",
        failed: "Échec de mise à jour",
    };
    return labels[status] || cleanDisplayText(status);
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

function alertSeverityVariant(severity) {
    const normalized = normalizeSearchValue(severity);
    if (["critical", "critique", "high", "haute", "elevee", "elevée"].includes(normalized)) {
        return "danger";
    }
    if (["medium", "moyenne", "warning", "avertissement", "moderee", "modérée"].includes(normalized)) {
        return "warning";
    }
    return "";
}

document.addEventListener("DOMContentLoaded", async () => {
    const AUTO_REFRESH_MS = 30000;
    const GRAFANA_DASHBOARD_UID = "station-overview";
    const GRAFANA_DASHBOARD_SLUG = "station-vue-globale-supervision";
    const GRAFANA_DASHBOARD_QUERY = "orgId=1&from=now-6h&to=now&refresh=10s";
    const GRAFANA_DASHBOARD_PATH = `/d/${GRAFANA_DASHBOARD_UID}/${GRAFANA_DASHBOARD_SLUG}?${GRAFANA_DASHBOARD_QUERY}`;
    const GRAFANA_DASHBOARD_SUBPATH = `/grafana${GRAFANA_DASHBOARD_PATH}`;
    const status = document.getElementById("admin-status");
    const logoutBtn = document.getElementById("logout-admin");
    const grafanaLink = document.getElementById("grafana-link");
    const realtimeStatus = document.getElementById("supervision-realtime-status");
    const exportJsonBtn = document.getElementById("admin-export-json");
    const exportCsvBtn = document.getElementById("admin-export-csv");
    const exportDatasetSelect = document.getElementById("admin-export-dataset");
    const exportStationSelect = document.getElementById("admin-export-station");
    const exportDateFromInput = document.getElementById("admin-export-date-from");
    const exportDateToInput = document.getElementById("admin-export-date-to");
    const exportLogStatusSelect = document.getElementById("admin-export-log-status");
    const exportQueryInput = document.getElementById("admin-export-query");
    const exportSummary = document.getElementById("admin-export-summary");
    const exportPreviewTable = document.getElementById("admin-export-preview-table");

    let users = [];
    let stations = [];
    let bornes = [];
    let emplacements = [];
    let technicians = [];
    let maintenances = [];
    let ongoingReservations = [];
    let upcomingReservations = [];
    let archivedReservations = [];
    let activeSessions = [];
    let archivedSessions = [];
    let supervision = {
        stats: {},
        devices: [],
        alerts: [],
        measurements: [],
        commands: [],
    };
    let currentAdminId = null;
    let currentTab = "overview";
    let isLoading = false;
    let isRefreshingLiveData = false;
    let isRefreshingSessionData = false;
    let exportPreviewTimer = null;
    let exportPreviewRequestId = 0;
    let supervisionSocket = null;
    let supervisionReconnectTimer = null;
    let supervisionRealtimeStarted = false;
    let supervisionReconnectAttempts = 0;
    const paginatedTables = ["users", "stations", "technicians", "maintenances"];
    const supervisionPaginationState = {
        devices: { page: 1, pageSize: 10 },
        commands: { page: 1, pageSize: 10 },
        alerts: { page: 1, pageSize: 10 },
        measurements: { page: 1, pageSize: 10 },
    };
    const paginationState = Object.fromEntries(
        paginatedTables.map((key) => [
            key,
            {
                page: 1,
                pageSize: 10,
                count: 0,
                next: null,
                previous: null,
            },
        ])
    );
    const searchState = {
        users: "",
        stations: "",
        technicians: "",
        maintenances: "",
        ongoingReservations: "",
        upcomingReservations: "",
        archivedReservations: "",
        activeSessions: "",
        archivedSessions: "",
    };

    const searchTextByTable = {
        users: (user) => collectSearchText([
            user.pseudo,
            user.email,
            user.nom,
            user.telephone,
        ]),
        stations: (station) => collectSearchText([
            station.nom,
            station.localisation_text,
            station.latitude,
            station.longitude,
            station.statut,
            ...bornes.filter((borne) => String(borne.station) === String(station.id_station)).map((borne) => `${borne.nom} ${borne.numero} ${borne.statut}`),
            ...emplacements.filter((emplacement) => String(emplacement.station) === String(station.id_station)).map((emplacement) => `${emplacement.borne_nom || ""} ${emplacement.numero} ${emplacement.statut}`),
        ]),
        technicians: (technician) => collectSearchText([
            technician.nom,
            technician.email,
            technician.telephone,
            technician.utilisateur_pseudo,
            ...(technician.assigned_stations || []).map((assignment) => `${assignment.station_nom} ${assignment.role}`),
        ]),
        maintenances: (maintenance) => collectSearchText([
            maintenance.station_nom,
            maintenance.technicien_nom,
            maintenance.type,
            maintenance.description,
            formatMaintenanceStatus(maintenance.status),
            formatDateTime(maintenance.date_planifiee),
            formatDateTime(maintenance.date_realisee),
        ]),
        ongoingReservations: reservationSearchText,
        upcomingReservations: reservationSearchText,
        archivedReservations: reservationSearchText,
        activeSessions: sessionSearchText,
        archivedSessions: sessionSearchText,
    };

    function reservationSearchText(reservation) {
        return collectSearchText([
            reservation.reference_code,
            reservation.utilisateur_pseudo,
            reservation.station_nom,
            reservation.borne_nom,
            reservation.emplacement_numero,
            reservation.emplacement,
            reservation.auth_mode,
            reservation.auth_display_value,
            reservation.auth_expiration,
            formatReservationStatus(reservation.statut),
            formatDateTime(reservation.date_debut),
            formatDateTime(reservation.date_fin),
        ]);
    }

    function sessionSearchText(session) {
        return collectSearchText([
            session.utilisateur_pseudo,
            session.reference_code,
            session.station,
            session.borne,
            session.emplacement,
            session.status === "active" ? "en cours active" : "archivee archivée",
            session.latest_telemetry?.courant,
            session.latest_telemetry?.tension,
            session.latest_telemetry?.puissance_w,
            session.latest_telemetry?.energie_kwh,
            formatDateTime(session.latest_telemetry?.timestamp),
            formatDateTime(session.start_time),
            formatDateTime(session.end_time),
        ]);
    }

    function formatTelemetryNumber(value, unit, digits = 2) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return "-";
        return `${numeric.toLocaleString("fr-FR", {
            minimumFractionDigits: 0,
            maximumFractionDigits: digits,
        })} ${unit}`.trim();
    }

    function renderSessionTelemetry(session) {
        const telemetry = session.latest_telemetry;
        if (!telemetry) {
            return createStackedCell(["Aucune mesure"], "muted-cell");
        }
        const current = formatTelemetryNumber(telemetry.courant, "A");
        const power = formatTelemetryNumber(telemetry.puissance_w, "W", 1);
        const energy = formatTelemetryNumber(telemetry.energie_kwh, "kWh", 4);
        return createStackedCell([
            `${current} · ${power}`,
            `Énergie ${energy}`,
            formatDateTime(telemetry.timestamp),
        ]);
    }

    function formatMeasurementValue(row) {
        if (row.display_value) return row.display_value;
        const value = Number(row.valeur);
        const formatted = Number.isFinite(value) ? value.toLocaleString("fr-FR", {
            maximumFractionDigits: 2,
        }) : row.valeur;
        return `${formatted} ${row.unite || ""}`.trim();
    }

    function formatCommandAck(device) {
        if (!device.last_command_action && !device.last_command_status && !device.last_command_message) {
            return "-";
        }
        const parts = [
            device.last_command_action,
            device.last_command_status,
            device.last_command_message,
            device.last_command_at ? formatDateTime(device.last_command_at) : "",
        ].filter(Boolean);
        return parts.join(" - ");
    }

    function buildGrafanaDashboardUrl(baseUrl) {
        const cleaned = String(baseUrl || "").trim().replace(/\/+$/, "");
        if (!cleaned) return GRAFANA_DASHBOARD_SUBPATH;
        if (cleaned.includes(`/d/${GRAFANA_DASHBOARD_UID}/`)) return cleaned;
        return `${cleaned}${GRAFANA_DASHBOARD_PATH}`;
    }

    function resolveGrafanaUrl() {
        const configured = window.__GRAFANA_URL__;
        if (configured) return buildGrafanaDashboardUrl(configured);

        if (window.location.port && window.location.port !== "80" && window.location.port !== "443") {
            return `${window.location.protocol}//${window.location.hostname}:3000${GRAFANA_DASHBOARD_SUBPATH}`;
        }

        return GRAFANA_DASHBOARD_SUBPATH;
    }

    function setRealtimeStatus(label, state = "") {
        if (!realtimeStatus) return;
        realtimeStatus.textContent = label;
        realtimeStatus.classList.toggle("connected", state === "connected");
        realtimeStatus.classList.toggle("fallback", state === "fallback");
    }

    function buildSupervisionWebSocketUrl(token) {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        return `${protocol}//${window.location.host}/ws/admin/supervision/?token=${encodeURIComponent(token)}`;
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
            setRealtimeStatus("Polling de secours", "fallback");
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
            setRealtimeStatus("Polling de secours", "fallback");
            return;
        }

        setRealtimeStatus("Connexion temps réel", "fallback");
        const socket = new WebSocket(buildSupervisionWebSocketUrl(token));
        supervisionSocket = socket;

        socket.addEventListener("open", () => {
            supervisionReconnectAttempts = 0;
            setRealtimeStatus("Temps réel actif", "connected");
        });

        socket.addEventListener("message", (event) => {
            let message = null;
            try {
                message = JSON.parse(event.data);
            } catch (_error) {
                return;
            }
            if (message?.type !== "supervision.snapshot" || !message.payload) return;
            supervision = message.payload;
            renderSupervision();
            if (
                message.summary?.session_telemetry_created ||
                ["mqtt-telemetry", "mqtt-status", "mqtt-ack"].includes(message.reason)
            ) {
                refreshSessionData();
            }
        });

        socket.addEventListener("close", async (event) => {
            if (supervisionSocket !== socket) return;
            supervisionSocket = null;
            setRealtimeStatus("Polling de secours", "fallback");
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
            setRealtimeStatus("Polling de secours", "fallback");
        });
    }

    function filterRows(tableKey, rows) {
        const query = normalizeSearchValue(searchState[tableKey]);
        if (!query) return rows;

        const terms = query.split(/\s+/).filter(Boolean);
        const getSearchText = searchTextByTable[tableKey] || ((row) => JSON.stringify(row));
        return rows.filter((row) => {
            const haystack = normalizeSearchValue(getSearchText(row));
            return terms.every((term) => haystack.includes(term));
        });
    }

    function emptyMessageFor(tableKey, defaultMessage) {
        const query = (searchState[tableKey] || "").trim();
        if (!query) return defaultMessage;
        return `Aucun résultat pour « ${query} ».`;
    }

    function pageParams(tableKey) {
        const state = paginationState[tableKey];
        return {
            page: state.page,
            page_size: state.pageSize,
        };
    }

    function updatePageState(tableKey, response) {
        const state = paginationState[tableKey];
        state.count = Number(response.count ?? response.results?.length ?? 0);
        state.next = response.next || null;
        state.previous = response.previous || null;
    }

    function renderPagination(containerId, tableKey) {
        const container = document.getElementById(containerId);
        const state = paginationState[tableKey];
        const totalPages = Math.max(1, Math.ceil(state.count / state.pageSize));
        const start = state.count === 0 ? 0 : (state.page - 1) * state.pageSize + 1;
        const end = Math.min(state.count, state.page * state.pageSize);

        const controls = document.createElement("div");
        controls.className = "pagination-controls";

        const summary = document.createElement("span");
        summary.className = "pagination-summary";
        summary.textContent = `${start}-${end} sur ${state.count}`;

        const previousButton = createActionButton("Précédent", async () => {
            if (state.page <= 1 || isLoading) return;
            state.page -= 1;
            await loadAll();
        });
        previousButton.disabled = state.page <= 1 || !state.previous;

        const nextButton = createActionButton("Suivant", async () => {
            if (state.page >= totalPages || isLoading) return;
            state.page = parsePageNumber(state.next) || state.page + 1;
            await loadAll();
        });
        nextButton.disabled = state.page >= totalPages || !state.next;

        const pageSizeLabel = document.createElement("label");
        pageSizeLabel.className = "pagination-size";
        const pageSizeText = document.createElement("span");
        pageSizeText.textContent = "Par page";
        const pageSizeSelect = document.createElement("select");
        [10, 25, 50, 100].forEach((value) => {
            const option = document.createElement("option");
            option.value = String(value);
            option.textContent = String(value);
            option.selected = value === state.pageSize;
            pageSizeSelect.appendChild(option);
        });
        pageSizeSelect.addEventListener("change", async () => {
            state.pageSize = Number(pageSizeSelect.value);
            state.page = 1;
            await loadAll();
        });

        pageSizeLabel.appendChild(pageSizeText);
        pageSizeLabel.appendChild(pageSizeSelect);
        controls.appendChild(summary);
        controls.appendChild(previousButton);
        controls.appendChild(nextButton);
        controls.appendChild(pageSizeLabel);
        container.appendChild(controls);
    }

    function paginateRows(rows, state) {
        const totalPages = Math.max(1, Math.ceil(rows.length / state.pageSize));
        if (state.page > totalPages) state.page = totalPages;
        const start = (state.page - 1) * state.pageSize;
        return rows.slice(start, start + state.pageSize);
    }

    function renderClientPagination(containerId, tableKey, rows, renderCallback) {
        const container = document.getElementById(containerId);
        const state = supervisionPaginationState[tableKey];
        const totalPages = Math.max(1, Math.ceil(rows.length / state.pageSize));
        const start = rows.length === 0 ? 0 : (state.page - 1) * state.pageSize + 1;
        const end = Math.min(rows.length, state.page * state.pageSize);

        const controls = document.createElement("div");
        controls.className = "pagination-controls";

        const summary = document.createElement("span");
        summary.className = "pagination-summary";
        summary.textContent = `${start}-${end} sur ${rows.length}`;

        const previousButton = createActionButton("Précédent", () => {
            if (state.page <= 1) return;
            state.page -= 1;
            renderCallback();
        });
        previousButton.disabled = state.page <= 1;

        const nextButton = createActionButton("Suivant", () => {
            if (state.page >= totalPages) return;
            state.page += 1;
            renderCallback();
        });
        nextButton.disabled = state.page >= totalPages;

        const pageSizeLabel = document.createElement("label");
        pageSizeLabel.className = "pagination-size";
        const pageSizeText = document.createElement("span");
        pageSizeText.textContent = "Par page";
        const pageSizeSelect = document.createElement("select");
        [10, 25, 50].forEach((value) => {
            const option = document.createElement("option");
            option.value = String(value);
            option.textContent = String(value);
            option.selected = value === state.pageSize;
            pageSizeSelect.appendChild(option);
        });
        pageSizeSelect.addEventListener("change", () => {
            state.pageSize = Number(pageSizeSelect.value);
            state.page = 1;
            renderCallback();
        });

        pageSizeLabel.appendChild(pageSizeText);
        pageSizeLabel.appendChild(pageSizeSelect);
        controls.appendChild(summary);
        controls.appendChild(previousButton);
        controls.appendChild(nextButton);
        controls.appendChild(pageSizeLabel);
        container.appendChild(controls);
    }

    function setAdminTab(name, pushHash = true) {
        currentTab = name;
        document.querySelectorAll("[data-admin-tab]").forEach((button) => {
            const active = button.dataset.adminTab === name;
            button.classList.toggle("active", active);
            button.setAttribute("aria-selected", String(active));
        });
        document.querySelectorAll("[data-admin-panel]").forEach((panel) => {
            panel.hidden = panel.dataset.adminPanel !== name;
        });
        if (pushHash && window.location.hash !== `#${name}`) {
            window.history.replaceState(null, "", `#${name}`);
        }
        if (name === "exports") {
            scheduleExportPreview(0);
        }
    }

    function setOperationsSubtab(name) {
        document.querySelectorAll("[data-operations-subtab]").forEach((button) => {
            const active = button.dataset.operationsSubtab === name;
            button.classList.toggle("active", active);
            button.setAttribute("aria-selected", String(active));
        });
        document.querySelectorAll("[data-operations-panel]").forEach((panel) => {
            panel.hidden = panel.dataset.operationsPanel !== name;
        });
    }

    function setStatus(message, isError = false) {
        status.classList.toggle("error", isError);
        status.classList.toggle("success", Boolean(message) && !isError);
        status.textContent = message;
    }

    function collectExportFilters() {
        return {
            dataset: exportDatasetSelect?.value || "operational",
            station_id: exportStationSelect?.value || "",
            date_from: exportDateFromInput?.value || "",
            date_to: exportDateToInput?.value || "",
            log_status: exportLogStatusSelect?.value || "",
            query: exportQueryInput?.value || "",
        };
    }

    function updateExportFilterAvailability() {
        const isSecurityLogExport = exportDatasetSelect?.value === "security_logs";
        if (exportStationSelect) {
            exportStationSelect.disabled = isSecurityLogExport;
            if (isSecurityLogExport) exportStationSelect.value = "";
        }
        [exportLogStatusSelect, exportQueryInput].forEach((field) => {
            if (!field) return;
            field.disabled = !isSecurityLogExport;
            if (!isSecurityLogExport) field.value = "";
        });
    }

    function exportSummaryText(payload) {
        const metadata = payload.metadata || {};
        const summary = payload.summary || {};
        const rowCount = payload.rows?.length ?? 0;
        if (metadata.dataset === "security_logs") {
            const total = summary.total_matches ?? rowCount;
            const limitText = summary.limited ? `, limit\u00e9 \u00e0 ${rowCount} lignes affich\u00e9es` : "";
            return `${metadata.label || "Journaux"} : ${total} entr\u00e9e(s) trouv\u00e9e(s)${limitText}.`;
        }
        return `${metadata.label || "Export"} : ${rowCount} emplacement(s), ${summary.sessions_in_period ?? 0} session(s), ${summary.reservations_in_period ?? 0} r\u00e9servation(s).`;
    }

    function renderExportPreview(payload) {
        if (!exportSummary || !exportPreviewTable) return;
        exportSummary.textContent = exportSummaryText(payload);

        const metadata = payload.metadata || {};
        const rows = payload.rows || [];
        const columns = (metadata.columns || []).map((key) => ({
            key,
            label: {
                date_action: "Date",
                utilisateur: "Utilisateur",
                action: "Action",
                statut: "Statut",
                ip: "Adresse IP",
                statut_emplacement: "\u00c9tat emplacement",
                serrure: "Serrure",
                statut_esp32: "Statut ESP32",
                firmware_attendu: "Firmware attendu",
                conformite_firmware: "Conformit\u00e9 firmware",
                derniere_telemetrie: "Derni\u00e8re t\u00e9l\u00e9m\u00e9trie",
                session_active: "Session active",
                etat_session: "\u00c9tat session",
                reservations_periode: "R\u00e9servations",
                sessions_periode: "Sessions",
                alertes_actives: "Alertes actives",
            }[key] || key.replaceAll("_", " "),
            render: (row) => {
                const value = row[key];
                if (key.startsWith("date") || key === "derniere_telemetrie") return formatDateTime(value);
                if (key === "utilisateur") return formatUserDisplay(value);
                if (key === "statut") return value === "success" ? "Succ\u00e8s" : value === "failure" ? "\u00c9chec" : cleanDisplayText(value);
                return cleanDisplayText(value);
            },
        }));
        createDataTable(
            exportPreviewTable,
            columns,
            rows,
            "Aucune donn\u00e9e ne correspond aux filtres."
        );
    }

    async function previewOperationalExport() {
        if (!exportPreviewTable) return;
        const requestId = ++exportPreviewRequestId;
        if (exportSummary) {
            exportSummary.textContent = "Chargement des résultats...";
        }
        try {
            const payload = await window.AuthAPI.getAdminOperationalExport(collectExportFilters());
            if (requestId !== exportPreviewRequestId) return;
            renderExportPreview(payload);
        } catch (error) {
            if (requestId !== exportPreviewRequestId) return;
            exportSummary.textContent = "";
            createDataTable(exportPreviewTable, [], [], "Aucune donn\u00e9e disponible pour ces filtres.");
            setStatus(error.message || "Impossible de charger les donn\u00e9es d'export.", true);
        }
    }

    function scheduleExportPreview(delay = 350) {
        if (!exportPreviewTable) return;
        window.clearTimeout(exportPreviewTimer);
        exportPreviewTimer = window.setTimeout(() => {
            previewOperationalExport();
        }, delay);
    }

    async function downloadOperationalExport(format) {
        try {
            const result = await window.AuthAPI.downloadAdminOperationalExport(format, collectExportFilters());
            const url = URL.createObjectURL(result.blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = result.filename;
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(url);
            setStatus(`Export ${format.toUpperCase()} généré.`);
        } catch (error) {
            setStatus(error.message || "Export impossible.", true);
        }
    }

    function populateExportStationFilter() {
        if (!exportStationSelect) return;
        const selected = exportStationSelect.value;
        exportStationSelect.replaceChildren(new Option("Toutes les stations", ""));
        stations
            .slice()
            .sort((a, b) => String(a.nom || "").localeCompare(String(b.nom || "")))
            .forEach((station) => {
                exportStationSelect.appendChild(new Option(station.nom, station.id_station));
            });
        exportStationSelect.value = stations.some((station) => station.id_station === selected) ? selected : "";
    }

    function renderOverviewStats(overview) {
        const stats = overview.stats || {};
        document.getElementById("stat-users").textContent = stats.users_total ?? "-";
        document.getElementById("stat-stations").textContent = stats.stations_total ?? "-";
        document.getElementById("stat-emplacements").textContent = stats.emplacements_total ?? "-";
        document.getElementById("stat-reservations-upcoming").textContent = stats.reservations_upcoming ?? "-";
        document.getElementById("stat-sessions-active").textContent = stats.sessions_active ?? "-";
        document.getElementById("stat-sessions-archived").textContent = stats.sessions_archived ?? "-";
    }

    function editHref(resource, id) {
        return `/admin-form.html?resource=${resource}&id=${id}`;
    }

    function renderActions({ resource, id, label, onDelete }) {
        const actions = document.createElement("div");
        actions.className = "table-actions";
        actions.appendChild(createActionLink("Modifier", editHref(resource, id)));
        actions.appendChild(createActionButton("Supprimer", onDelete, "danger-action"));
        actions.setAttribute("aria-label", `Actions ${label}`);
        return actions;
    }

    function canManageTemporaryAccess(reservation) {
        return ["qr", "code"].includes(reservation.auth_mode)
            && !["annulee", "terminee"].includes(reservation.statut)
            && new Date(reservation.date_fin) >= new Date();
    }

    function isArchivedReservation(reservation) {
        return reservation.statut === "annulee"
            || (reservation.date_fin && new Date(reservation.date_fin) < new Date());
    }

    function renderAccessSummary(reservation) {
        const summary = document.createElement("div");
        summary.className = "access-summary";

        const statusBadge = document.createElement("span");
        statusBadge.className = "badge";

        const detail = document.createElement("small");

        if (isArchivedReservation(reservation)) {
            statusBadge.textContent = "Archiv\u00e9";
            detail.textContent = "Acc\u00e8s non utilisable";
            summary.appendChild(statusBadge);
            summary.appendChild(detail);
            return summary;
        }

        if (!["qr", "code"].includes(reservation.auth_mode)) {
            statusBadge.textContent = "RFID";
            detail.textContent = "Badge utilisateur";
            summary.appendChild(statusBadge);
            summary.appendChild(detail);
            return summary;
        }

        if (reservation.auth_is_active === false) {
            statusBadge.textContent = "Révoqué";
            summary.appendChild(statusBadge);
            return summary;
        }

        if (reservation.auth_expiration && new Date(reservation.auth_expiration) < new Date()) {
            statusBadge.textContent = "Expiré";
            summary.appendChild(statusBadge);
            return summary;
        }

        statusBadge.textContent = "Actif";
        detail.textContent = reservation.auth_expiration
            ? `Jusqu'à ${formatDateTime(reservation.auth_expiration)}`
            : "Sans expiration";
        summary.appendChild(statusBadge);
        summary.appendChild(detail);
        return summary;
    }

    function renderReservationActions(reservation) {
        const actions = document.createElement("div");
        actions.className = "table-actions reservation-actions";
        const manageAccess = canManageTemporaryAccess(reservation);

        if (["qr", "code"].includes(reservation.auth_mode)) {
            const accessActions = document.createElement("div");
            accessActions.className = "reservation-action-group";

            const regenerateButton = createActionButton("Régénérer", () => regenerateReservationAccess(reservation));
            regenerateButton.disabled = !manageAccess;
            if (!manageAccess) regenerateButton.title = "Accès temporaire non régénérable.";
            accessActions.appendChild(regenerateButton);

            const revokeButton = createActionButton("Révoquer", () => revokeReservationAccess(reservation), "danger-action");
            revokeButton.disabled = !manageAccess || reservation.auth_is_active === false;
            if (revokeButton.disabled) revokeButton.title = "Aucun accès temporaire actif à révoquer.";
            accessActions.appendChild(revokeButton);

            actions.appendChild(accessActions);
        }

        const cancelActions = document.createElement("div");
        cancelActions.className = "reservation-action-group";
        const cancelButton = createActionButton("Annuler", () => deleteAndReload(
            `Annuler la réservation ${reservation.reference_code || ""} ?`,
            () => window.AuthAPI.cancelAdminReservation(reservation.id_reservation)
        ), "danger-action");
        cancelButton.disabled = !reservation.can_cancel;
        if (!reservation.can_cancel) {
            cancelButton.title = "Cette réservation ne peut plus être annulée.";
        }
        cancelActions.appendChild(cancelButton);
        actions.appendChild(cancelActions);

        return actions;
    }

    async function deleteAndReload(confirmMessage, deleteRequest) {
        const confirmed = await window.AuthAPI.confirmAction(confirmMessage, {
            title: "Confirmer la suppression",
            confirmLabel: "Supprimer",
            danger: true,
        });
        if (!confirmed) return;
        try {
            await deleteRequest();
            await loadAll();
            setStatus("Suppression effectu\u00e9e.");
        } catch (error) {
            setStatus(error.message || "Suppression impossible.", true);
        }
    }

    async function regenerateReservationAccess(reservation) {
        const confirmed = await window.AuthAPI.confirmAction(
            `Régénérer l'accès temporaire de la réservation ${reservation.reference_code || ""} ?`,
            {
                title: "Régénérer l'accès",
                confirmLabel: "Régénérer",
            }
        );
        if (!confirmed) return;

        try {
            await window.AuthAPI.regenerateAdminReservationAccess(reservation.id_reservation);
            await loadAll();
            setStatus(`Accès temporaire régénéré pour ${reservation.reference_code || "la réservation"}. L'utilisateur verra la nouvelle valeur automatiquement.`);
        } catch (error) {
            setStatus(error.message || "Régénération impossible.", true);
        }
    }

    async function revokeReservationAccess(reservation) {
        const confirmed = await window.AuthAPI.confirmAction(
            `Révoquer l'accès temporaire de la réservation ${reservation.reference_code || ""} ?`,
            {
                title: "Révoquer l'accès",
                confirmLabel: "Révoquer",
                danger: true,
            }
        );
        if (!confirmed) return;

        try {
            await window.AuthAPI.revokeAdminReservationAccess(reservation.id_reservation);
            await loadAll();
            setStatus(`Accès temporaire révoqué pour ${reservation.reference_code || "la réservation"}.`);
        } catch (error) {
            setStatus(error.message || "Révocation impossible.", true);
        }
    }

    function renderUsers() {
        createDataTable(
            document.getElementById("users-list"),
            [
                { label: "Pseudo", render: (user) => user.pseudo },
                { label: "E-mail", render: (user) => user.email },
                { label: "Nom", render: (user) => user.nom || "-" },
                { label: "T\u00e9l\u00e9phone", render: (user) => user.telephone || "-" },
                { label: "Statut", render: (user) => formatUserStatus(user.statut) },
                {
                    label: "R\u00f4les",
                    render: (user) => [
                        user.is_superuser ? "super-admin" : null,
                        user.is_staff ? "staff" : null,
                        user.is_technician ? "technicien" : null,
                    ].filter(Boolean).join(", ") || "utilisateur",
                },
                { label: "Cr\u00e9\u00e9 le", render: (user) => formatDateTime(user.date_joined) },
                {
                    label: "Actions",
                    className: "actions-column",
                    renderNode: (user) => renderActions({
                        resource: "user",
                        id: user.id_user,
                        label: user.pseudo,
                        onDelete: async () => {
                            if (String(user.id_user) === String(currentAdminId)) {
                                setStatus("Vous ne pouvez pas supprimer votre propre compte depuis cet \u00e9cran.", true);
                                return;
                            }
                            await deleteAndReload(
                                `Supprimer l'utilisateur ${user.pseudo} ?`,
                                () => window.AuthAPI.deleteAdminUser(user.id_user)
                            );
                        },
                    }),
                },
            ],
            filterRows("users", users),
            emptyMessageFor("users", "Aucun utilisateur.")
        );
        renderPagination("users-list", "users");
    }

    function renderStations() {
        const container = document.getElementById("stations-list");
        const rows = filterRows("stations", stations);

        createDataTable(
            container,
            [
                {
                    label: "Station",
                    renderNode: (station) => {
                        const wrapper = document.createElement("div");
                        wrapper.className = "station-name-cell";
                        const link = createActionLink(station.nom, `/admin-station.html?id=${station.id_station}`);
                        link.className = "table-action station-profile-link";
                        const hint = document.createElement("small");
                        hint.textContent = "Fiche station";
                        wrapper.appendChild(link);
                        wrapper.appendChild(hint);
                        return wrapper;
                    },
                },
                { label: "Localisation", render: (station) => station.localisation_text || "-" },
                { label: "Statut", render: (station) => formatStationStatus(station.statut) },
                {
                    label: "Bornes",
                    render: (station) => bornes.filter((borne) => String(borne.station) === String(station.id_station)).length,
                },
                {
                    label: "Emplacements",
                    render: (station) => emplacements.filter((emplacement) => String(emplacement.station) === String(station.id_station)).length,
                },
                {
                    label: "Actions",
                    className: "actions-column",
                    renderNode: (station) => {
                        const actions = document.createElement("div");
                        actions.className = "table-actions";
                        actions.appendChild(createActionLink("Ouvrir", `/admin-station.html?id=${station.id_station}`));
                        actions.appendChild(createActionLink("Modifier", editHref("station", station.id_station)));
                        actions.appendChild(createActionButton("Supprimer", () => deleteAndReload(
                            `Supprimer la station ${station.nom} ?`,
                            () => window.AuthAPI.deleteAdminStation(station.id_station)
                        ), "danger-action"));
                        return actions;
                    },
                },
            ],
            rows,
            emptyMessageFor("stations", "Aucune station.")
        );
        renderPagination("stations-list", "stations");
    }

    function renderTechnicians() {
        createDataTable(
            document.getElementById("technicians-list"),
            [
                { label: "Nom", render: (technician) => technician.nom },
                { label: "E-mail", render: (technician) => technician.email },
                { label: "Utilisateur li\u00e9", render: (technician) => formatUserDisplay(technician.utilisateur_pseudo) },
                { label: "T\u00e9l\u00e9phone", render: (technician) => technician.telephone || "-" },
                {
                    label: "Stations",
                    render: (technician) => (technician.assigned_stations || [])
                        .map((assignment) => assignment.station_nom)
                        .join(", ") || "-",
                },
                {
                    label: "Actions",
                    className: "actions-column",
                    renderNode: (technician) => renderActions({
                        resource: "technician",
                        id: technician.id_technicien,
                        label: technician.nom,
                        onDelete: () => deleteAndReload(
                            `Supprimer le technicien ${technician.nom} ?`,
                            () => window.AuthAPI.deleteAdminTechnician(technician.id_technicien)
                        ),
                    }),
                },
            ],
            filterRows("technicians", technicians),
            emptyMessageFor("technicians", "Aucun technicien.")
        );
        renderPagination("technicians-list", "technicians");
    }

    function renderMaintenances() {
        createDataTable(
            document.getElementById("maintenances-list"),
            [
                { label: "Station", render: (maintenance) => maintenance.station_nom },
                { label: "Technicien", render: (maintenance) => maintenance.technicien_nom || "-" },
                { label: "Type", render: (maintenance) => cleanDisplayText(maintenance.type) },
                { label: "Statut", render: (maintenance) => formatMaintenanceStatus(maintenance.status) },
                { label: "Date planifi\u00e9e", render: (maintenance) => formatDateTime(maintenance.date_planifiee) },
                { label: "Date r\u00e9alis\u00e9e", render: (maintenance) => formatDateTime(maintenance.date_realisee) },
                {
                    label: "Actions",
                    className: "actions-column",
                    renderNode: (maintenance) => renderActions({
                        resource: "maintenance",
                        id: maintenance.id_maintenance,
                        label: cleanDisplayText(maintenance.type),
                        onDelete: () => deleteAndReload(
                            `Supprimer la maintenance ${cleanDisplayText(maintenance.type)} ?`,
                            () => window.AuthAPI.deleteAdminMaintenance(maintenance.id_maintenance)
                        ),
                    }),
                },
            ],
            filterRows("maintenances", maintenances),
            emptyMessageFor("maintenances", "Aucune maintenance.")
        );
        renderPagination("maintenances-list", "maintenances");
    }

    function renderReservations(containerId, rows, emptyMessage, searchKey, { includeActions = true } = {}) {
        const columns = [
            {
                label: "Réservation",
                className: "reservation-summary-column",
                renderNode: (reservation) => createStackedCell([
                    reservation.reference_code || "-",
                    formatReservationStatus(reservation.statut),
                ]),
            },
            { label: "Utilisateur", render: (reservation) => formatUserDisplay(reservation.utilisateur_pseudo) },
            {
                label: "Lieu",
                className: "location-column",
                renderNode: (reservation) => createStackedCell([
                    reservation.station_nom || "-",
                    `${reservation.borne_nom || "Borne"} - emplacement ${reservation.emplacement_numero || reservation.emplacement || "-"}`,
                ]),
            },
            {
                label: "Créneau",
                className: "time-window-column",
                renderNode: (reservation) => createStackedCell([
                    formatDateTime(reservation.date_debut),
                    formatDateTime(reservation.date_fin),
                ]),
            },
            {
                label: "Accès",
                className: "access-column",
                renderNode: (reservation) => {
                    const wrapper = document.createElement("div");
                    wrapper.className = "reservation-access-cell";
                    const mode = document.createElement("strong");
                    mode.textContent = formatAuthMode(reservation.auth_mode);
                    wrapper.appendChild(mode);
                    wrapper.appendChild(renderAccessSummary(reservation));
                    return wrapper;
                },
            },
        ];

        if (includeActions) {
            columns.push({
                label: "Actions",
                className: "actions-column reservation-actions-column",
                renderNode: renderReservationActions,
            });
        }

        createDataTable(
            document.getElementById(containerId),
            columns,
            filterRows(searchKey, rows),
            emptyMessageFor(searchKey, emptyMessage)
        );
    }

    function renderSessions(containerId, rows, emptyMessage, searchKey) {
        createDataTable(
            document.getElementById(containerId),
            [
                { label: "Utilisateur", render: (session) => formatUserDisplay(session.utilisateur_pseudo) },
                { label: "Code réservation", render: (session) => session.reference_code || "-" },
                { label: "Station", render: (session) => session.station || "-" },
                { label: "Borne", render: (session) => session.borne || "-" },
                { label: "Emplacement", render: (session) => session.emplacement || "-" },
                { label: "Accès validé", render: (session) => formatDateTime(session.start_time) },
                { label: "Dernière télémétrie", renderNode: renderSessionTelemetry },
                { label: "Fin", render: (session) => formatDateTime(session.end_time) },
                { label: "Statut", render: (session) => session.status === "active" ? "En cours" : "Archivée" },
            ],
            filterRows(searchKey, rows),
            emptyMessageFor(searchKey, emptyMessage)
        );
    }

    function renderSupervision() {
        const stats = supervision.stats || {};
        document.getElementById("stat-devices-online").textContent = stats.devices_online ?? "-";
        document.getElementById("stat-devices-offline").textContent = stats.devices_offline ?? "-";
        document.getElementById("stat-devices-firmware").textContent = stats.devices_firmware_update_required ?? "-";
        document.getElementById("stat-alerts-active").textContent = stats.active_alerts ?? "-";
        document.getElementById("stat-alerts-critical").textContent = stats.critical_alerts ?? "-";
        document.getElementById("stat-telemetry-24h").textContent = stats.telemetry_samples_24h ?? "-";

        createDataTable(
            document.getElementById("admin-devices-list"),
            [
                { label: "Emplacement", render: (device) => device.slot_label || device.slot_id || "-" },
                { label: "Connexion", renderNode: (device) => createStatusBadge(device.online ? "En ligne" : "Hors ligne", device.online ? "success" : "danger") },
                { label: "Dernier état reçu", render: (device) => cleanDisplayText(device.status_display || device.status) },
                { label: "Dernière confirmation", render: formatCommandAck },
                { label: "Station", render: (device) => device.station_nom || "-" },
                { label: "Borne", render: (device) => device.borne_nom || "-" },
                { label: "Emplacement", render: (device) => device.emplacement_numero ?? "-" },
                { label: "Serrure", render: (device) => formatLockState(device.lock_state) },
                { label: "Version", render: (device) => device.firmware_version || "-" },
                { label: "Version attendue", render: (device) => device.effective_expected_firmware_version || device.expected_firmware_version || "-" },
                { label: "Mise à jour", render: (device) => formatFirmwareStatus(device.firmware_update_status) },
                { label: "IP", render: (device) => device.ip_address || "-" },
                { label: "Adresse matérielle", render: (device) => device.hardware_mac || "-" },
                { label: "Dernier signal", render: (device) => formatDateTime(device.last_seen) },
            ],
            paginateRows(supervision.devices || [], supervisionPaginationState.devices),
            "Aucun contrôleur enregistré."
        );

        renderClientPagination("admin-devices-list", "devices", supervision.devices || [], renderSupervision);

        createDataTable(
            document.getElementById("admin-commands-list"),
            [
                { label: "Date", render: (command) => formatDateTime(command.timestamp) },
                { label: "Emplacement", render: (command) => command.slot_label || command.slot_id || "-" },
                { label: "Action", render: (command) => command.action || "-" },
                { label: "Statut", renderNode: (command) => createStatusBadge(command.status || "-", ["accepted", "stopped", "locked", "unlocked"].includes(command.status) ? "success" : "warning") },
                { label: "Message", render: (command) => command.message || "-" },
                { label: "Source", render: (command) => command.source || "-" },
                { label: "Session", render: (command) => command.session_id || "-" },
            ],
            paginateRows(supervision.commands || [], supervisionPaginationState.commands),
            "Aucune commande reçue."
        );

        renderClientPagination("admin-commands-list", "commands", supervision.commands || [], renderSupervision);

        createDataTable(
            document.getElementById("admin-alerts-list"),
            [
                { label: "Date", render: (alert) => formatDateTime(alert.timestamp) },
                { label: "Type", render: (alert) => alert.type || "-" },
                { label: "Sévérité", renderNode: (alert) => createStatusBadge(cleanDisplayText(alert.niveau_severite), alertSeverityVariant(alert.niveau_severite)) },
                { label: "Statut", render: (alert) => formatAlertStatus(alert.status) },
                { label: "Station", render: (alert) => alert.station_nom || "-" },
                { label: "Borne", render: (alert) => alert.borne_nom || "-" },
                { label: "Emplacement", render: (alert) => alert.emplacement_numero ?? "-" },
                { label: "Message", render: (alert) => alert.message || "-" },
            ],
            paginateRows(supervision.alerts || [], supervisionPaginationState.alerts),
            "Aucune alerte récente."
        );

        renderClientPagination("admin-alerts-list", "alerts", supervision.alerts || [], renderSupervision);

        createDataTable(
            document.getElementById("admin-measurements-list"),
            [
                { label: "Date", render: (row) => formatDateTime(row.timestamp) },
                { label: "Emplacement", render: (row) => row.slot_label || row.slot_id || "-" },
                { label: "Capteur", render: (row) => row.type || "-" },
                { label: "Valeur", render: formatMeasurementValue },
                { label: "Station", render: (row) => row.station_nom || "-" },
                { label: "Borne", render: (row) => row.borne_nom || "-" },
                { label: "Emplacement", render: (row) => row.emplacement_numero ?? "-" },
            ],
            paginateRows(supervision.measurements || [], supervisionPaginationState.measurements),
            "Aucune mesure capteur reçue."
        );
        renderClientPagination("admin-measurements-list", "measurements", supervision.measurements || [], renderSupervision);
    }

    function renderAllTables() {
        renderSupervision();
        renderUsers();
        renderStations();
        renderTechnicians();
        renderMaintenances();
        renderReservations("admin-ongoing-reservations", ongoingReservations, "Aucune réservation en cours.", "ongoingReservations");
        renderReservations("admin-upcoming-reservations", upcomingReservations, "Aucune réservation à venir.", "upcomingReservations");
        renderReservations("admin-archived-reservations", archivedReservations, "Aucune réservation archivée.", "archivedReservations", { includeActions: false });
        renderSessions("admin-active-sessions", activeSessions, "Aucune session en cours.", "activeSessions");
        renderSessions("admin-archived-sessions", archivedSessions, "Aucune session archivée.", "archivedSessions");
    }

    async function loadAll() {
        if (isLoading) return;
        isLoading = true;

        try {
            const [
                overview,
                adminSupervision,
                adminUsers,
                adminStations,
                adminBornes,
                adminEmplacements,
                adminTechnicians,
                adminMaintenances,
            ] = await Promise.all([
                window.AuthAPI.getAdminOverview(),
                window.AuthAPI.getAdminSupervision(),
                window.AuthAPI.getAdminUsers(pageParams("users")),
                window.AuthAPI.getAdminStations(pageParams("stations")),
                window.AuthAPI.getAdminBornes(),
                window.AuthAPI.getAdminEmplacements(),
                window.AuthAPI.getAdminTechnicians(pageParams("technicians")),
                window.AuthAPI.getAdminMaintenances(pageParams("maintenances")),
            ]);

            let adminReservations = { ongoing: [], future: [], upcoming: [], archived: [] };
            let adminSessions = { active: [], archived: [] };
            let optionalDataFailed = false;

            try {
                [adminReservations, adminSessions] = await Promise.all([
                    window.AuthAPI.getAdminReservations(),
                    window.AuthAPI.getAdminSessions(),
                ]);
            } catch (_error) {
                optionalDataFailed = true;
            }

            renderOverviewStats(overview);

            users = adminUsers.results || [];
            stations = adminStations.results || [];
            bornes = adminBornes.results || [];
            emplacements = adminEmplacements.results || [];
            technicians = adminTechnicians.results || [];
            maintenances = adminMaintenances.results || [];
            supervision = adminSupervision || supervision;
            updatePageState("users", adminUsers);
            updatePageState("stations", adminStations);
            updatePageState("technicians", adminTechnicians);
            updatePageState("maintenances", adminMaintenances);
            ongoingReservations = adminReservations.ongoing || [];
            upcomingReservations = adminReservations.future || adminReservations.upcoming || [];
            archivedReservations = adminReservations.archived || [];
            activeSessions = adminSessions.active || [];
            archivedSessions = adminSessions.archived || [];

            populateExportStationFilter();
            updateExportFilterAvailability();
            renderAllTables();
            scheduleExportPreview(0);

            setStatus(
                optionalDataFailed
                    ? "Administration chargée. Redémarrez le backend pour activer les vues réservations/sessions."
                    : "",
                optionalDataFailed
            );
        } finally {
            isLoading = false;
        }
    }

    async function refreshLiveData() {
        if (isLoading || isRefreshingLiveData) return;
        isRefreshingLiveData = true;

        try {
            const [overview, adminSupervision] = await Promise.all([
                window.AuthAPI.getAdminOverview(),
                window.AuthAPI.getAdminSupervision(),
            ]);

            renderOverviewStats(overview);
            supervision = adminSupervision || supervision;
            renderSupervision();
        } finally {
            isRefreshingLiveData = false;
        }
    }

    async function refreshSessionData() {
        if (isLoading || isRefreshingSessionData) return;
        isRefreshingSessionData = true;

        try {
            const adminSessions = await window.AuthAPI.getAdminSessions();
            activeSessions = adminSessions.active || [];
            archivedSessions = adminSessions.archived || [];
            renderSessions("admin-active-sessions", activeSessions, "Aucune session en cours.", "activeSessions");
            renderSessions("admin-archived-sessions", archivedSessions, "Aucune session archivée.", "archivedSessions");
        } finally {
            isRefreshingSessionData = false;
        }
    }

    document.querySelectorAll("[data-admin-search]").forEach((input) => {
        input.addEventListener("input", () => {
            searchState[input.dataset.adminSearch] = input.value;
            renderAllTables();
        });
    });

    document.querySelectorAll("[data-admin-tab]").forEach((button) => {
        button.addEventListener("click", () => setAdminTab(button.dataset.adminTab));
    });

    document.querySelectorAll("[data-operations-subtab]").forEach((button) => {
        button.addEventListener("click", () => setOperationsSubtab(button.dataset.operationsSubtab));
    });

    document.querySelectorAll("[data-admin-jump]").forEach((button) => {
        button.addEventListener("click", () => setAdminTab(button.dataset.adminJump));
    });

    logoutBtn.addEventListener("click", () => window.AuthAPI.logout());
    exportDatasetSelect?.addEventListener("change", () => {
        updateExportFilterAvailability();
        scheduleExportPreview(0);
    });
    [
        exportStationSelect,
        exportDateFromInput,
        exportDateToInput,
        exportLogStatusSelect,
    ].forEach((field) => {
        field?.addEventListener("change", () => scheduleExportPreview(0));
    });
    exportQueryInput?.addEventListener("input", () => scheduleExportPreview());
    exportJsonBtn?.addEventListener("click", () => downloadOperationalExport("json"));
    exportCsvBtn?.addEventListener("click", () => downloadOperationalExport("csv"));
    if (grafanaLink) {
        grafanaLink.href = resolveGrafanaUrl();
    }
    window.addEventListener("beforeunload", () => {
        supervisionRealtimeStarted = false;
        window.clearTimeout(supervisionReconnectTimer);
        if (supervisionSocket) {
            supervisionSocket.close();
        }
    });

    const session = await window.AuthAPI.ensureSession();
    if (!session) {
        setStatus("Session absente ou expir\u00e9e. Redirection vers la connexion.", true);
        window.setTimeout(() => {
            window.location.href = "/login.html";
        }, 1200);
        return;
    }

    try {
        const dashboard = await window.AuthAPI.getDashboard();
        currentAdminId = dashboard.user?.id || dashboard.user?.id_user || null;
        if (!dashboard.user?.is_staff) {
            setStatus("Acc\u00e8s refus\u00e9. Redirection vers le tableau de bord utilisateur.", true);
            window.setTimeout(() => {
                window.location.href = "/dashboard.html";
            }, 1200);
            return;
        }

        const initialTab = (window.location.hash || "#overview").replace("#", "");
        const allowedTabs = ["overview", "supervision", "users", "infrastructure", "reservations", "sessions", "operations", "exports"];
        const selectedTab = allowedTabs.includes(initialTab) ? initialTab : "overview";
        window.AppNavigation.render(dashboard, {
            active: selectedTab === "overview" ? "admin" : selectedTab,
            preferredRole: "admin",
        });

        await loadAll();
        supervisionRealtimeStarted = true;
        connectSupervisionSocket();
        setAdminTab(selectedTab, false);

        window.setInterval(async () => {
            try {
                await refreshLiveData();
            } catch (_error) {
                if (currentTab === "overview" || currentTab === "supervision") {
                    setStatus("Impossible de rafra\u00eechir les donn\u00e9es de supervision.", true);
                }
            }
        }, AUTO_REFRESH_MS);
    } catch (_error) {
        setStatus("Impossible de charger l'administration.", true);
        window.AuthAPI.clearTokens();
        window.setTimeout(() => {
            window.location.href = "/login.html";
        }, 1200);
    }
});
