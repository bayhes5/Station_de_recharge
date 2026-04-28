function toLocalInputValue(value) {
    if (!value) return "";
    const date = new Date(value);
    const offset = date.getTimezoneOffset() * 60000;
    return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function fromLocalInputValue(value) {
    if (!value) return "";
    return new Date(value).toISOString();
}

function createActionButton(label, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "table-action";
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
    tableWrap.className = "data-table-wrap";
    const table = document.createElement("table");
    table.className = "data-table";

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

document.addEventListener("DOMContentLoaded", async () => {
    const AUTO_REFRESH_MS = 30000;
    const status = document.getElementById("admin-status");
    const logoutBtn = document.getElementById("logout-admin");
    const userForm = document.getElementById("user-form");
    const stationForm = document.getElementById("station-form");
    const emplacementForm = document.getElementById("emplacement-form");
    const technicianForm = document.getElementById("technician-form");
    const maintenanceForm = document.getElementById("maintenance-form");
    const userCancel = document.getElementById("user-cancel");
    const stationCancel = document.getElementById("station-cancel");
    const emplacementCancel = document.getElementById("emplacement-cancel");
    const technicianCancel = document.getElementById("technician-cancel");
    const maintenanceCancel = document.getElementById("maintenance-cancel");

    let users = [];
    let stations = [];
    let emplacements = [];
    let technicians = [];
    let maintenances = [];
    let currentAdminId = null;
    let isLoading = false;

    function setAdminTab(name) {
        document.querySelectorAll("[data-admin-tab]").forEach((button) => {
            button.classList.toggle("active", button.dataset.adminTab === name);
            button.setAttribute("aria-selected", String(button.dataset.adminTab === name));
        });
        document.querySelectorAll("[data-admin-panel]").forEach((panel) => {
            panel.hidden = panel.dataset.adminPanel !== name;
        });
    }

    function setStatus(message, isError = false) {
        status.classList.toggle("error", isError);
        status.textContent = message;
    }

    function isEditingForm() {
        return Boolean(document.activeElement?.closest("form"));
    }

    function resetUserForm() {
        userForm.user_id.value = "";
        userForm.pseudo.value = "";
        userForm.email.value = "";
        userForm.telephone.value = "";
        userForm.nom.value = "";
        userForm.statut.value = "actif";
        userForm.password.value = "";
        userForm.is_active.checked = true;
        userForm.is_staff.checked = false;
        userForm.is_superuser.checked = false;
        userForm.querySelector('button[type="submit"]').textContent = "Enregistrer l’utilisateur";
    }

    function resetStationForm() {
        stationForm.station_id.value = "";
        stationForm.nom.value = "";
        stationForm.localisation_text.value = "";
        stationForm.latitude.value = "";
        stationForm.longitude.value = "";
        stationForm.statut.value = "active";
        stationForm.querySelector('button[type="submit"]').textContent = "Enregistrer la station";
    }

    function resetEmplacementForm() {
        emplacementForm.emplacement_id.value = "";
        emplacementForm.numero.value = "";
        emplacementForm.statut.value = "disponible";
        emplacementForm.lock_state.value = "verrouillée";
        emplacementForm.querySelector('button[type="submit"]').textContent = "Enregistrer l’emplacement";
    }

    function resetTechnicianForm() {
        technicianForm.technician_id.value = "";
        technicianForm.utilisateur.value = "";
        technicianForm.nom.value = "";
        technicianForm.email.value = "";
        technicianForm.telephone.value = "";
        technicianForm.querySelector('button[type="submit"]').textContent = "Enregistrer le technicien";
    }

    function resetMaintenanceForm() {
        maintenanceForm.maintenance_id.value = "";
        maintenanceForm.station.value = "";
        maintenanceForm.technicien.value = "";
        maintenanceForm.type.value = "";
        maintenanceForm.description.value = "";
        maintenanceForm.status.value = "planifiée";
        maintenanceForm.date_planifiee.value = "";
        maintenanceForm.date_realisee.value = "";
        maintenanceForm.querySelector('button[type="submit"]').textContent = "Enregistrer la maintenance";
    }

    function fillSelect(select, options, placeholder, getValue, getLabel) {
        select.innerHTML = "";
        const first = document.createElement("option");
        first.value = "";
        first.textContent = placeholder;
        select.appendChild(first);
        options.forEach((item) => {
            const option = document.createElement("option");
            option.value = getValue(item);
            option.textContent = getLabel(item);
            select.appendChild(option);
        });
    }

    function fillStationSelect() {
        fillSelect(
            maintenanceForm.station,
            stations,
            "Choisir une station",
            (station) => station.id_station,
            (station) => `${station.nom} - ${station.localisation_text}`
        );
        fillSelect(
            emplacementForm.station,
            stations,
            "Choisir une station",
            (station) => station.id_station,
            (station) => `${station.nom} - ${station.localisation_text}`
        );
    }

    function fillTechnicianSelect() {
        fillSelect(
            maintenanceForm.technicien,
            technicians,
            "Choisir un technicien",
            (technician) => technician.id_technicien,
            (technician) => `${technician.nom} (${technician.email})`
        );
        fillSelect(
            technicianForm.utilisateur,
            users,
            "Lier un utilisateur",
            (user) => user.id_user,
            (user) => `${user.pseudo} (${user.email})${user.is_technician ? " - technicien" : ""}`
        );
    }

    function renderActions(onEdit, onDelete) {
        const actions = document.createElement("div");
        actions.className = "table-actions";
        actions.appendChild(createActionButton("Modifier", onEdit));
        actions.appendChild(createActionButton("Supprimer", onDelete));
        return actions;
    }

    function renderUsers() {
        createDataTable(
            document.getElementById("users-list"),
            [
                { label: "Pseudo", render: (user) => user.pseudo },
                { label: "E-mail", render: (user) => user.email },
                { label: "Nom", render: (user) => user.nom || "-" },
                { label: "Téléphone", render: (user) => user.telephone || "-" },
                { label: "Statut", render: (user) => user.statut || "-" },
                {
                    label: "Rôles",
                    render: (user) => [
                        user.is_superuser ? "superuser" : null,
                        user.is_staff ? "staff" : null,
                        user.is_technician ? "technicien" : null,
                    ].filter(Boolean).join(", ") || "utilisateur",
                },
                {
                    label: "Actions",
                    render: (user) => renderActions(
                        () => {
                            userForm.user_id.value = user.id_user;
                            userForm.pseudo.value = user.pseudo;
                            userForm.email.value = user.email;
                            userForm.telephone.value = user.telephone || "";
                            userForm.nom.value = user.nom || "";
                            userForm.statut.value = user.statut || "actif";
                            userForm.password.value = "";
                            userForm.is_active.checked = user.is_active;
                            userForm.is_staff.checked = user.is_staff;
                            userForm.is_superuser.checked = user.is_superuser;
                            userForm.querySelector('button[type="submit"]').textContent = "Mettre à jour l’utilisateur";
                            setAdminTab("users");
                        },
                        async () => {
                            if (user.id_user === currentAdminId) {
                                setStatus("Vous ne pouvez pas supprimer votre propre compte depuis cet écran.", true);
                                return;
                            }
                            if (!window.confirm(`Supprimer l'utilisateur ${user.pseudo} ?`)) return;
                            try {
                                await window.AuthAPI.deleteAdminUser(user.id_user);
                                await loadAll();
                            } catch (error) {
                                setStatus(error.message || "Suppression utilisateur impossible.", true);
                            }
                        }
                    ),
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
                    render: (station) => renderActions(
                        () => {
                            stationForm.station_id.value = station.id_station;
                            stationForm.nom.value = station.nom;
                            stationForm.localisation_text.value = station.localisation_text;
                            stationForm.latitude.value = station.latitude;
                            stationForm.longitude.value = station.longitude;
                            stationForm.statut.value = station.statut;
                            stationForm.querySelector('button[type="submit"]').textContent = "Mettre à jour la station";
                            setAdminTab("infrastructure");
                        },
                        async () => {
                            if (!window.confirm(`Supprimer la station ${station.nom} ?`)) return;
                            try {
                                await window.AuthAPI.deleteAdminStation(station.id_station);
                                await loadAll();
                            } catch (error) {
                                setStatus(error.message || "Suppression station impossible.", true);
                            }
                        }
                    ),
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
                { label: "Numéro", render: (emplacement) => emplacement.numero },
                { label: "Statut", render: (emplacement) => emplacement.statut },
                { label: "Serrure", render: (emplacement) => emplacement.lock_state },
                {
                    label: "Actions",
                    render: (emplacement) => renderActions(
                        () => {
                            emplacementForm.emplacement_id.value = emplacement.id_emplacement;
                            emplacementForm.station.value = emplacement.station;
                            emplacementForm.numero.value = emplacement.numero;
                            emplacementForm.statut.value = emplacement.statut;
                            emplacementForm.lock_state.value = emplacement.lock_state;
                            emplacementForm.querySelector('button[type="submit"]').textContent = "Mettre à jour l’emplacement";
                            setAdminTab("infrastructure");
                        },
                        async () => {
                            if (!window.confirm(`Supprimer l'emplacement ${emplacement.numero} ?`)) return;
                            try {
                                await window.AuthAPI.deleteAdminEmplacement(emplacement.id_emplacement);
                                await loadAll();
                            } catch (error) {
                                setStatus(error.message || "Suppression emplacement impossible.", true);
                            }
                        }
                    ),
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
                { label: "Utilisateur lié", render: (technician) => technician.utilisateur_pseudo || "-" },
                { label: "Téléphone", render: (technician) => technician.telephone || "-" },
                {
                    label: "Actions",
                    render: (technician) => renderActions(
                        () => {
                            technicianForm.technician_id.value = technician.id_technicien;
                            technicianForm.utilisateur.value = technician.utilisateur || "";
                            technicianForm.nom.value = technician.nom;
                            technicianForm.email.value = technician.email;
                            technicianForm.telephone.value = technician.telephone || "";
                            technicianForm.querySelector('button[type="submit"]').textContent = "Mettre à jour le technicien";
                            setAdminTab("operations");
                        },
                        async () => {
                            if (!window.confirm(`Supprimer le technicien ${technician.nom} ?`)) return;
                            try {
                                await window.AuthAPI.deleteAdminTechnician(technician.id_technicien);
                                await loadAll();
                            } catch (error) {
                                setStatus(error.message || "Suppression technicien impossible.", true);
                            }
                        }
                    ),
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
                { label: "Date planifiée", render: (maintenance) => new Date(maintenance.date_planifiee).toLocaleString("fr-FR") },
                { label: "Date réalisée", render: (maintenance) => maintenance.date_realisee ? new Date(maintenance.date_realisee).toLocaleString("fr-FR") : "-" },
                {
                    label: "Actions",
                    render: (maintenance) => renderActions(
                        () => {
                            maintenanceForm.maintenance_id.value = maintenance.id_maintenance;
                            maintenanceForm.station.value = maintenance.station;
                            maintenanceForm.technicien.value = maintenance.technicien;
                            maintenanceForm.type.value = maintenance.type;
                            maintenanceForm.description.value = maintenance.description;
                            maintenanceForm.status.value = maintenance.status;
                            maintenanceForm.date_planifiee.value = toLocalInputValue(maintenance.date_planifiee);
                            maintenanceForm.date_realisee.value = toLocalInputValue(maintenance.date_realisee);
                            maintenanceForm.querySelector('button[type="submit"]').textContent = "Mettre à jour la maintenance";
                            setAdminTab("operations");
                        },
                        async () => {
                            if (!window.confirm(`Supprimer la maintenance ${maintenance.type} ?`)) return;
                            try {
                                await window.AuthAPI.deleteAdminMaintenance(maintenance.id_maintenance);
                                await loadAll();
                            } catch (error) {
                                setStatus(error.message || "Suppression maintenance impossible.", true);
                            }
                        }
                    ),
                },
            ],
            maintenances,
            "Aucune maintenance."
        );
    }

    async function loadAll() {
        if (isLoading) return;
        isLoading = true;

        try {
            const overview = await window.AuthAPI.getAdminOverview();
            const adminUsers = await window.AuthAPI.getAdminUsers();
            const adminStations = await window.AuthAPI.getAdminStations();
            const adminEmplacements = await window.AuthAPI.getAdminEmplacements();
            const adminTechnicians = await window.AuthAPI.getAdminTechnicians();
            const adminMaintenances = await window.AuthAPI.getAdminMaintenances();

            document.getElementById("stat-users").textContent = overview.stats.users_total;
            document.getElementById("stat-stations").textContent = overview.stats.stations_total;
            document.getElementById("stat-emplacements").textContent = overview.stats.emplacements_total;

            users = adminUsers.results || [];
            stations = adminStations.results || [];
            emplacements = adminEmplacements.results || [];
            technicians = adminTechnicians.results || [];
            maintenances = adminMaintenances.results || [];

            fillStationSelect();
            fillTechnicianSelect();
            renderUsers();
            renderStations();
            renderEmplacements();
            renderTechnicians();
            renderMaintenances();

            setStatus("Administration chargée. Mise à jour automatique toutes les 30 secondes.");
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

    userCancel.addEventListener("click", resetUserForm);
    stationCancel.addEventListener("click", resetStationForm);
    emplacementCancel.addEventListener("click", resetEmplacementForm);
    technicianCancel.addEventListener("click", resetTechnicianForm);
    maintenanceCancel.addEventListener("click", resetMaintenanceForm);

    userForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const submitButton = userForm.querySelector('button[type="submit"]');
        submitButton.disabled = true;

        const payload = {
            pseudo: userForm.pseudo.value.trim(),
            email: userForm.email.value.trim(),
            telephone: userForm.telephone.value.trim(),
            nom: userForm.nom.value.trim(),
            statut: userForm.statut.value.trim(),
            is_active: userForm.is_active.checked,
            is_staff: userForm.is_staff.checked,
            is_superuser: userForm.is_superuser.checked,
        };

        try {
            if (userForm.user_id.value) {
                await window.AuthAPI.updateAdminUser(userForm.user_id.value, payload);
            } else {
                if (!userForm.password.value) {
                    setStatus("Le mot de passe est obligatoire pour créer un utilisateur.", true);
                    return;
                }
                await window.AuthAPI.createAdminUser({ ...payload, password: userForm.password.value });
            }
            resetUserForm();
            await loadAll();
        } catch (error) {
            setStatus(error.message || "Erreur utilisateur.", true);
        } finally {
            submitButton.disabled = false;
        }
    });

    stationForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const submitButton = stationForm.querySelector('button[type="submit"]');
        submitButton.disabled = true;

        const payload = {
            nom: stationForm.nom.value.trim(),
            localisation_text: stationForm.localisation_text.value.trim(),
            latitude: Number(stationForm.latitude.value),
            longitude: Number(stationForm.longitude.value),
            statut: stationForm.statut.value.trim(),
        };

        try {
            if (stationForm.station_id.value) {
                await window.AuthAPI.updateAdminStation(stationForm.station_id.value, payload);
            } else {
                await window.AuthAPI.createAdminStation(payload);
            }
            resetStationForm();
            await loadAll();
        } catch (error) {
            setStatus(error.message || "Erreur station.", true);
        } finally {
            submitButton.disabled = false;
        }
    });

    emplacementForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const submitButton = emplacementForm.querySelector('button[type="submit"]');
        submitButton.disabled = true;

        const payload = {
            station: emplacementForm.station.value,
            numero: Number(emplacementForm.numero.value),
            statut: emplacementForm.statut.value.trim(),
            lock_state: emplacementForm.lock_state.value.trim(),
        };

        try {
            if (emplacementForm.emplacement_id.value) {
                await window.AuthAPI.updateAdminEmplacement(emplacementForm.emplacement_id.value, payload);
            } else {
                await window.AuthAPI.createAdminEmplacement(payload);
            }
            resetEmplacementForm();
            await loadAll();
        } catch (error) {
            setStatus(error.message || "Erreur emplacement.", true);
        } finally {
            submitButton.disabled = false;
        }
    });

    technicianForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const submitButton = technicianForm.querySelector('button[type="submit"]');
        submitButton.disabled = true;

        const payload = {
            utilisateur: technicianForm.utilisateur.value || null,
            nom: technicianForm.nom.value.trim(),
            email: technicianForm.email.value.trim(),
            telephone: technicianForm.telephone.value.trim(),
        };

        try {
            if (technicianForm.technician_id.value) {
                await window.AuthAPI.updateAdminTechnician(technicianForm.technician_id.value, payload);
            } else {
                await window.AuthAPI.createAdminTechnician(payload);
            }
            resetTechnicianForm();
            await loadAll();
        } catch (error) {
            setStatus(error.message || "Erreur technicien.", true);
        } finally {
            submitButton.disabled = false;
        }
    });

    maintenanceForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const submitButton = maintenanceForm.querySelector('button[type="submit"]');
        submitButton.disabled = true;

        const payload = {
            station: maintenanceForm.station.value,
            technicien: maintenanceForm.technicien.value,
            type: maintenanceForm.type.value.trim(),
            description: maintenanceForm.description.value.trim(),
            status: maintenanceForm.status.value.trim(),
            date_planifiee: fromLocalInputValue(maintenanceForm.date_planifiee.value),
            date_realisee: maintenanceForm.date_realisee.value ? fromLocalInputValue(maintenanceForm.date_realisee.value) : null,
        };

        try {
            if (maintenanceForm.maintenance_id.value) {
                await window.AuthAPI.updateAdminMaintenance(maintenanceForm.maintenance_id.value, payload);
            } else {
                await window.AuthAPI.createAdminMaintenance(payload);
            }
            resetMaintenanceForm();
            await loadAll();
        } catch (error) {
            setStatus(error.message || "Erreur maintenance.", true);
        } finally {
            submitButton.disabled = false;
        }
    });

    const session = await window.AuthAPI.ensureSession();
    if (!session) {
        setStatus("Session absente ou expirée. Redirection vers la connexion.", true);
        window.setTimeout(() => {
            window.location.href = "/login.html";
        }, 1200);
        return;
    }

    try {
        const dashboard = await window.AuthAPI.getDashboard();
        currentAdminId = dashboard.user?.id || null;
        if (!dashboard.user?.is_staff) {
            setStatus("Accès refusé. Redirection vers le tableau de bord utilisateur.", true);
            window.setTimeout(() => {
                window.location.href = "/dashboard.html";
            }, 1200);
            return;
        }

        resetUserForm();
        resetStationForm();
        resetEmplacementForm();
        resetTechnicianForm();
        resetMaintenanceForm();
        await loadAll();
        setAdminTab("overview");
        window.setInterval(async () => {
            if (isEditingForm()) return;

            try {
                await loadAll();
            } catch (_error) {
                setStatus("Impossible de rafraîchir l’administration.", true);
            }
        }, AUTO_REFRESH_MS);
    } catch (_error) {
        setStatus("Impossible de charger l’administration.", true);
        window.AuthAPI.clearTokens();
        window.setTimeout(() => {
            window.location.href = "/login.html";
        }, 1200);
    }
});
