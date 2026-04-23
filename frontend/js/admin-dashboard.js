function createItemRow(title, details, onEdit, onDelete) {
    const item = document.createElement("article");
    item.className = "list-item";

    const head = document.createElement("div");
    head.className = "list-item-head";

    const titleEl = document.createElement("strong");
    titleEl.textContent = title;

    const actions = document.createElement("div");
    actions.className = "cta-row";
    actions.style.marginTop = "0";
    actions.style.gap = "8px";

    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.className = "btn btn-secondary";
    editButton.textContent = "Modifier";
    editButton.addEventListener("click", onEdit);

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "btn btn-secondary";
    deleteButton.textContent = "Supprimer";
    deleteButton.addEventListener("click", onDelete);

    actions.appendChild(editButton);
    actions.appendChild(deleteButton);
    head.appendChild(titleEl);
    head.appendChild(actions);
    item.appendChild(head);

    details.forEach((line) => {
        const p = document.createElement("p");
        p.textContent = line;
        item.appendChild(p);
    });

    return item;
}

document.addEventListener("DOMContentLoaded", async () => {
    const status = document.getElementById("admin-status");
    const logoutBtn = document.getElementById("logout-admin");
    const refreshBtn = document.getElementById("refresh-admin");
    const userForm = document.getElementById("user-form");
    const stationForm = document.getElementById("station-form");
    const emplacementForm = document.getElementById("emplacement-form");
    const userCancel = document.getElementById("user-cancel");
    const stationCancel = document.getElementById("station-cancel");
    const emplacementCancel = document.getElementById("emplacement-cancel");

    let users = [];
    let stations = [];
    let emplacements = [];
    let isStaff = false;
    let currentAdminId = null;

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
        userForm.querySelector('button[type="submit"]').textContent = "Enregistrer utilisateur";
    }

    function resetStationForm() {
        stationForm.station_id.value = "";
        stationForm.nom.value = "";
        stationForm.localisation_text.value = "";
        stationForm.latitude.value = "";
        stationForm.longitude.value = "";
        stationForm.statut.value = "active";
        stationForm.querySelector('button[type="submit"]').textContent = "Enregistrer station";
    }

    function resetEmplacementForm() {
        emplacementForm.emplacement_id.value = "";
        emplacementForm.station.value = "";
        emplacementForm.numero.value = "";
        emplacementForm.statut.value = "disponible";
        emplacementForm.lock_state.value = "verrouille";
        emplacementForm.querySelector('button[type="submit"]').textContent = "Enregistrer emplacement";
    }

    function fillStationSelect() {
        const select = emplacementForm.station;
        select.innerHTML = "";
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "Choisir une station";
        select.appendChild(placeholder);

        stations.forEach((station) => {
            const option = document.createElement("option");
            option.value = station.id_station;
            option.textContent = `${station.nom} - ${station.localisation_text}`;
            select.appendChild(option);
        });
    }

    function renderUsers() {
        const list = document.getElementById("users-list");
        list.innerHTML = "";

        if (users.length === 0) {
            const empty = document.createElement("div");
            empty.className = "empty-state";
            empty.textContent = "Aucun utilisateur.";
            list.appendChild(empty);
            return;
        }

        users.forEach((user) => {
            list.appendChild(
                createItemRow(
                    `${user.pseudo} (${user.email})`,
                    [
                        `Nom: ${user.nom || "-"}`,
                        `Telephone: ${user.telephone || "-"}`,
                        `Statut: ${user.statut || "-"}`,
                        `Staff: ${user.is_staff ? "oui" : "non"}`,
                    ],
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
                        userForm.querySelector('button[type="submit"]').textContent = "Mettre a jour l'utilisateur";
                    },
                    async () => {
                        try {
                            if (user.id_user === currentAdminId) {
                                status.classList.add("error");
                                status.textContent = "Tu ne peux pas supprimer ton propre compte depuis cet ecran.";
                                return;
                            }
                            if (!window.confirm(`Supprimer l'utilisateur ${user.pseudo} ?`)) {
                                return;
                            }
                            await window.AuthAPI.deleteAdminUser(user.id_user);
                            await loadAll();
                        } catch (error) {
                            status.classList.add("error");
                            status.textContent = error.message || "Suppression utilisateur impossible.";
                        }
                    }
                )
            );
        });
    }

    function renderStations() {
        const list = document.getElementById("stations-list");
        list.innerHTML = "";

        if (stations.length === 0) {
            const empty = document.createElement("div");
            empty.className = "empty-state";
            empty.textContent = "Aucune station.";
            list.appendChild(empty);
            return;
        }

        stations.forEach((station) => {
            list.appendChild(
                createItemRow(
                    station.nom,
                    [
                        station.localisation_text,
                        `Coordonnees: ${station.latitude}, ${station.longitude}`,
                        `Statut: ${station.statut}`,
                    ],
                    () => {
                        stationForm.station_id.value = station.id_station;
                        stationForm.nom.value = station.nom;
                        stationForm.localisation_text.value = station.localisation_text;
                        stationForm.latitude.value = station.latitude;
                        stationForm.longitude.value = station.longitude;
                        stationForm.statut.value = station.statut;
                        stationForm.querySelector('button[type="submit"]').textContent = "Mettre a jour la station";
                    },
                    async () => {
                        try {
                            if (!window.confirm(`Supprimer la station ${station.nom} ?`)) {
                                return;
                            }
                            await window.AuthAPI.deleteAdminStation(station.id_station);
                            await loadAll();
                        } catch (error) {
                            status.classList.add("error");
                            status.textContent = error.message || "Suppression station impossible.";
                        }
                    }
                )
            );
        });
    }

    function renderEmplacements() {
        const list = document.getElementById("emplacements-list");
        list.innerHTML = "";

        if (emplacements.length === 0) {
            const empty = document.createElement("div");
            empty.className = "empty-state";
            empty.textContent = "Aucun emplacement.";
            list.appendChild(empty);
            return;
        }

        emplacements.forEach((emplacement) => {
            list.appendChild(
                createItemRow(
                    `Emplacement ${emplacement.numero} - ${emplacement.station_nom}`,
                    [
                        `Statut: ${emplacement.statut}`,
                        `Serrure: ${emplacement.lock_state}`,
                    ],
                    () => {
                        emplacementForm.emplacement_id.value = emplacement.id_emplacement;
                        emplacementForm.station.value = emplacement.station;
                        emplacementForm.numero.value = emplacement.numero;
                        emplacementForm.statut.value = emplacement.statut;
                        emplacementForm.lock_state.value = emplacement.lock_state;
                        emplacementForm.querySelector('button[type="submit"]').textContent = "Mettre a jour l'emplacement";
                    },
                    async () => {
                        try {
                            if (!window.confirm(`Supprimer l'emplacement ${emplacement.numero} ?`)) {
                                return;
                            }
                            await window.AuthAPI.deleteAdminEmplacement(emplacement.id_emplacement);
                            await loadAll();
                        } catch (error) {
                            status.classList.add("error");
                            status.textContent = error.message || "Suppression emplacement impossible.";
                        }
                    }
                )
            );
        });
    }

    async function loadAll() {
        const overview = await window.AuthAPI.getAdminOverview();
        const adminUsers = await window.AuthAPI.getAdminUsers();
        const adminStations = await window.AuthAPI.getAdminStations();
        const adminEmplacements = await window.AuthAPI.getAdminEmplacements();

        document.getElementById("stat-users").textContent = overview.stats.users_total;
        document.getElementById("stat-stations").textContent = overview.stats.stations_total;
        document.getElementById("stat-emplacements").textContent = overview.stats.emplacements_total;

        users = adminUsers.results || [];
        stations = adminStations.results || [];
        emplacements = adminEmplacements.results || [];

        fillStationSelect();
        renderUsers();
        renderStations();
        renderEmplacements();

        status.classList.remove("error");
        status.textContent = "Administration chargee.";
    }

    logoutBtn.addEventListener("click", () => window.AuthAPI.logout());
    refreshBtn.addEventListener("click", async () => {
        await loadAll();
    });

    userCancel.addEventListener("click", resetUserForm);
    stationCancel.addEventListener("click", resetStationForm);
    emplacementCancel.addEventListener("click", resetEmplacementForm);

    userForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        status.classList.remove("error");
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
                    status.classList.add("error");
                    status.textContent = "Le mot de passe est obligatoire pour creer un utilisateur.";
                    submitButton.disabled = false;
                    return;
                }
                await window.AuthAPI.createAdminUser({
                    ...payload,
                    password: userForm.password.value,
                });
            }
            resetUserForm();
            await loadAll();
        } catch (error) {
            status.classList.add("error");
            status.textContent = error.message || "Erreur utilisateur.";
        } finally {
            submitButton.disabled = false;
        }
    });

    stationForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        status.classList.remove("error");
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
            status.classList.add("error");
            status.textContent = error.message || "Erreur station.";
        } finally {
            submitButton.disabled = false;
        }
    });

    emplacementForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        status.classList.remove("error");
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
                await window.AuthAPI.updateAdminEmplacement(
                    emplacementForm.emplacement_id.value,
                    payload
                );
            } else {
                await window.AuthAPI.createAdminEmplacement(payload);
            }
            resetEmplacementForm();
            await loadAll();
        } catch (error) {
            status.classList.add("error");
            status.textContent = error.message || "Erreur emplacement.";
        } finally {
            submitButton.disabled = false;
        }
    });

    const session = await window.AuthAPI.ensureSession();
    if (!session) {
        status.classList.add("error");
        status.textContent = "Session absente ou expiree. Redirection vers la connexion.";
        window.setTimeout(() => {
            window.location.href = "/login.html";
        }, 1200);
        return;
    }

    try {
        const dashboard = await window.AuthAPI.getDashboard();
        isStaff = Boolean(dashboard.user?.is_staff);
        currentAdminId = dashboard.user?.id || null;
        if (!isStaff) {
            status.classList.add("error");
            status.textContent = "Acces refuse. Redirection vers le dashboard utilisateur.";
            window.setTimeout(() => {
                window.location.href = "/dashboard.html";
            }, 1200);
            return;
        }

        resetUserForm();
        resetStationForm();
        resetEmplacementForm();
        await loadAll();
    } catch (_error) {
        status.classList.add("error");
        status.textContent = "Impossible de charger l'administration.";
        window.AuthAPI.clearTokens();
        window.setTimeout(() => {
            window.location.href = "/login.html";
        }, 1200);
    }
});
