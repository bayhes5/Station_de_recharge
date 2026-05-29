const ROLE_NAVIGATION = {
    user: [
        { id: "dashboard", label: "Tableau de bord", href: "/dashboard.html" },
        { id: "reservation", label: "Réserver", href: "/reservation.html", emphasis: true },
        { id: "profile", label: "Profil", href: "/profile.html" },
    ],
    technician: [
        { id: "technician", label: "Espace technicien", href: "/technician-dashboard.html" },
        { id: "dashboard", label: "Tableau de bord", href: "/dashboard.html" },
        { id: "profile", label: "Profil", href: "/profile.html" },
    ],
    admin: [
        { id: "admin", label: "Vue globale", href: "/admin-dashboard.html" },
        { id: "dashboard", label: "Tableau de bord", href: "/dashboard.html" },
        { id: "profile", label: "Profil", href: "/profile.html" },
    ],
};

function currentRole(user = {}, preferredRole = "") {
    if (preferredRole === "admin" && user.is_staff) return "admin";
    if (preferredRole === "technician" && (user.is_technician || user.is_staff)) return "technician";
    return "user";
}

function entriesForRole(user, role) {
    if (role !== "user") {
        return ROLE_NAVIGATION[role];
    }

    const entries = [];
    if (user.is_staff) {
        entries.push({ id: "admin", label: "Administration", href: "/admin-dashboard.html" });
    }
    if (user.is_technician && !user.is_staff) {
        entries.push({ id: "technician", label: "Espace technicien", href: "/technician-dashboard.html" });
    }
    return [...entries, ...ROLE_NAVIGATION.user];
}

function navButtonClass(item, activeId) {
    const classes = ["btn"];
    classes.push(item.emphasis && item.id !== activeId ? "btn-primary" : "btn-secondary");
    if (item.id === activeId) {
        classes.push("is-active");
    }
    return classes.join(" ");
}

function createLink(item, activeId) {
    const link = document.createElement("a");
    link.className = navButtonClass(item, activeId);
    link.href = item.href;
    link.textContent = item.label;
    if (item.id === activeId) {
        link.setAttribute("aria-current", "page");
    }
    return link;
}

function renderAppNavigation(session, options = {}) {
    const {
        active = "",
        preferredRole = "",
        selector = "[data-app-nav]",
        extraLinks = [],
        logout = true,
    } = options;

    const nav = document.querySelector(selector);
    if (!nav) return;

    const user = session?.user || session || {};
    const role = currentRole(user, preferredRole);
    const entries = [...extraLinks, ...entriesForRole(user, role)];

    nav.replaceChildren();
    entries.forEach((entry) => nav.appendChild(createLink(entry, active)));

    if (logout) {
        const button = document.createElement("button");
        button.className = "btn btn-secondary";
        button.type = "button";
        button.textContent = "Se déconnecter";
        button.addEventListener("click", () => window.AuthAPI.logout());
        nav.appendChild(button);
    }
}

window.AppNavigation = {
    render: renderAppNavigation,
};
