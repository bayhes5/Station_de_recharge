function downloadJson(filename, data) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
}

function formatDate(value) {
    if (!value) {
        return "-";
    }
    return new Date(value).toLocaleString("fr-FR");
}

function renderAuthMethods(listElement, methods, onDelete) {
    listElement.innerHTML = "";

    if (!methods.length) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = "Aucun badge RFID configuré.";
        listElement.appendChild(empty);
        return;
    }

    methods.forEach((method) => {
        const item = document.createElement("article");
        item.className = "list-item";

        const head = document.createElement("div");
        head.className = "list-item-head";

        const title = document.createElement("strong");
        title.textContent = method.type_label === "RFID" ? "Badge RFID" : method.type_label;

        const badge = document.createElement("span");
        badge.className = "badge";
        badge.textContent = "Enregistré";

        head.appendChild(title);
        head.appendChild(badge);

        const value = document.createElement("p");
        value.textContent = method.display_value
            ? `Badge : ${method.display_value}`
            : "Badge enregistré";

        const meta = document.createElement("p");
        meta.textContent = "Utilisé automatiquement lors d’une réservation avec badge RFID.";

        const actions = document.createElement("div");
        actions.className = "cta-row";

        const deleteButton = document.createElement("button");
        deleteButton.className = "btn btn-secondary";
        deleteButton.type = "button";
        deleteButton.textContent = "Supprimer";
        deleteButton.addEventListener("click", () => onDelete(method));

        actions.appendChild(deleteButton);

        item.appendChild(head);
        item.appendChild(value);
        item.appendChild(meta);
        item.appendChild(actions);
        listElement.appendChild(item);
    });
}

function renderAuthHistory(listElement, history) {
    listElement.innerHTML = "";

    if (!history.length) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = "Aucun accès de réservation pour le moment.";
        listElement.appendChild(empty);
        return;
    }

    history.forEach((entry) => {
        const item = document.createElement("article");
        item.className = "list-item";

        const head = document.createElement("div");
        head.className = "list-item-head";

        const title = document.createElement("strong");
        title.textContent = `${entry.auth_type} - ${entry.station_nom} / emplacement ${entry.emplacement}`;

        const badge = document.createElement("span");
        badge.className = "badge";
        badge.textContent = entry.auth_source === "generated" ? "Créé pour la réservation" : "Enregistré";

        head.appendChild(title);
        head.appendChild(badge);

        const ref = document.createElement("p");
        ref.textContent = `Réservation : ${entry.reference_code || "-"} | ${formatDate(entry.date_debut)} - ${formatDate(entry.date_fin)}`;

        const value = document.createElement("p");
        value.textContent = entry.auth_value
            ? `Référence d'accès : ${entry.auth_value}`
            : "Accès non affichable";

        const meta = document.createElement("p");
        meta.textContent = entry.auth_expiration
            ? `Expire le ${formatDate(entry.auth_expiration)}`
            : "Sans expiration";

        item.appendChild(head);
        item.appendChild(ref);
        item.appendChild(value);
        item.appendChild(meta);
        listElement.appendChild(item);
    });
}

function formatConsentStatus(status) {
    const labels = {
        accepte: "Accepté",
        refuse: "Refusé",
        retire: "Retiré",
        non_renseigne: "Non renseigné",
    };
    return labels[status] || status;
}

function formatConsentDate(value) {
    if (!value) {
        return "Aucune date enregistrée";
    }

    return new Intl.DateTimeFormat("fr-FR", {
        dateStyle: "medium",
        timeStyle: "short",
    }).format(new Date(value));
}

