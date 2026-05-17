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

document.addEventListener("DOMContentLoaded", async () => {
    const AUTO_REFRESH_MS = 30000;
    const GRAFANA_DASHBOARD_UID = "station-supervision";
    const GRAFANA_DASHBOARD_SLUG = "station-supervision-technique";
    const GRAFANA_DASHBOARD_QUERY = "orgId=1&from=now-6h&to=now&refresh=5s";
    const GRAFANA_DASHBOARD_PATH = `/d/${GRAFANA_DASHBOARD_UID}/${GRAFANA_DASHBOARD_SLUG}?${GRAFANA_DASHBOARD_QUERY}`;
    const GRAFANA_DASHBOARD_SUBPATH = `/grafana${GRAFANA_DASHBOARD_PATH}`;
    const status = document.getElementById("admin-status");
    const logoutBtn = document.getElementById("logout-admin");
    const grafanaLink = document.getElementById("grafana-link");
    const realtimeStatus = document.getElementById("supervision-realtime-status");

    let users = [];
    let stations = [];
    let bornes = [];
    let emplacements = [];
    let technicians = [];
    let maintenances = [];
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
    let supervisionSocket = null;
    let supervisionReconnectTimer = null;
    let supervisionRealtimeStarted = false;
    let supervisionReconnectAttempts = 0;
    const expandedStations = new Set();
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
        ]),
        maintenances: (maintenance) => collectSearchText([
            maintenance.station_nom,
            maintenance.technicien_nom,
            maintenance.type,
            maintenance.description,
            maintenance.status,
            formatDateTime(maintenance.date_planifiee),
            formatDateTime(maintenance.date_realisee),
        ]),
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
            reservation.statut,
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
            formatDateTime(session.start_time),
            formatDateTime(session.end_time),
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
    }

    function setStatus(message, isError = false) {
        status.classList.toggle("error", isError);
        status.classList.toggle("success", Boolean(message) && !isError);
        status.textContent = message;
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

    function renderAccessSummary(reservation) {
        const summary = document.createElement("div");
        summary.className = "access-summary";

        const statusBadge = document.createElement("span");
        statusBadge.className = "badge";

        const detail = document.createElement("small");

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
                { label: "Statut", render: (user) => user.statut || "-" },
                {
                    label: "R\u00f4les",
                    render: (user) => [
                        user.is_superuser ? "super-admin" : null,
                        user.is_staff ? "staff" : null,
                        user.is_technician ? "technicien" : null,
                    ].filter(Boolean).join(", ") || "utilisateur",
                },
                { label: "Actif", render: (user) => user.is_active ? "Oui" : "Non" },
                { label: "Cr\u00e9\u00e9 le", render: (user) => formatDateTime(user.date_joined) },
                {
                    label: "Actions",
                    className: "actions-column",
                    render: (user) => renderActions({
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
        container.innerHTML = "";

        if (!rows.length) {
            const empty = document.createElement("div");
            empty.className = "empty-state";
            empty.textContent = emptyMessageFor("stations", "Aucune station.");
            container.appendChild(empty);
            return;
        }

        const columnsCount = 8;
        const tableWrap = document.createElement("div");
        tableWrap.className = "data-table-wrap admin-data-table-wrap";
        const table = document.createElement("table");
        table.className = "data-table admin-data-table station-tree-table";
        const thead = document.createElement("thead");
        const headRow = document.createElement("tr");
        ["Station", "Localisation", "Latitude", "Longitude", "Statut", "Bornes", "Emplacements", "Actions"].forEach((label) => {
            const th = document.createElement("th");
            th.textContent = label;
            headRow.appendChild(th);
        });
        thead.appendChild(headRow);
        table.appendChild(thead);

        const tbody = document.createElement("tbody");
        rows.forEach((station) => {
            const stationId = String(station.id_station);
            const stationBornes = bornes
                .filter((borne) => String(borne.station) === stationId)
                .sort((left, right) => Number(left.numero) - Number(right.numero));
            const stationEmplacements = emplacements
                .filter((emplacement) => String(emplacement.station) === stationId)
                .sort((left, right) => Number(left.borne_numero ?? 0) - Number(right.borne_numero ?? 0) || Number(left.numero) - Number(right.numero));
            const expanded = expandedStations.has(stationId);

            const stationRow = document.createElement("tr");
            stationRow.className = "expandable-row";
            stationRow.tabIndex = 0;
            stationRow.setAttribute("aria-expanded", String(expanded));

            const nameCell = document.createElement("td");
            const toggle = createActionButton(expanded ? "Masquer" : "Voir", () => {
                if (expandedStations.has(stationId)) {
                    expandedStations.delete(stationId);
                } else {
                    expandedStations.add(stationId);
                }
                renderStations();
            });
            toggle.className = "table-action station-toggle";
            toggle.setAttribute("aria-label", `${expanded ? "Masquer" : "Afficher"} les bornes et emplacements de ${station.nom}`);
            const nameStack = document.createElement("div");
            nameStack.className = "station-name-cell";
            const strong = document.createElement("strong");
            strong.textContent = station.nom;
            const small = document.createElement("small");
            small.textContent = expanded ? "Infrastructure affichée" : "Cliquer pour dérouler";
            nameStack.appendChild(strong);
            nameStack.appendChild(small);
            nameCell.appendChild(toggle);
            nameCell.appendChild(nameStack);
            stationRow.appendChild(nameCell);

            [station.localisation_text, station.latitude, station.longitude, station.statut, stationBornes.length, stationEmplacements.length].forEach((value) => {
                const td = document.createElement("td");
                td.textContent = value ?? "-";
                stationRow.appendChild(td);
            });

            const actionsCell = document.createElement("td");
            actionsCell.className = "actions-column";
            actionsCell.appendChild(renderActions({
                resource: "station",
                id: station.id_station,
                label: station.nom,
                onDelete: () => deleteAndReload(
                    `Supprimer la station ${station.nom} ?`,
                    () => window.AuthAPI.deleteAdminStation(station.id_station)
                ),
            }));
            stationRow.appendChild(actionsCell);

            const toggleStation = () => {
                if (expandedStations.has(stationId)) {
                    expandedStations.delete(stationId);
                } else {
                    expandedStations.add(stationId);
                }
                renderStations();
            };
            stationRow.addEventListener("click", (event) => {
                if (event.target.closest("a, button")) return;
                toggleStation();
            });
            stationRow.addEventListener("keydown", (event) => {
                if (event.key !== "Enter" && event.key !== " ") return;
                if (event.target.closest("a, button")) return;
                event.preventDefault();
                toggleStation();
            });
            tbody.appendChild(stationRow);

            if (expanded) {
                const detailsRow = document.createElement("tr");
                detailsRow.className = "station-details-row";
                const detailsCell = document.createElement("td");
                detailsCell.colSpan = columnsCount;
                detailsCell.appendChild(renderStationEmplacements(station, stationBornes, stationEmplacements));
                detailsRow.appendChild(detailsCell);
                tbody.appendChild(detailsRow);
            }
        });

        table.appendChild(tbody);
        tableWrap.appendChild(table);
        container.appendChild(tableWrap);
        renderPagination("stations-list", "stations");
    }

    function renderStationEmplacements(station, stationBornes, stationEmplacements) {
        const wrapper = document.createElement("div");
        wrapper.className = "station-emplacements-panel";

        const heading = document.createElement("div");
        heading.className = "station-emplacements-heading";
        const title = document.createElement("strong");
        title.textContent = `Bornes et emplacements de ${station.nom}`;
        const addBorneLink = createActionLink("Ajouter une borne", "/admin-form.html?resource=borne");
        addBorneLink.className = "table-action";
        const addLink = createActionLink("Ajouter un emplacement", "/admin-form.html?resource=emplacement");
        addLink.className = "table-action";
        heading.appendChild(title);
        heading.appendChild(addBorneLink);
        heading.appendChild(addLink);
        wrapper.appendChild(heading);

        if (!stationBornes.length && !stationEmplacements.length) {
            const empty = document.createElement("div");
            empty.className = "empty-state";
            empty.textContent = "Aucune borne ni emplacement pour cette station.";
            wrapper.appendChild(empty);
            return wrapper;
        }

        const grid = document.createElement("div");
        grid.className = "slot-grid";
        const bornesToRender = stationBornes.length
            ? stationBornes
            : [{ id_borne: "__unassigned__", nom: "Borne non renseign\u00e9e", numero: "-", statut: "-" }];

        bornesToRender.forEach((borne) => {
            const borneEmplacements = stationEmplacements.filter((emplacement) => String(emplacement.borne) === String(borne.id_borne));
            const card = document.createElement("article");
            card.className = "slot-card";
            const head = document.createElement("div");
            head.className = "slot-card-head";
            const borneTitle = document.createElement("strong");
            borneTitle.textContent = borne.nom || `Borne ${borne.numero}`;
            const statusBadge = createStatusBadge(borne.statut || "-", borne.statut === "active" ? "success" : "warning");
            head.appendChild(borneTitle);
            head.appendChild(statusBadge);

            const actions = document.createElement("div");
            actions.className = "table-actions";
            if (borne.id_borne !== "__unassigned__") {
                actions.appendChild(createActionLink("Modifier", editHref("borne", borne.id_borne)));
                actions.appendChild(createActionButton("Supprimer", () => deleteAndReload(
                    `Supprimer la borne ${borne.nom || borne.numero} ?`,
                    () => window.AuthAPI.deleteAdminBorne(borne.id_borne)
                ), "danger-action"));
            }

            const slots = document.createElement("div");
            slots.className = "stacked-list";
            if (!borneEmplacements.length) {
                const empty = document.createElement("p");
                empty.className = "helper";
                empty.textContent = "Aucun emplacement rattach\u00e9.";
                slots.appendChild(empty);
            } else {
                borneEmplacements.forEach((emplacement) => {
                    const row = document.createElement("div");
                    row.className = "list-item compact-list-item";
                    const rowHead = document.createElement("div");
                    rowHead.className = "list-item-head";
                    const emplacementTitle = document.createElement("strong");
                    emplacementTitle.textContent = `Emplacement ${emplacement.numero}`;
                    rowHead.appendChild(emplacementTitle);
                    rowHead.appendChild(createStatusBadge(emplacement.statut || "-", emplacement.statut === "disponible" ? "success" : "warning"));

                    const lock = document.createElement("p");
                    lock.textContent = `Serrure : ${emplacement.lock_state || "-"}`;

                    const slotActions = document.createElement("div");
                    slotActions.className = "table-actions";
                    slotActions.appendChild(createActionLink("Modifier", editHref("emplacement", emplacement.id_emplacement)));
                    slotActions.appendChild(createActionButton("Supprimer", () => deleteAndReload(
                        `Supprimer l'emplacement ${emplacement.numero} ?`,
                        () => window.AuthAPI.deleteAdminEmplacement(emplacement.id_emplacement)
                    ), "danger-action"));

                    row.appendChild(rowHead);
                    row.appendChild(lock);
                    row.appendChild(slotActions);
                    slots.appendChild(row);
                });
            }

            card.appendChild(head);
            card.appendChild(actions);
            card.appendChild(slots);
            grid.appendChild(card);
        });
        wrapper.appendChild(grid);
        return wrapper;
    }

    function renderTechnicians() {
        createDataTable(
            document.getElementById("technicians-list"),
            [
                { label: "Nom", render: (technician) => technician.nom },
                { label: "E-mail", render: (technician) => technician.email },
                { label: "Utilisateur li\u00e9", render: (technician) => technician.utilisateur_pseudo || "-" },
                { label: "T\u00e9l\u00e9phone", render: (technician) => technician.telephone || "-" },
                {
                    label: "Actions",
                    className: "actions-column",
                    render: (technician) => renderActions({
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
                { label: "Type", render: (maintenance) => maintenance.type },
                { label: "Statut", render: (maintenance) => maintenance.status },
                { label: "Date planifi\u00e9e", render: (maintenance) => formatDateTime(maintenance.date_planifiee) },
                { label: "Date r\u00e9alis\u00e9e", render: (maintenance) => formatDateTime(maintenance.date_realisee) },
                {
                    label: "Actions",
                    className: "actions-column",
                    render: (maintenance) => renderActions({
                        resource: "maintenance",
                        id: maintenance.id_maintenance,
                        label: maintenance.type,
                        onDelete: () => deleteAndReload(
                            `Supprimer la maintenance ${maintenance.type} ?`,
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

    function renderReservations(containerId, rows, emptyMessage, searchKey) {
        createDataTable(
            document.getElementById(containerId),
            [
                { label: "Code", render: (reservation) => reservation.reference_code || "-" },
                { label: "Utilisateur", render: (reservation) => reservation.utilisateur_pseudo || "-" },
                { label: "Station", render: (reservation) => reservation.station_nom || "-" },
                { label: "Borne", render: (reservation) => reservation.borne_nom || "-" },
                { label: "Emplacement", render: (reservation) => reservation.emplacement_numero || reservation.emplacement || "-" },
                { label: "Début", render: (reservation) => formatDateTime(reservation.date_debut) },
                { label: "Fin", render: (reservation) => formatDateTime(reservation.date_fin) },
                { label: "Mode", render: (reservation) => reservation.auth_mode || "-" },
                { label: "Accès", className: "access-column", render: renderAccessSummary },
                { label: "Statut", render: (reservation) => reservation.statut || "-" },
                {
                    label: "Actions",
                    className: "actions-column reservation-actions-column",
                    render: renderReservationActions,
                },
            ],
            filterRows(searchKey, rows),
            emptyMessageFor(searchKey, emptyMessage)
        );
    }

    function renderSessions(containerId, rows, emptyMessage, searchKey) {
        createDataTable(
            document.getElementById(containerId),
            [
                { label: "Utilisateur", render: (session) => session.utilisateur_pseudo || "-" },
                { label: "Code réservation", render: (session) => session.reference_code || "-" },
                { label: "Station", render: (session) => session.station || "-" },
                { label: "Borne", render: (session) => session.borne || "-" },
                { label: "Emplacement", render: (session) => session.emplacement || "-" },
                { label: "Début", render: (session) => formatDateTime(session.start_time) },
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
        document.getElementById("stat-alerts-active").textContent = stats.active_alerts ?? "-";
        document.getElementById("stat-alerts-critical").textContent = stats.critical_alerts ?? "-";
        document.getElementById("stat-telemetry-24h").textContent = stats.telemetry_samples_24h ?? "-";

        createDataTable(
            document.getElementById("admin-devices-list"),
            [
                { label: "Emplacement", render: (device) => device.slot_label || device.slot_id || "-" },
                { label: "Connexion", render: (device) => createStatusBadge(device.online ? "En ligne" : "Hors ligne", device.online ? "success" : "danger") },
                { label: "Dernier état reçu", render: (device) => device.status_display || device.status || "-" },
                { label: "Dernier ACK", render: formatCommandAck },
                { label: "Station", render: (device) => device.station_nom || "-" },
                { label: "Borne", render: (device) => device.borne_nom || "-" },
                { label: "Emplacement", render: (device) => device.emplacement_numero ?? "-" },
                { label: "Serrure", render: (device) => device.lock_state || "-" },
                { label: "Firmware", render: (device) => device.firmware_version || "-" },
                { label: "IP", render: (device) => device.ip_address || "-" },
                { label: "Dernier signal", render: (device) => formatDateTime(device.last_seen) },
            ],
            paginateRows(supervision.devices || [], supervisionPaginationState.devices),
            "Aucun ESP32 enregistré."
        );

        renderClientPagination("admin-devices-list", "devices", supervision.devices || [], renderSupervision);

        createDataTable(
            document.getElementById("admin-commands-list"),
            [
                { label: "Date", render: (command) => formatDateTime(command.timestamp) },
                { label: "Emplacement", render: (command) => command.slot_label || command.slot_id || "-" },
                { label: "Action", render: (command) => command.action || "-" },
                { label: "Statut", render: (command) => createStatusBadge(command.status || "-", ["accepted", "stopped", "locked", "unlocked"].includes(command.status) ? "success" : "warning") },
                { label: "Message", render: (command) => command.message || "-" },
                { label: "Source", render: (command) => command.source || "-" },
                { label: "Session", render: (command) => command.session_id || "-" },
            ],
            paginateRows(supervision.commands || [], supervisionPaginationState.commands),
            "Aucune commande ESP32 reçue."
        );

        renderClientPagination("admin-commands-list", "commands", supervision.commands || [], renderSupervision);

        createDataTable(
            document.getElementById("admin-alerts-list"),
            [
                { label: "Date", render: (alert) => formatDateTime(alert.timestamp) },
                { label: "Type", render: (alert) => alert.type || "-" },
                { label: "Sévérité", render: (alert) => createStatusBadge(alert.niveau_severite || "-", ["critical", "critique"].includes(alert.niveau_severite) ? "danger" : "warning") },
                { label: "Statut", render: (alert) => alert.status || "-" },
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
        renderReservations("admin-upcoming-reservations", upcomingReservations, "Aucune réservation à venir.", "upcomingReservations");
        renderReservations("admin-archived-reservations", archivedReservations, "Aucune réservation archivée.", "archivedReservations");
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

            let adminReservations = { upcoming: [], archived: [] };
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
            upcomingReservations = adminReservations.upcoming || [];
            archivedReservations = adminReservations.archived || [];
            activeSessions = adminSessions.active || [];
            archivedSessions = adminSessions.archived || [];

            renderAllTables();

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

    document.querySelectorAll("[data-admin-search]").forEach((input) => {
        input.addEventListener("input", () => {
            searchState[input.dataset.adminSearch] = input.value;
            renderAllTables();
        });
    });

    document.querySelectorAll("[data-admin-tab]").forEach((button) => {
        button.addEventListener("click", () => setAdminTab(button.dataset.adminTab));
    });

    document.querySelectorAll("[data-admin-jump]").forEach((button) => {
        button.addEventListener("click", () => setAdminTab(button.dataset.adminJump));
    });

    logoutBtn.addEventListener("click", () => window.AuthAPI.logout());
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

        await loadAll();
        supervisionRealtimeStarted = true;
        connectSupervisionSocket();
        const initialTab = (window.location.hash || "#overview").replace("#", "");
        const allowedTabs = ["overview", "supervision", "users", "infrastructure", "reservations", "sessions", "operations"];
        setAdminTab(allowedTabs.includes(initialTab) ? initialTab : "overview", false);

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
