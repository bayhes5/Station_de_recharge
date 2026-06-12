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
    link.dataset.navId = item.id;
    link.href = item.href;
    link.textContent = item.label;
    if (item.id === activeId) {
        link.setAttribute("aria-current", "page");
    }
    return link;
}

function mobileLabel(item) {
    const labels = {
        admin: "Admin",
        dashboard: "Accueil",
        profile: "Profil",
        reservation: "Réserver",
        technician: "Tech",
    };
    return labels[item.id] || item.label;
}

function createMobileLink(item, activeId) {
    const link = document.createElement("a");
    link.className = "mobile-nav-link";
    link.dataset.navId = item.id;
    link.href = item.href;
    link.textContent = mobileLabel(item);
    if (item.id === activeId) {
        link.classList.add("is-active");
        link.setAttribute("aria-current", "page");
    }
    return link;
}

function renderMobileNavigation(entries, activeId) {
    const visibleEntries = entries
        .filter((entry) => ["admin", "technician", "dashboard", "reservation", "profile"].includes(entry.id))
        .slice(0, 4);
    if (!visibleEntries.length) return;

    let mobileNav = document.querySelector("[data-mobile-app-nav]");
    if (!mobileNav) {
        mobileNav = document.createElement("nav");
        mobileNav.className = "mobile-app-nav";
        mobileNav.dataset.mobileAppNav = "true";
        mobileNav.setAttribute("aria-label", "Navigation mobile");
        document.body.appendChild(mobileNav);
    }

    mobileNav.replaceChildren();
    visibleEntries.forEach((entry) => mobileNav.appendChild(createMobileLink(entry, activeId)));
    document.body.classList.add("has-mobile-nav");
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
        button.dataset.navAction = "logout";
        button.type = "button";
        button.textContent = "Se déconnecter";
        button.addEventListener("click", () => window.AuthAPI.logout());
        nav.appendChild(button);
    }

    renderMobileNavigation(entries, active);
}

window.AppNavigation = {
    render: renderAppNavigation,
};
