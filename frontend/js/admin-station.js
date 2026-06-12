function formatValue(value) {
    return value === null || value === undefined || value === "" ? "-" : value;
}

function createTextElement(tag, text, className = "") {
    const element = document.createElement(tag);
    if (className) {
        element.className = className;
    }
    element.textContent = text;
    return element;
}

function createStatusBadge(label, variant = "") {
    const badge = document.createElement("span");
    badge.className = `badge status-badge${variant ? ` ${variant}` : ""}`;
    badge.textContent = label;
    return badge;
}

function formatStationStatus(status) {
    const labels = {
        active: "Déclarée active",
        maintenance: "Maintenance",
        inactive: "Déclarée inactive",
    };
    return labels[status] || formatValue(status);
}

function formatEmplacementStatus(status) {
    const labels = {
        disponible: "Déclaré disponible",
        reserve: "Réservé",
        occupe: "Occupé",
        maintenance: "Maintenance",
    };
    return labels[status] || formatValue(status);
}

function formatLockState(lockState) {
    const labels = {
        verrouille: "Verrouillée",
        deverrouille: "Déverrouillée",
        bloque: "Bloquée",
    };
    return labels[lockState] || formatValue(lockState);
}

function createActionLink(label, href, variant = "") {
    const link = document.createElement("a");
    link.className = `table-action${variant ? ` ${variant}` : ""}`;
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

document.addEventListener("DOMContentLoaded", async () => {
    const params = new URLSearchParams(window.location.search);
    const stationId = params.get("id");
    const title = document.getElementById("station-title");
    const lead = document.getElementById("station-lead");
    const status = document.getElementById("station-status");
    const logoutButton = document.getElementById("logout-admin-station");
    const editStationLink = document.getElementById("station-edit-link");
    const deleteStationButton = document.getElementById("station-delete");
    const addBorneLink = document.getElementById("station-add-borne");
    const bornesList = document.getElementById("station-bornes-list");

    let station = null;
    let bornes = [];
    let emplacements = [];

    function setStatus(message, isError = false) {
        status.classList.toggle("error", isError);
        status.classList.toggle("success", Boolean(message) && !isError);
        status.textContent = message;
    }

    function returnPath() {
        return `/admin-station.html?id=${encodeURIComponent(stationId)}`;
    }

    function formHref(resource, id = "", extra = {}) {
        const formParams = new URLSearchParams({ resource, return: returnPath(), ...extra });
        if (id) {
            formParams.set("id", id);
        }
        return `/admin-form.html?${formParams.toString()}`;
    }

    function renderStationSummary() {
        title.textContent = station.nom;
        lead.textContent = station.localisation_text || "Bornes, emplacements et état opérationnel de la station.";
        document.getElementById("station-statut").textContent = formatStationStatus(station.statut);
        document.getElementById("station-bornes-count").textContent = bornes.length;
        document.getElementById("station-emplacements-count").textContent = emplacements.length;
        document.getElementById("station-location").textContent = formatValue(station.localisation_text);
        document.getElementById("station-coordinates").textContent = `${formatValue(station.latitude)} / ${formatValue(station.longitude)}`;
        editStationLink.href = formHref("station", station.id_station);
        addBorneLink.href = formHref("borne", "", { station: station.id_station });
    }

    function emplacementsForBorne(borne) {
        return emplacements
            .filter((emplacement) => String(emplacement.borne) === String(borne.id_borne))
            .sort((left, right) => Number(left.numero) - Number(right.numero));
    }

    function renderEmplacement(emplacement) {
        const row = document.createElement("article");
        row.className = "list-item compact-list-item station-slot-row";

        const head = document.createElement("div");
        head.className = "list-item-head";
        head.appendChild(createTextElement("strong", `Emplacement ${emplacement.numero}`));
        head.appendChild(createStatusBadge(
            formatEmplacementStatus(emplacement.statut),
            emplacement.statut === "maintenance" ? "warning" : "",
        ));

        const lock = createTextElement("p", `Serrure : ${formatLockState(emplacement.lock_state)}`);

        const actions = document.createElement("div");
        actions.className = "table-actions";
        actions.appendChild(createActionLink("Modifier", formHref("emplacement", emplacement.id_emplacement)));
        actions.appendChild(createActionButton("Supprimer", () => deleteEmplacement(emplacement), "danger-action"));

        row.appendChild(head);
        row.appendChild(lock);
        row.appendChild(actions);
        return row;
    }

    function renderBornes() {
        bornesList.innerHTML = "";

        if (!bornes.length) {
            const empty = document.createElement("div");
            empty.className = "empty-state";
            empty.textContent = "Aucune borne n'est rattachée à cette station.";
            bornesList.appendChild(empty);
            return;
        }

        bornes.forEach((borne) => {
            const card = document.createElement("article");
            card.className = "slot-card station-borne-card";

            const head = document.createElement("div");
            head.className = "slot-card-head";
            head.appendChild(createTextElement("strong", borne.nom || `Borne ${borne.numero}`));
            head.appendChild(createStatusBadge(formatStationStatus(borne.statut), borne.statut === "maintenance" ? "warning" : ""));

            const meta = document.createElement("dl");
            meta.className = "station-borne-meta";
            [
                ["Numéro", borne.numero],
                ["Emplacements", emplacementsForBorne(borne).length],
                ["Identifiant de communication", borne.mqtt_prefix || "-"],
            ].forEach(([label, value]) => {
                const group = document.createElement("div");
                group.appendChild(createTextElement("dt", label));
                group.appendChild(createTextElement("dd", formatValue(value)));
                meta.appendChild(group);
            });

            const actions = document.createElement("div");
            actions.className = "table-actions station-card-actions";
            actions.appendChild(createActionLink("Modifier", formHref("borne", borne.id_borne)));
            actions.appendChild(createActionLink("Ajouter un emplacement", formHref("emplacement", "", { borne: borne.id_borne })));
            actions.appendChild(createActionButton("Supprimer", () => deleteBorne(borne), "danger-action"));

            const slots = document.createElement("div");
            slots.className = "stacked-list station-slot-list";
            const borneSlots = emplacementsForBorne(borne);
            if (!borneSlots.length) {
                slots.appendChild(createTextElement("p", "Aucun emplacement rattaché à cette borne.", "helper"));
            } else {
                borneSlots.forEach((emplacement) => slots.appendChild(renderEmplacement(emplacement)));
            }

            card.appendChild(head);
            card.appendChild(meta);
            card.appendChild(actions);
            card.appendChild(slots);
            bornesList.appendChild(card);
        });
    }

    async function loadStation() {
        const [stationResult, bornesResult, emplacementsResult] = await Promise.all([
            window.AuthAPI.getAdminStation(stationId),
            window.AuthAPI.getAdminBornes({ station: stationId }),
            window.AuthAPI.getAdminEmplacements({ station: stationId }),
        ]);
        station = stationResult;
        bornes = (bornesResult.results || []).sort((left, right) => Number(left.numero) - Number(right.numero));
        emplacements = (emplacementsResult.results || []).sort(
            (left, right) => Number(left.borne_numero ?? 0) - Number(right.borne_numero ?? 0) || Number(left.numero) - Number(right.numero)
        );
        renderStationSummary();
        renderBornes();
    }

    async function deleteStation() {
        const confirmed = await window.AuthAPI.confirmAction(
            `Supprimer la station ${station.nom} ?`,
            { title: "Supprimer la station", confirmLabel: "Supprimer", danger: true },
        );
        if (!confirmed) return;

        deleteStationButton.disabled = true;
        try {
            await window.AuthAPI.deleteAdminStation(station.id_station);
            window.location.href = "/admin-dashboard.html#infrastructure";
        } catch (error) {
            setStatus(error.message || "Suppression impossible.", true);
            deleteStationButton.disabled = false;
        }
    }

    async function deleteBorne(borne) {
        const confirmed = await window.AuthAPI.confirmAction(
            `Supprimer la borne ${borne.nom || borne.numero} ?`,
            { title: "Supprimer la borne", confirmLabel: "Supprimer", danger: true },
        );
        if (!confirmed) return;

        try {
            await window.AuthAPI.deleteAdminBorne(borne.id_borne);
            await loadStation();
            setStatus("Borne supprimée.");
        } catch (error) {
            setStatus(error.message || "Suppression impossible.", true);
        }
    }

    async function deleteEmplacement(emplacement) {
        const confirmed = await window.AuthAPI.confirmAction(
            `Supprimer l'emplacement ${emplacement.numero} ?`,
            { title: "Supprimer l'emplacement", confirmLabel: "Supprimer", danger: true },
        );
        if (!confirmed) return;

        try {
            await window.AuthAPI.deleteAdminEmplacement(emplacement.id_emplacement);
            await loadStation();
            setStatus("Emplacement supprimé.");
        } catch (error) {
            setStatus(error.message || "Suppression impossible.", true);
        }
    }

    logoutButton.addEventListener("click", () => window.AuthAPI.logout());

    if (!stationId) {
        setStatus("Station introuvable.", true);
        return;
    }

    if (!await window.AuthAPI.ensureSession()) {
        setStatus("Session absente ou expirée. Redirection vers la connexion.", true);
        window.setTimeout(() => { window.location.href = "/login.html"; }, 1200);
        return;
    }

    try {
        const dashboard = await window.AuthAPI.getDashboard();
        if (!dashboard.user?.is_staff) {
            setStatus("Accès refusé.", true);
            window.setTimeout(() => { window.location.href = "/dashboard.html"; }, 1200);
            return;
        }

        window.AppNavigation.render(dashboard, { active: "infrastructure", preferredRole: "admin" });

        await loadStation();
        deleteStationButton.addEventListener("click", deleteStation);
        setStatus("");
    } catch (error) {
        setStatus(error.message || "Impossible de charger la station.", true);
    }
});
