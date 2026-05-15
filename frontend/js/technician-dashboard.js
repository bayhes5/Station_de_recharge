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
        details.textContent = `${maintenance.status} | ${new Date(maintenance.date_planifiee).toLocaleString("fr-FR")}`;

        const description = document.createElement("p");
        description.textContent = maintenance.description || "";

        item.appendChild(title);
        item.appendChild(details);
        item.appendChild(description);
        container.appendChild(item);
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    const AUTO_REFRESH_MS = 30000;
    const status = document.getElementById("tech-status");
    const logoutBtn = document.getElementById("logout-tech");
    const list = document.getElementById("maintenances-list");
    let isLoading = false;

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

    async function loadMaintenances() {
        if (isLoading) return;
        isLoading = true;

        try {
            const result = await window.AuthAPI.getTechnicianMaintenances();
            renderMaintenances(list, result.results || []);
            status.classList.remove("error");
            status.textContent = "";
        } finally {
            isLoading = false;
        }
    }

    try {
        await loadMaintenances();
        window.setInterval(async () => {
            try {
                await loadMaintenances();
            } catch (_error) {
                status.classList.add("error");
                status.textContent = "Impossible de rafraîchir les maintenances.";
            }
        }, AUTO_REFRESH_MS);
    } catch (error) {
        status.classList.add("error");
        status.textContent = error.message || "Impossible de charger les maintenances.";
    }
});
