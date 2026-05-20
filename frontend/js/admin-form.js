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

const USER_STATUS_OPTIONS = [
    { value: "actif", label: "Actif" },
    { value: "suspendu", label: "Suspendu" },
    { value: "archive", label: "Archivé" },
];

const STATION_STATUS_OPTIONS = [
    { value: "active", label: "Active" },
    { value: "maintenance", label: "Maintenance" },
    { value: "inactive", label: "Inactive" },
];

const EMPLACEMENT_STATUS_OPTIONS = [
    { value: "disponible", label: "Disponible" },
    { value: "reserve", label: "Réservé" },
    { value: "occupe", label: "Occupé" },
    { value: "maintenance", label: "Maintenance" },
];

const LOCK_STATE_OPTIONS = [
    { value: "verrouille", label: "Verrouillé" },
    { value: "deverrouille", label: "Déverrouillé" },
    { value: "bloque", label: "Bloqué" },
];

const MAINTENANCE_STATUS_OPTIONS = [
    { value: "planifiee", label: "Planifiée" },
    { value: "en_cours", label: "En cours" },
    { value: "realisee", label: "Réalisée" },
    { value: "annulee", label: "Annulée" },
];

function createTextElement(tagName, text, className = "") {
    const element = document.createElement(tagName);
    if (className) element.className = className;
    element.textContent = text;
    return element;
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
    let bornes = [];
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
                { name: "statut", label: "Statut", type: "select", defaultValue: "actif", options: USER_STATUS_OPTIONS },
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
                { name: "statut", label: "Statut", type: "select", defaultValue: "active", required: true, options: STATION_STATUS_OPTIONS },
            ],
        },
        borne: {
            singular: "borne",
            plural: "bornes",
            tab: "infrastructure",
            idKey: "id_borne",
            list: () => window.AuthAPI.getAdminBornes(),
            create: (payload) => window.AuthAPI.createAdminBorne(payload),
            update: (id, payload) => window.AuthAPI.updateAdminBorne(id, payload),
            fields: [
                { name: "station", label: "Station", type: "select", required: true, options: "stations" },
                { name: "numero", label: "Num\u00e9ro", type: "number", required: true },
                { name: "nom", label: "Nom", type: "text", required: true },
                { name: "mqtt_prefix", label: "Pr\u00e9fixe MQTT", type: "text" },
                { name: "statut", label: "Statut", type: "select", defaultValue: "active", required: true, options: STATION_STATUS_OPTIONS },
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
                { name: "borne", label: "Borne", type: "select", required: true, options: "bornes" },
                { name: "numero", label: "Num\u00e9ro", type: "number", required: true },
                { name: "statut", label: "Statut", type: "select", defaultValue: "disponible", required: true, options: EMPLACEMENT_STATUS_OPTIONS },
                { name: "lock_state", label: "\u00c9tat serrure", type: "select", defaultValue: "verrouille", required: true, options: LOCK_STATE_OPTIONS },
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
                {
                    name: "station_scope",
                    label: "P\u00e9rim\u00e8tre d'intervention",
                    type: "station-scope",
                    options: "stations",
                    fullWidth: true,
                    helper: "S\u00e9lectionnez uniquement les stations que ce technicien peut superviser ou traiter.",
                },
            ],
        },
        "technician-station": {
            singular: "affectation technicien-station",
            plural: "affectations technicien-station",
            tab: "operations",
            idKey: "id_assignment",
            list: () => window.AuthAPI.getAdminTechnicianStationAssignments(),
            create: (payload) => window.AuthAPI.createAdminTechnicianStationAssignment(payload),
            update: (id, payload) => window.AuthAPI.updateAdminTechnicianStationAssignment(id, payload),
            fields: [
                { name: "technicien", label: "Technicien", type: "select", required: true, options: "technicians" },
                { name: "station", label: "Station", type: "select", required: true, options: "stations" },
                {
                    name: "role",
                    label: "R\u00f4le",
                    type: "select",
                    defaultValue: "intervenant",
                    required: true,
                    options: [
                        { value: "intervenant", label: "Intervenant" },
                        { value: "referent", label: "R\u00e9f\u00e9rent" },
                        { value: "observateur", label: "Observateur" },
                    ],
                },
                { name: "is_active", label: "Affectation active", type: "checkbox", defaultValue: true },
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
                { name: "status", label: "Statut", type: "select", defaultValue: "planifiee", required: true, options: MAINTENANCE_STATUS_OPTIONS },
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

        const dialog = document.createElement("section");
        dialog.className = "modal-dialog";
        dialog.setAttribute("role", "dialog");
        dialog.setAttribute("aria-modal", "true");
        dialog.setAttribute("aria-labelledby", "reset-password-title");

        const heading = document.createElement("div");
        heading.className = "modal-heading";
        const headingText = document.createElement("div");
        headingText.appendChild(createTextElement("p", "Administration", "eyebrow"));
        const dialogTitle = createTextElement("h2", "Mot de passe temporaire");
        dialogTitle.id = "reset-password-title";
        headingText.appendChild(dialogTitle);
        const closeButton = document.createElement("button");
        closeButton.className = "modal-close";
        closeButton.type = "button";
        closeButton.setAttribute("aria-label", "Fermer");
        closeButton.textContent = "\u00d7";
        heading.appendChild(headingText);
        heading.appendChild(closeButton);

        const accountForm = document.createElement("div");
        accountForm.className = "account-form";
        const userLine = createTextElement("p", "", "helper");
        userLine.id = "reset-password-user";
        accountForm.appendChild(userLine);
        accountForm.appendChild(
            createTextElement(
                "p",
                "Copiez ce mot de passe maintenant. Il ne sera plus affiché après fermeture.",
                "helper",
            )
        );
        const passwordBox = document.createElement("div");
        passwordBox.className = "generated-password-box";
        const passwordCode = document.createElement("code");
        passwordCode.id = "generated-password-value";
        passwordBox.appendChild(passwordCode);
        accountForm.appendChild(passwordBox);
        const dialogStatus = createTextElement("p", "", "field-feedback");
        dialogStatus.id = "reset-password-status";
        dialogStatus.setAttribute("aria-live", "polite");
        accountForm.appendChild(dialogStatus);

        const actions = document.createElement("div");
        actions.className = "cta-row";
        const copyButton = createTextElement("button", "Copier", "btn btn-primary");
        copyButton.type = "button";
        copyButton.dataset.copyPassword = "";
        const cancelButton = createTextElement("button", "Fermer", "btn btn-secondary");
        cancelButton.type = "button";
        cancelButton.dataset.resetCancel = "";
        actions.appendChild(copyButton);
        actions.appendChild(cancelButton);
        accountForm.appendChild(actions);

        dialog.appendChild(heading);
        dialog.appendChild(accountForm);
        backdrop.appendChild(dialog);

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

        const heading = document.createElement("div");
        heading.className = "panel-heading admin-password-heading";
        const headingText = document.createElement("div");
        const titleElement = createTextElement("p", "Mot de passe", "panel-title");
        titleElement.id = "admin-password-title";
        headingText.appendChild(titleElement);
        headingText.appendChild(
            createTextElement("p", "Générez un mot de passe temporaire pour ce compte utilisateur.", "helper")
        );
        const resetButton = createTextElement("button", "Réinitialiser le mot de passe", "btn btn-secondary");
        resetButton.id = "admin-reset-password";
        resetButton.type = "button";
        heading.appendChild(headingText);
        heading.appendChild(resetButton);
        panel.appendChild(heading);

        resetButton.addEventListener("click", (event) => {
            resetCurrentUserPassword(event.currentTarget);
        });
        form.closest(".admin-edit-panel").after(panel);
    }

    function renderAuthMethodsPanel() {
        if (resource !== "user" || !isEdit) return;

        const panel = document.createElement("section");
        panel.className = "dashboard-panel admin-access-panel";
        panel.setAttribute("aria-labelledby", "admin-access-title");

        const heading = document.createElement("div");
        heading.className = "panel-heading admin-access-heading";
        const headingText = document.createElement("div");
        const titleElement = createTextElement("p", "Moyens d'accès", "panel-title");
        titleElement.id = "admin-access-title";
        headingText.appendChild(titleElement);
        headingText.appendChild(
            createTextElement(
                "p",
                "Gérez les badges RFID sans afficher leur valeur complète. Les QR codes et codes temporaires se gèrent depuis les réservations.",
                "helper",
            )
        );
        heading.appendChild(headingText);
        panel.appendChild(heading);

        const rfidForm = document.createElement("form");
        rfidForm.id = "admin-rfid-form";
        rfidForm.className = "admin-inline-form";
        const field = document.createElement("div");
        field.className = "field";
        const label = createTextElement("label", "Nouveau badge RFID");
        label.setAttribute("for", "admin-rfid-value");
        const input = document.createElement("input");
        input.id = "admin-rfid-value";
        input.name = "auth_value";
        input.type = "text";
        input.placeholder = "Valeur du badge";
        input.autocomplete = "off";
        input.required = true;
        field.appendChild(label);
        field.appendChild(input);
        rfidForm.appendChild(field);
        const submit = createTextElement("button", "Associer / remplacer", "btn btn-secondary");
        submit.type = "submit";
        rfidForm.appendChild(submit);
        panel.appendChild(rfidForm);

        const list = document.createElement("div");
        list.id = "admin-auth-methods-list";
        list.className = "stacked-list";
        panel.appendChild(list);

        const anchor = document.querySelector(".admin-password-panel") || form.closest(".admin-edit-panel");
        anchor.after(panel);
        rfidForm.addEventListener("submit", handleRfidSubmit);
        renderAuthMethodsList(list);
    }

    function renderAuthMethodsList(container = document.getElementById("admin-auth-methods-list")) {
        if (!container) return;
        container.innerHTML = "";

        if (!authMethods.length) {
            const empty = document.createElement("div");
            empty.className = "empty-state";
            empty.textContent = "Aucun badge RFID actif. Les QR codes et codes temporaires apparaissent dans l'administration des réservations.";
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
            revokeButton.textContent = "Révoquer";
            revokeButton.addEventListener("click", () => revokeAuthMethod(method, revokeButton));
            actions.appendChild(revokeButton);

            item.appendChild(head);
            item.appendChild(meta);
            item.appendChild(actions);
            container.appendChild(item);
        });

        const temporaryAccessNote = document.createElement("p");
        temporaryAccessNote.className = "helper";
        temporaryAccessNote.textContent = "Les QR codes et codes temporaires de cet utilisateur restent visibles et gérables dans l'administration des réservations.";
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
        const confirmed = await window.AuthAPI.confirmAction(
            `Révoquer ce badge RFID pour ${currentItem.pseudo} ?`,
            {
                title: "Révoquer le badge RFID",
                confirmLabel: "Révoquer",
                danger: true,
            }
        );
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

        const confirmed = await window.AuthAPI.confirmAction(
            `G\u00e9n\u00e9rer un nouveau mot de passe temporaire pour ${currentItem.pseudo} ?`,
            {
                title: "Reinitialiser le mot de passe",
                confirmLabel: "Generer",
            }
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

        if (field.type === "station-scope") {
            return createStationScopeField(field);
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
        if (field.defaultValue !== undefined) {
            input.value = field.defaultValue;
        }

        wrapper.appendChild(label);
        wrapper.appendChild(input);
        return wrapper;
    }

    function createStationScopeField(field) {
        const wrapper = document.createElement("fieldset");
        wrapper.className = "field admin-field-wide station-scope-field";

        const legend = document.createElement("legend");
        legend.textContent = field.label;
        wrapper.appendChild(legend);

        if (field.helper) {
            wrapper.appendChild(createTextElement("p", field.helper, "helper"));
        }

        const list = document.createElement("div");
        list.className = "station-scope-list";

        if (!stations.length) {
            const empty = createTextElement("p", "Aucune station disponible.", "empty-state");
            wrapper.appendChild(empty);
            return wrapper;
        }

        stations.forEach((station) => {
            const option = document.createElement("label");
            option.className = "station-scope-option";

            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.name = field.name;
            checkbox.value = station.id_station;

            const text = document.createElement("span");
            const title = createTextElement("strong", station.nom || "Station");
            const location = createTextElement("small", optionLabel(station.localisation_text));
            text.appendChild(title);
            text.appendChild(location);

            option.appendChild(checkbox);
            option.appendChild(text);
            list.appendChild(option);
        });

        wrapper.appendChild(list);
        return wrapper;
    }

    function appendOptions(select, field) {
        select.innerHTML = "";
        const empty = document.createElement("option");
        empty.value = "";
        empty.textContent = field.required ? "Choisir" : "Aucun";
        select.appendChild(empty);

        const source = Array.isArray(field.options) ? field.options : {
            users,
            stations,
            bornes,
            technicians,
        }[field.options] || [];

        source.forEach((item) => {
            const option = document.createElement("option");
            if (Array.isArray(field.options)) {
                option.value = item.value;
                option.textContent = item.label;
            } else if (field.options === "users") {
                option.value = item.id_user;
                option.textContent = `${item.pseudo} (${item.email})`;
            } else if (field.options === "stations") {
                option.value = item.id_station;
                option.textContent = `${item.nom} - ${optionLabel(item.localisation_text)}`;
            } else if (field.options === "bornes") {
                option.value = item.id_borne;
                option.textContent = `${item.station_nom || "Station"} - ${item.nom || `Borne ${item.numero}`}`;
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
            if (field.type === "station-scope") {
                const selectedStations = new Set(
                    (item.assigned_stations || []).map((assignment) => String(assignment.station))
                );
                form.querySelectorAll(`input[name="${field.name}"]`).forEach((control) => {
                    control.checked = selectedStations.has(String(control.value));
                });
                return;
            }

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
            if (field.type === "station-scope") {
                payload[field.name] = Array.from(
                    form.querySelectorAll(`input[name="${field.name}"]:checked`)
                ).map((control) => control.value);
                return;
            }

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
        const needsBornes = config.fields.some((field) => field.options === "bornes");
        const needsTechnicians = config.fields.some((field) => field.options === "technicians");

        const tasks = [];
        if (needsUsers) tasks.push(window.AuthAPI.getAdminUsers().then((result) => { users = result.results || []; }));
        if (needsStations) tasks.push(window.AuthAPI.getAdminStations().then((result) => { stations = result.results || []; }));
        if (needsBornes) tasks.push(window.AuthAPI.getAdminBornes().then((result) => { bornes = result.results || []; }));
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
        setStatus("");
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
