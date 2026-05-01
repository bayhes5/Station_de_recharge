function toLocalInputValue(value) {
    if (!value) return "";
    const date = new Date(value);
    const offset = date.getTimezoneOffset() * 60000;
    return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function fromLocalInputValue(value) {
    return value ? new Date(value).toISOString() : null;
}

function formatDateTime(value) {
    if (!value) return "-";
    return new Date(value).toLocaleString("fr-FR");
}

function optionLabel(item, fallback = "-") {
    return item || fallback;
}

document.addEventListener("DOMContentLoaded", async () => {
    const params = new URLSearchParams(window.location.search);
    const resource = params.get("resource") || "user";
    const itemId = params.get("id");
    const isEdit = Boolean(itemId);

    const title = document.getElementById("admin-form-title");
    const lead = document.getElementById("admin-form-lead");
    const status = document.getElementById("admin-form-status");
    const fieldsHost = document.getElementById("admin-form-fields");
    const form = document.getElementById("admin-entity-form");
    const submitButton = document.getElementById("admin-form-submit");
    const backLink = document.getElementById("admin-form-back");
    const cancelLink = document.getElementById("admin-form-cancel");
    const logoutButton = document.getElementById("admin-form-logout");

    let users = [];
    let stations = [];
    let technicians = [];
    let currentItem = null;
    let passwordResetDialog = null;
    let authMethods = [];

    const configs = {
        user: {
            singular: "utilisateur",
            plural: "utilisateurs",
            tab: "users",
            idKey: "id_user",
            list: () => window.AuthAPI.getAdminUsers(),
            create: (payload) => window.AuthAPI.createAdminUser(payload),
            update: (id, payload) => window.AuthAPI.updateAdminUser(id, payload),
            fields: [
                { name: "pseudo", label: "Pseudo", type: "text", required: true },
                { name: "email", label: "E-mail", type: "email", required: true },
                { name: "telephone", label: "T\u00e9l\u00e9phone", type: "tel" },
                { name: "nom", label: "Nom", type: "text" },
                { name: "statut", label: "Statut", type: "text", defaultValue: "actif" },
                { name: "password", label: "Mot de passe", type: "password", createOnly: true, requiredOnCreate: true },
                { name: "is_active", label: "Actif", type: "checkbox", defaultValue: true },
                { name: "is_staff", label: "Staff", type: "checkbox" },
                { name: "is_superuser", label: "Super-administrateur", type: "checkbox" },
            ],
        },
        station: {
            singular: "station",
            plural: "stations",
            tab: "infrastructure",
            idKey: "id_station",
            list: () => window.AuthAPI.getAdminStations(),
            create: (payload) => window.AuthAPI.createAdminStation(payload),
            update: (id, payload) => window.AuthAPI.updateAdminStation(id, payload),
            fields: [
                { name: "nom", label: "Nom", type: "text", required: true },
                { name: "localisation_text", label: "Localisation", type: "text", required: true },
                { name: "latitude", label: "Latitude", type: "number", step: "any", required: true },
                { name: "longitude", label: "Longitude", type: "number", step: "any", required: true },
                { name: "statut", label: "Statut", type: "text", defaultValue: "active", required: true },
            ],
        },
        emplacement: {
            singular: "emplacement",
            plural: "emplacements",
            tab: "infrastructure",
            idKey: "id_emplacement",
            list: () => window.AuthAPI.getAdminEmplacements(),
            create: (payload) => window.AuthAPI.createAdminEmplacement(payload),
            update: (id, payload) => window.AuthAPI.updateAdminEmplacement(id, payload),
            fields: [
                { name: "station", label: "Station", type: "select", required: true, options: "stations" },
                { name: "numero", label: "Num\u00e9ro", type: "number", required: true },
                { name: "statut", label: "Statut", type: "text", defaultValue: "disponible", required: true },
                { name: "lock_state", label: "\u00c9tat serrure", type: "text", defaultValue: "verrouill\u00e9e", required: true },
            ],
        },
        technician: {
            singular: "technicien",
            plural: "techniciens",
            tab: "operations",
            idKey: "id_technicien",
            list: () => window.AuthAPI.getAdminTechnicians(),
            create: (payload) => window.AuthAPI.createAdminTechnician(payload),
            update: (id, payload) => window.AuthAPI.updateAdminTechnician(id, payload),
            fields: [
                { name: "utilisateur", label: "Utilisateur li\u00e9", type: "select", options: "users" },
                { name: "nom", label: "Nom", type: "text", required: true },
                { name: "email", label: "E-mail", type: "email", required: true },
                { name: "telephone", label: "T\u00e9l\u00e9phone", type: "tel" },
            ],
        },
        maintenance: {
            singular: "maintenance",
            plural: "maintenances",
            tab: "operations",
            idKey: "id_maintenance",
            list: () => window.AuthAPI.getAdminMaintenances(),
            create: (payload) => window.AuthAPI.createAdminMaintenance(payload),
            update: (id, payload) => window.AuthAPI.updateAdminMaintenance(id, payload),
            fields: [
                { name: "station", label: "Station", type: "select", required: true, options: "stations" },
                { name: "technicien", label: "Technicien", type: "select", required: true, options: "technicians" },
                { name: "type", label: "Type", type: "text", required: true },
                { name: "status", label: "Statut", type: "text", defaultValue: "planifi\u00e9e", required: true },
                { name: "description", label: "Description", type: "textarea", required: true, fullWidth: true },
                { name: "date_planifiee", label: "Date planifi\u00e9e", type: "datetime-local", required: true },
                { name: "date_realisee", label: "Date r\u00e9alis\u00e9e", type: "datetime-local" },
            ],
        },
    };

    const config = configs[resource];

    function returnUrl() {
        return `/admin-dashboard.html#${config?.tab || "overview"}`;
    }

    function setStatus(message, isError = false) {
        status.classList.toggle("error", isError);
        status.classList.toggle("success", Boolean(message) && !isError);
        status.textContent = message;
    }

    function getPasswordResetDialog() {
        if (!passwordResetDialog) {
            passwordResetDialog = createPasswordResetDialog();
        }
        return passwordResetDialog;
    }

    function createPasswordResetDialog() {
        const backdrop = document.createElement("div");
        backdrop.className = "modal-backdrop";
        backdrop.hidden = true;
        backdrop.innerHTML = `
            <section class="modal-dialog" role="dialog" aria-modal="true" aria-labelledby="reset-password-title">
                <div class="modal-heading">
                    <div>
                        <p class="eyebrow">Administration</p>
                        <h2 id="reset-password-title">Mot de passe temporaire</h2>
                    </div>
                    <button class="modal-close" type="button" aria-label="Fermer">&times;</button>
                </div>
                <div class="account-form">
                    <p id="reset-password-user" class="helper"></p>
                    <p class="helper">Copiez ce mot de passe maintenant. Il ne sera plus affich&eacute; apr&egrave;s fermeture.</p>
                    <div class="generated-password-box">
                        <code id="generated-password-value"></code>
                    </div>
                    <p id="reset-password-status" class="field-feedback" aria-live="polite"></p>
                    <div class="cta-row">
                        <button class="btn btn-primary" type="button" data-copy-password>Copier</button>
                        <button class="btn btn-secondary" type="button" data-reset-cancel>Fermer</button>
                    </div>
                </div>
            </section>
        `;

        document.body.appendChild(backdrop);

        const statusElement = backdrop.querySelector("#reset-password-status");
        const userElement = backdrop.querySelector("#reset-password-user");
        const passwordElement = backdrop.querySelector("#generated-password-value");
        let generatedPassword = "";

        function close() {
            generatedPassword = "";
            passwordElement.textContent = "";
            statusElement.textContent = "";
            statusElement.className = "field-feedback";
            backdrop.hidden = true;
        }

        function setDialogStatus(message, isError = false) {
            statusElement.textContent = message;
            statusElement.className = `field-feedback${isError ? " invalid" : " valid"}`;
        }

        backdrop.querySelector(".modal-close").addEventListener("click", close);
        backdrop.querySelector("[data-reset-cancel]").addEventListener("click", close);
        backdrop.querySelector("[data-copy-password]").addEventListener("click", async () => {
            if (!generatedPassword) return;

            try {
                await navigator.clipboard.writeText(generatedPassword);
                setDialogStatus("Mot de passe copi\u00e9.");
            } catch (_error) {
                setDialogStatus("Copie automatique impossible. S\u00e9lectionnez le mot de passe manuellement.", true);
            }
        });
        backdrop.addEventListener("click", (event) => {
            if (event.target === backdrop) {
                close();
            }
        });

        return {
            show(user, password) {
                generatedPassword = password;
                userElement.textContent = `Utilisateur : ${user.pseudo} (${user.email})`;
                passwordElement.textContent = password;
                statusElement.textContent = "";
                statusElement.className = "field-feedback";
                backdrop.hidden = false;
                backdrop.querySelector("[data-copy-password]").focus();
            },
        };
    }

    function renderPasswordResetPanel() {
        if (resource !== "user" || !isEdit) return;

        const panel = document.createElement("section");
        panel.className = "dashboard-panel admin-password-panel";
        panel.setAttribute("aria-labelledby", "admin-password-title");
        panel.innerHTML = `
            <div class="panel-heading admin-password-heading">
                <div>
                    <p id="admin-password-title" class="panel-title">Mot de passe</p>
                    <p class="helper">G&eacute;n&eacute;rez un mot de passe temporaire pour ce compte utilisateur.</p>
                </div>
                <button id="admin-reset-password" class="btn btn-secondary" type="button">R&eacute;initialiser le mot de passe</button>
            </div>
        `;

        panel.querySelector("#admin-reset-password").addEventListener("click", (event) => {
            resetCurrentUserPassword(event.currentTarget);
        });
        form.closest(".admin-edit-panel").after(panel);
    }

    function renderAuthMethodsPanel() {
        if (resource !== "user" || !isEdit) return;

        const panel = document.createElement("section");
        panel.className = "dashboard-panel admin-access-panel";
        panel.setAttribute("aria-labelledby", "admin-access-title");
        panel.innerHTML = `
            <div class="panel-heading admin-access-heading">
                <div>
                    <p id="admin-access-title" class="panel-title">Moyens d'acc&egrave;s</p>
                    <p class="helper">G&eacute;rez les badges RFID sans afficher leur valeur compl&egrave;te. Les QR codes et codes temporaires se g&egrave;rent depuis les r&eacute;servations.</p>
                </div>
            </div>
            <form id="admin-rfid-form" class="admin-inline-form">
                <div class="field">
                    <label for="admin-rfid-value">Nouveau badge RFID</label>
                    <input id="admin-rfid-value" name="auth_value" type="text" placeholder="Valeur du badge" autocomplete="off" required>
                </div>
                <button class="btn btn-secondary" type="submit">Associer / remplacer</button>
            </form>
            <div id="admin-auth-methods-list" class="stacked-list"></div>
        `;

        const anchor = document.querySelector(".admin-password-panel") || form.closest(".admin-edit-panel");
        anchor.after(panel);
        panel.querySelector("#admin-rfid-form").addEventListener("submit", handleRfidSubmit);
        renderAuthMethodsList(panel.querySelector("#admin-auth-methods-list"));
    }

    function renderAuthMethodsList(container = document.getElementById("admin-auth-methods-list")) {
        if (!container) return;
        container.innerHTML = "";

        if (!authMethods.length) {
            const empty = document.createElement("div");
            empty.className = "empty-state";
            empty.textContent = "Aucun badge RFID actif. Les QR codes et codes temporaires apparaissent dans l'administration des reservations.";
            container.appendChild(empty);
            return;
        }

        authMethods.forEach((method) => {
            const item = document.createElement("article");
            item.className = "list-item admin-access-item";

            const head = document.createElement("div");
            head.className = "list-item-head";

            const title = document.createElement("strong");
            title.textContent = method.type_label === "RFID" ? "Badge RFID" : method.type_label;

            const badge = document.createElement("span");
            badge.className = "badge";
            badge.textContent = method.is_active ? "Actif" : "Revoque";

            head.appendChild(title);
            head.appendChild(badge);

            const meta = document.createElement("p");
            const expiresAt = method.expiration ? formatDateTime(method.expiration) : "sans expiration";
            meta.textContent = `${method.display_value || "Valeur masquee"} | expire le ${expiresAt}`;

            const actions = document.createElement("div");
            actions.className = "cta-row compact-row";
            const revokeButton = document.createElement("button");
            revokeButton.className = "btn btn-secondary danger-action";
            revokeButton.type = "button";
            revokeButton.textContent = "Revoquer";
            revokeButton.addEventListener("click", () => revokeAuthMethod(method, revokeButton));
            actions.appendChild(revokeButton);

            item.appendChild(head);
            item.appendChild(meta);
            item.appendChild(actions);
            container.appendChild(item);
        });

        const temporaryAccessNote = document.createElement("p");
        temporaryAccessNote.className = "helper";
        temporaryAccessNote.textContent = "Les QR codes et codes temporaires de cet utilisateur restent visibles et gerables dans l'administration des reservations.";
        container.appendChild(temporaryAccessNote);
    }

    async function loadAuthMethods() {
        if (resource !== "user" || !isEdit) return;
        const result = await window.AuthAPI.getAdminUserAuthMethods(itemId);
        authMethods = result.results || [];
    }

    async function handleRfidSubmit(event) {
        event.preventDefault();
        const rfidForm = event.currentTarget;
        const submit = rfidForm.querySelector('button[type="submit"]');
        const authValue = rfidForm.auth_value.value.trim();
        if (!authValue) return;

        submit.disabled = true;
        try {
            await window.AuthAPI.createAdminUserRfid(itemId, { auth_value: authValue });
            rfidForm.reset();
            await loadAuthMethods();
            renderAuthMethodsList();
            setStatus(`Badge RFID associe a ${currentItem.pseudo}.`);
        } catch (error) {
            setStatus(error.message || "Impossible d'associer le badge RFID.", true);
        } finally {
            submit.disabled = false;
        }
    }

    async function revokeAuthMethod(method, triggerButton) {
        const confirmed = window.confirm(`Revoquer ce badge RFID pour ${currentItem.pseudo} ?`);
        if (!confirmed) return;

        triggerButton.disabled = true;
        try {
            await window.AuthAPI.revokeAdminUserAuthMethod(itemId, method.id_auth);
            await loadAuthMethods();
            renderAuthMethodsList();
            setStatus(`Badge RFID revoque pour ${currentItem.pseudo}.`);
        } catch (error) {
            setStatus(error.message || "Impossible de revoquer le badge RFID.", true);
            triggerButton.disabled = false;
        }
    }

    async function resetCurrentUserPassword(triggerButton) {
        if (!currentItem) return;

        const confirmed = window.confirm(
            `G\u00e9n\u00e9rer un nouveau mot de passe temporaire pour ${currentItem.pseudo} ?`
        );
        if (!confirmed) return;

        triggerButton.disabled = true;
        try {
            const result = await window.AuthAPI.resetAdminUserPassword(currentItem.id_user);
            getPasswordResetDialog().show(currentItem, result.temporary_password);
            setStatus(`Mot de passe temporaire g\u00e9n\u00e9r\u00e9 pour ${currentItem.pseudo}.`);
        } catch (error) {
            setStatus(error.message || "R\u00e9initialisation impossible.", true);
        } finally {
            triggerButton.disabled = false;
        }
    }

    function createField(field) {
        if (field.createOnly && isEdit) {
            return null;
        }

        const wrapper = document.createElement("div");
        wrapper.className = `field${field.fullWidth ? " admin-field-wide" : ""}`;

        if (field.type === "checkbox") {
            const label = document.createElement("label");
            const input = document.createElement("input");
            input.type = "checkbox";
            input.name = field.name;
            input.id = `admin-${field.name}`;
            input.checked = Boolean(field.defaultValue);
            label.appendChild(input);
            label.append(` ${field.label}`);
            wrapper.appendChild(label);
            return wrapper;
        }

        const label = document.createElement("label");
        label.htmlFor = `admin-${field.name}`;
        label.textContent = field.label;

        let input;
        if (field.type === "textarea") {
            input = document.createElement("textarea");
            input.rows = 4;
        } else if (field.type === "select") {
            input = document.createElement("select");
            appendOptions(input, field);
        } else {
            input = document.createElement("input");
            input.type = field.type;
            if (field.step) input.step = field.step;
        }

        input.id = `admin-${field.name}`;
        input.name = field.name;
        input.required = Boolean(field.required || (field.requiredOnCreate && !isEdit));
        if (field.defaultValue !== undefined && field.type !== "select") {
            input.value = field.defaultValue;
        }

        wrapper.appendChild(label);
        wrapper.appendChild(input);
        return wrapper;
    }

    function appendOptions(select, field) {
        select.innerHTML = "";
        const empty = document.createElement("option");
        empty.value = "";
        empty.textContent = field.required ? "Choisir" : "Aucun";
        select.appendChild(empty);

        const source = {
            users,
            stations,
            technicians,
        }[field.options] || [];

        source.forEach((item) => {
            const option = document.createElement("option");
            if (field.options === "users") {
                option.value = item.id_user;
                option.textContent = `${item.pseudo} (${item.email})`;
            } else if (field.options === "stations") {
                option.value = item.id_station;
                option.textContent = `${item.nom} - ${optionLabel(item.localisation_text)}`;
            } else if (field.options === "technicians") {
                option.value = item.id_technicien;
                option.textContent = `${item.nom} (${item.email})`;
            }
            select.appendChild(option);
        });
    }

    function renderForm() {
        fieldsHost.innerHTML = "";
        config.fields.forEach((field) => {
            const element = createField(field);
            if (element) fieldsHost.appendChild(element);
        });
    }

    function setFormValues(item) {
        config.fields.forEach((field) => {
            const control = form.elements[field.name];
            if (!control) return;

            let value = item[field.name];
            if (field.name === "date_planifiee" || field.name === "date_realisee") {
                value = toLocalInputValue(value);
            }

            if (field.type === "checkbox") {
                control.checked = Boolean(value);
            } else {
                control.value = value ?? field.defaultValue ?? "";
            }
        });
    }

    function collectPayload() {
        const payload = {};
        config.fields.forEach((field) => {
            const control = form.elements[field.name];
            if (!control || (field.createOnly && isEdit)) return;

            if (field.type === "checkbox") {
                payload[field.name] = control.checked;
            } else if (field.type === "number") {
                payload[field.name] = control.value === "" ? null : Number(control.value);
            } else if (field.type === "datetime-local") {
                payload[field.name] = fromLocalInputValue(control.value);
            } else {
                payload[field.name] = control.value.trim();
            }
        });

        if (resource === "technician" && !payload.utilisateur) {
            payload.utilisateur = null;
        }
        if (resource === "maintenance" && !payload.date_realisee) {
            payload.date_realisee = null;
        }

        return payload;
    }

    async function loadOptionData() {
        const needsUsers = config.fields.some((field) => field.options === "users");
        const needsStations = config.fields.some((field) => field.options === "stations");
        const needsTechnicians = config.fields.some((field) => field.options === "technicians");

        const tasks = [];
        if (needsUsers) tasks.push(window.AuthAPI.getAdminUsers().then((result) => { users = result.results || []; }));
        if (needsStations) tasks.push(window.AuthAPI.getAdminStations().then((result) => { stations = result.results || []; }));
        if (needsTechnicians) tasks.push(window.AuthAPI.getAdminTechnicians().then((result) => { technicians = result.results || []; }));
        await Promise.all(tasks);
    }

    async function loadCurrentItem() {
        if (!isEdit) return;
        const result = await config.list();
        currentItem = (result.results || []).find((item) => String(item[config.idKey]) === String(itemId));
        if (!currentItem) {
            throw new Error("Enregistrement introuvable.");
        }
    }

    if (!config) {
        title.textContent = "Ressource inconnue";
        setStatus("Le type de donn\u00e9e demand\u00e9 n'existe pas.", true);
        submitButton.disabled = true;
        return;
    }

    backLink.href = returnUrl();
    cancelLink.href = returnUrl();
    title.textContent = `${isEdit ? "Modifier" : "Ajouter"} un ${config.singular}`;
    lead.textContent = isEdit
        ? `Mettez \u00e0 jour les informations de cet ${config.singular}.`
        : `Renseignez les informations du nouvel ${config.singular}.`;
    submitButton.textContent = isEdit ? "Enregistrer les modifications" : `Ajouter le ${config.singular}`;
    logoutButton.addEventListener("click", () => window.AuthAPI.logout());

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
        if (!dashboard.user?.is_staff) {
            setStatus("Acc\u00e8s refus\u00e9.", true);
            window.setTimeout(() => {
                window.location.href = "/dashboard.html";
            }, 1200);
            return;
        }

        await loadOptionData();
        renderForm();
        await loadCurrentItem();
        await loadAuthMethods();
        if (currentItem) setFormValues(currentItem);
        renderPasswordResetPanel();
        renderAuthMethodsPanel();
        setStatus(isEdit ? "Formulaire charg\u00e9." : "Formulaire pr\u00eat.");
    } catch (error) {
        setStatus(error.message || "Impossible de charger le formulaire.", true);
        submitButton.disabled = true;
        return;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        setStatus("");
        submitButton.disabled = true;

        const payload = collectPayload();
        if (resource === "user" && !isEdit && !payload.password) {
            setStatus("Le mot de passe est obligatoire pour cr\u00e9er un utilisateur.", true);
            submitButton.disabled = false;
            return;
        }

        try {
            if (isEdit) {
                await config.update(itemId, payload);
                setStatus("Modification enregistr\u00e9e.");
            } else {
                await config.create(payload);
                setStatus("Enregistrement cr\u00e9\u00e9.");
            }
            window.setTimeout(() => {
                window.location.href = returnUrl();
            }, 500);
        } catch (error) {
            setStatus(error.message || "Enregistrement impossible.", true);
            submitButton.disabled = false;
        }
    });
});