function renderConsents(listElement, consents) {
    listElement.innerHTML = "";

    consents.forEach((consent) => {
        const item = document.createElement("article");
        item.className = "list-item";

        const head = document.createElement("div");
        head.className = "list-item-head";

        const title = document.createElement("strong");
        title.textContent = consent.label;

        const badge = document.createElement("span");
        badge.className = "badge";
        badge.textContent = formatConsentStatus(consent.statut);

        const meta = document.createElement("p");
        meta.textContent = consent.required
            ? "Consentement requis pour le service."
            : "Préférence optionnelle modifiable.";

        const date = document.createElement("p");
        date.textContent = formatConsentDate(consent.date_consentement);

        head.appendChild(title);
        head.appendChild(badge);
        item.appendChild(head);
        item.appendChild(meta);
        item.appendChild(date);
        listElement.appendChild(item);
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    const status = document.getElementById("profile-status");
    const logoutBtn = document.getElementById("logout-btn");
    const exportBtn = document.getElementById("export-btn");
    const deleteBtn = document.getElementById("delete-btn");
    const profileForm = document.getElementById("profile-form");
    const passwordForm = document.getElementById("password-form");
    const authMethodForm = document.getElementById("auth-method-form");
    const authMethodsList = document.getElementById("auth-methods-list");
    const rfidLinkCode = document.getElementById("rfid-link-code");
    const authHistoryList = document.getElementById("auth-history-list");
    const authHistoryPreview = document.getElementById("auth-history-preview");
    const consentForm = document.getElementById("consent-form");
    const consentSummary = document.getElementById("consent-summary");
    const adminLink = document.getElementById("profile-admin-link");
    const tabButtons = [...document.querySelectorAll("[data-tab-button]")];
    const tabPanels = [...document.querySelectorAll("[data-tab-panel]")];
    const forcePasswordChange = new URLSearchParams(window.location.search).has("force_password_change");

    let currentProfile = null;

    function setStatus(message, isError = false) {
        status.classList.toggle("error", isError);
        status.textContent = message;
    }

    function setTab(name) {
        tabButtons.forEach((button) => {
            button.classList.toggle("active", button.dataset.tabButton === name);
            button.setAttribute("aria-selected", String(button.dataset.tabButton === name));
        });

        tabPanels.forEach((panel) => {
            panel.hidden = panel.dataset.tabPanel !== name;
        });
    }

    async function deleteRfidBadge(method) {
        const confirmed = await window.AuthAPI.confirmAction(
            "Supprimer ce badge RFID ?",
            {
                title: "Supprimer le badge RFID",
                confirmLabel: "Supprimer",
                danger: true,
            }
        );
        if (!confirmed) return;

        try {
            await window.AuthAPI.deleteAuthMethod(method.id_auth);
            await loadAuthMethods();
            setStatus("Badge RFID supprimé.");
        } catch (error) {
            setStatus(error.message || "Impossible de supprimer le badge RFID.", true);
        }
    }

    async function loadProfile() {
        const result = await window.AuthAPI.getProfile();
        currentProfile = result;
        const user = result.user;
        const profile = result.profile || {};
        if (adminLink) {
            adminLink.hidden = !user.is_staff;
        }

        profileForm.pseudo.value = user.pseudo || "";
        profileForm.email.value = user.email || "";
        profileForm.telephone.value = user.telephone || "";
        profileForm.nom.value = profile.nom || user.nom || "";
        profileForm.statut.value = user.statut || "";

        setStatus("");
    }

    async function loadAuthMethods() {
        const result = await window.AuthAPI.getAuthMethods();
        renderAuthMethods(authMethodsList, result.results || [], deleteRfidBadge);
    }

    async function loadAuthHistory() {
        const result = await window.AuthAPI.getAuthHistory();
        const history = result.results || [];
        renderAuthHistory(authHistoryList, history);

        const preview = history
            .filter((entry) => entry.auth_source === "generated")
            .slice(0, 3);
        renderAuthHistory(authHistoryPreview, preview);
    }

    async function loadConsents() {
        const result = await window.AuthAPI.getConsents();
        const consents = result.current || [];
        const notifications = consents.find((consent) => consent.type === "notifications");

        renderConsents(consentSummary, consents);
        consentForm.notificationsAccepted.checked = notifications?.statut === "accepte";
    }

    tabButtons.forEach((button) => {
        button.addEventListener("click", () => setTab(button.dataset.tabButton));
    });

    logoutBtn.addEventListener("click", () => window.AuthAPI.logout());

    const session = await window.AuthAPI.ensureSession();
    if (!session) {
        setStatus("Session absente ou expirée. Redirection vers la connexion.", true);
        window.setTimeout(() => {
            window.location.href = "/login.html";
        }, 1200);
        return;
    }

    window.AppNavigation.render(session, { active: "profile" });

    try {
        await Promise.all([loadProfile(), loadAuthMethods(), loadAuthHistory(), loadConsents()]);
        setTab("account");
        if (forcePasswordChange || currentProfile?.user?.must_change_password) {
            setStatus("Vous utilisez un mot de passe provisoire. Choisissez un nouveau mot de passe pour continuer.");
            passwordForm.current_password.focus();
        }
    } catch (_error) {
        setStatus("Impossible de charger le profil ou l’historique d’authentification.", true);
        return;
    }

    authMethodForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        setStatus("");
        const submitButton = authMethodForm.querySelector('button[type="submit"]');
        submitButton.disabled = true;

        try {
            const result = await window.AuthAPI.createRfidLinkCode();
            if (rfidLinkCode) {
                rfidLinkCode.hidden = false;
                rfidLinkCode.textContent = `Code association : ${result.code} - valable ${window.AuthAPI.formatDuration(result.expires_in)}. Saisissez ce code sur la borne, puis présentez votre badge.`;
            }
            setStatus("Code d'association RFID généré.");
        } catch (error) {
            setStatus(error.message || "Impossible de générer le code d'association RFID.", true);
        } finally {
            submitButton.disabled = false;
        }
    });

    profileForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        setStatus("");

        const submitButton = profileForm.querySelector('button[type="submit"]');
        submitButton.disabled = true;

        const payload = {
            pseudo: profileForm.pseudo.value.trim(),
            email: profileForm.email.value.trim(),
            telephone: profileForm.telephone.value.trim(),
            nom: profileForm.nom.value.trim(),
        };

        try {
            await window.AuthAPI.updateProfile(payload);
            await loadProfile();
            setStatus("Profil mis à jour.");
        } catch (error) {
            if (error.payload?.email) {
                setStatus(`E-mail : ${error.payload.email.join(" ")}`, true);
            } else if (error.payload?.pseudo) {
                setStatus(`Pseudo : ${error.payload.pseudo.join(" ")}`, true);
            } else {
                setStatus(error.message || "Erreur lors de la mise à jour du profil.", true);
            }
        } finally {
            submitButton.disabled = false;
        }
    });

    passwordForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        setStatus("");

        const submitButton = passwordForm.querySelector('button[type="submit"]');
        submitButton.disabled = true;

        const payload = {
            current_password: passwordForm.current_password.value,
            new_password: passwordForm.new_password.value,
            confirm_password: passwordForm.confirm_password.value,
        };

        if (payload.new_password !== payload.confirm_password) {
            setStatus("Les mots de passe ne correspondent pas.", true);
            submitButton.disabled = false;
            return;
        }

        try {
            await window.AuthAPI.changePassword(payload);
            passwordForm.reset();
            currentProfile = await window.AuthAPI.getProfile();
            setStatus("Mot de passe mis à jour.");
        } catch (error) {
            if (error.payload?.current_password) {
                setStatus(error.payload.current_password, true);
            } else if (error.payload?.new_password) {
                setStatus(`Nouveau mot de passe : ${error.payload.new_password.join(" ")}`, true);
            } else {
                setStatus(error.message || "Erreur lors du changement de mot de passe.", true);
            }
        } finally {
            submitButton.disabled = false;
        }
    });

    consentForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        setStatus("");

        const submitButton = consentForm.querySelector('button[type="submit"]');
        submitButton.disabled = true;

        try {
            await window.AuthAPI.updateConsents({
                notifications_accepted: consentForm.notificationsAccepted.checked,
            });
            await loadConsents();
            setStatus("Préférences de consentement mises à jour.");
        } catch (error) {
            setStatus(error.message || "Impossible de mettre à jour les consentements.", true);
        } finally {
            submitButton.disabled = false;
        }
    });

    exportBtn.addEventListener("click", async () => {
        try {
            const account = await window.AuthAPI.exportAccount();
            downloadJson(`compte-${currentProfile.user.pseudo || "utilisateur"}.json`, account);
            setStatus("Export RGPD téléchargé.");
        } catch (_error) {
            setStatus("Impossible de télécharger vos données.", true);
        }
    });

    deleteBtn.addEventListener("click", async () => {
        const confirmed = await window.AuthAPI.confirmAction(
            "Cette action supprime votre compte et les données associées. Continuer ?",
            {
                title: "Supprimer le compte",
                confirmLabel: "Supprimer mon compte",
                danger: true,
            }
        );

        if (!confirmed) {
            return;
        }

        try {
            await window.AuthAPI.deleteAccount();
            window.AuthAPI.clearTokens();
            window.location.href = "/register.html";
        } catch (_error) {
            setStatus("Impossible de supprimer le compte.", true);
        }
    });
});
