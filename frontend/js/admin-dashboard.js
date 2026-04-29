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

document.addEventListener("DOMContentLoaded", async () => {
    const AUTO_REFRESH_MS = 30000;
    const status = document.getElementById("admin-status");
    const logoutBtn = document.getElementById("logout-admin");

    let users = [];
    let stations = [];
    let emplacements = [];
    let technicians = [];
    let maintenances = [];
    let upcomingReservations = [];
    let archivedReservations = [];
    let activeSessions = [];
    let archivedSessions = [];
    let currentAdminId = null;
    let isLoading = false;

    function setAdminTab(name, pushHash = true) {
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

    function renderCancelAction(reservation) {
        const actions = document.createElement("div");
        actions.className = "table-actions";

        const button = createActionButton("Annuler", () => deleteAndReload(
            `Annuler la réservation ${reservation.reference_code || ""} ?`,
            () => window.AuthAPI.cancelAdminReservation(reservation.id_reservation)
        ), "danger-action");
        button.disabled = !reservation.can_cancel;
        if (!reservation.can_cancel) {
            button.title = "Cette réservation ne peut plus être annulée.";
        }
        actions.appendChild(button);
        return actions;
    }

    async function deleteAndReload(confirmMessage, deleteRequest) {
        if (!window.confirm(confirmMessage)) return;
        try {
            await deleteRequest();
            await loadAll();
            setStatus("Suppression effectu\u00e9e.");
        } catch (error) {
            setStatus(error.message || "Suppression impossible.", true);
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
            users,
            "Aucun utilisateur."
        );
    }

    function renderStations() {
        createDataTable(
            document.getElementById("stations-list"),
            [
                { label: "Nom", render: (station) => station.nom },
                { label: "Localisation", render: (station) => station.localisation_text },
                { label: "Latitude", render: (station) => station.latitude },
                { label: "Longitude", render: (station) => station.longitude },
                { label: "Statut", render: (station) => station.statut },
                {
                    label: "Actions",
                    className: "actions-column",
                    render: (station) => renderActions({
                        resource: "station",
                        id: station.id_station,
                        label: station.nom,
                        onDelete: () => deleteAndReload(
                            `Supprimer la station ${station.nom} ?`,
                            () => window.AuthAPI.deleteAdminStation(station.id_station)
                        ),
                    }),
                },
            ],
            stations,
            "Aucune station."
        );
    }

    function renderEmplacements() {
        createDataTable(
            document.getElementById("emplacements-list"),
            [
                { label: "Station", render: (emplacement) => emplacement.station_nom },
                { label: "Num\u00e9ro", render: (emplacement) => emplacement.numero },
                { label: "Statut", render: (emplacement) => emplacement.statut },
                { label: "Serrure", render: (emplacement) => emplacement.lock_state },
                {
                    label: "Actions",
                    className: "actions-column",
                    render: (emplacement) => renderActions({
                        resource: "emplacement",
                        id: emplacement.id_emplacement,
                        label: `emplacement ${emplacement.numero}`,
                        onDelete: () => deleteAndReload(
                            `Supprimer l'emplacement ${emplacement.numero} ?`,
                            () => window.AuthAPI.deleteAdminEmplacement(emplacement.id_emplacement)
                        ),
                    }),
                },
            ],
            emplacements,
            "Aucun emplacement."
        );
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
            technicians,
            "Aucun technicien."
        );
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
            maintenances,
            "Aucune maintenance."
        );
    }

    function renderReservations(containerId, rows, emptyMessage) {
        createDataTable(
            document.getElementById(containerId),
            [
                { label: "Code", render: (reservation) => reservation.reference_code || "-" },
                { label: "Utilisateur", render: (reservation) => reservation.utilisateur_pseudo || "-" },
                { label: "Station", render: (reservation) => reservation.station_nom || "-" },
                { label: "Emplacement", render: (reservation) => reservation.emplacement_numero || reservation.emplacement || "-" },
                { label: "Début", render: (reservation) => formatDateTime(reservation.date_debut) },
                { label: "Fin", render: (reservation) => formatDateTime(reservation.date_fin) },
                { label: "Mode", render: (reservation) => reservation.auth_mode || "-" },
                { label: "Statut", render: (reservation) => reservation.statut || "-" },
                {
                    label: "Actions",
                    className: "actions-column",
                    render: renderCancelAction,
                },
            ],
            rows,
            emptyMessage
        );
    }

    function renderSessions(containerId, rows, emptyMessage) {
        createDataTable(
            document.getElementById(containerId),
            [
                { label: "Utilisateur", render: (session) => session.utilisateur_pseudo || "-" },
                { label: "Code réservation", render: (session) => session.reference_code || "-" },
                { label: "Station", render: (session) => session.station || "-" },
                { label: "Emplacement", render: (session) => session.emplacement || "-" },
                { label: "Début", render: (session) => formatDateTime(session.start_time) },
                { label: "Fin", render: (session) => formatDateTime(session.end_time) },
                { label: "Statut", render: (session) => session.status === "active" ? "En cours" : "Archivée" },
            ],
            rows,
            emptyMessage
        );
    }

    async function loadAll() {
        if (isLoading) return;
        isLoading = true;

        try {
            const [
                overview,
                adminUsers,
                adminStations,
                adminEmplacements,
                adminTechnicians,
                adminMaintenances,
            ] = await Promise.all([
                window.AuthAPI.getAdminOverview(),
                window.AuthAPI.getAdminUsers(),
                window.AuthAPI.getAdminStations(),
                window.AuthAPI.getAdminEmplacements(),
                window.AuthAPI.getAdminTechnicians(),
                window.AuthAPI.getAdminMaintenances(),
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

            document.getElementById("stat-users").textContent = overview.stats.users_total;
            document.getElementById("stat-stations").textContent = overview.stats.stations_total;
            document.getElementById("stat-emplacements").textContent = overview.stats.emplacements_total;
            document.getElementById("stat-reservations-upcoming").textContent = overview.stats.reservations_upcoming ?? "-";
            document.getElementById("stat-sessions-active").textContent = overview.stats.sessions_active ?? "-";
            document.getElementById("stat-sessions-archived").textContent = overview.stats.sessions_archived ?? "-";

            users = adminUsers.results || [];
            stations = adminStations.results || [];
            emplacements = adminEmplacements.results || [];
            technicians = adminTechnicians.results || [];
            maintenances = adminMaintenances.results || [];
            upcomingReservations = adminReservations.upcoming || [];
            archivedReservations = adminReservations.archived || [];
            activeSessions = adminSessions.active || [];
            archivedSessions = adminSessions.archived || [];

            renderUsers();
            renderStations();
            renderEmplacements();
            renderTechnicians();
            renderMaintenances();
            renderReservations("admin-upcoming-reservations", upcomingReservations, "Aucune réservation à venir.");
            renderReservations("admin-archived-reservations", archivedReservations, "Aucune réservation archivée.");
            renderSessions("admin-active-sessions", activeSessions, "Aucune session en cours.");
            renderSessions("admin-archived-sessions", archivedSessions, "Aucune session archivée.");

            setStatus(
                optionalDataFailed
                    ? "Administration chargée. Redémarrez le backend pour activer les vues réservations/sessions."
                    : "Données chargées. Mise à jour automatique toutes les 30 secondes.",
                optionalDataFailed
            );
        } finally {
            isLoading = false;
        }
    }

    document.querySelectorAll("[data-admin-tab]").forEach((button) => {
        button.addEventListener("click", () => setAdminTab(button.dataset.adminTab));
    });

    document.querySelectorAll("[data-admin-jump]").forEach((button) => {
        button.addEventListener("click", () => setAdminTab(button.dataset.adminJump));
    });

    logoutBtn.addEventListener("click", () => window.AuthAPI.logout());

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
        const initialTab = (window.location.hash || "#overview").replace("#", "");
        const allowedTabs = ["overview", "users", "infrastructure", "reservations", "sessions", "operations"];
        setAdminTab(allowedTabs.includes(initialTab) ? initialTab : "overview", false);

        window.setInterval(async () => {
            try {
                await loadAll();
            } catch (_error) {
                setStatus("Impossible de rafra\u00eechir l'administration.", true);
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
