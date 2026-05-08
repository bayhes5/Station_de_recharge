document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("register-form");
    const status = document.getElementById("register-status");
    const submitButton = document.getElementById("register-submit");

    const fields = {
        pseudo: form.pseudo,
        email: form.email,
        password: form.password,
        passwordConfirm: form.passwordConfirm,
        cgu: form.cguAccepted,
        privacy: form.privacyPolicyAccepted,
        notifications: form.notificationsAccepted,
    };

    const feedback = {
        pseudo: document.getElementById("pseudo-feedback"),
        email: document.getElementById("email-feedback"),
        password: document.getElementById("password-feedback"),
        passwordConfirm: document.getElementById("password-confirm-feedback"),
        cgu: document.getElementById("cgu-feedback"),
        privacy: document.getElementById("privacy-feedback"),
    };

    const state = {
        pseudo: false,
        email: false,
        password: false,
        passwordConfirm: false,
        cgu: false,
        privacy: false,
    };

    const debounceTimers = {};

    function initializePasswordToggles() {
        document.querySelectorAll("[data-password-toggle]").forEach((button) => {
            button.addEventListener("click", () => {
                const input = document.getElementById(button.dataset.passwordToggle);
                const shouldShow = input.type === "password";
                input.type = shouldShow ? "text" : "password";
                button.setAttribute("aria-pressed", String(shouldShow));
                button.setAttribute(
                    "aria-label",
                    shouldShow ? "Masquer le mot de passe" : "Afficher le mot de passe"
                );
                button.classList.toggle("is-visible", shouldShow);
                input.focus();
            });
        });
    }

    function setStatus(message = "", type = "") {
        status.className = `status${type ? ` ${type}` : ""}`;
        status.textContent = message;
    }

    function setFieldState(name, type, message) {
        const field = fields[name].closest(".field");
        field.classList.remove("is-valid", "is-invalid", "is-pending");
        if (type) {
            field.classList.add(`is-${type}`);
        }

        feedback[name].textContent = message || "";
        feedback[name].className = `field-feedback${type ? ` ${type}` : ""}`;
    }

    function updateSubmitState() {
        submitButton.disabled = !Object.values(state).every(Boolean);
    }

    function validateEmailFormat(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email);
    }

    function getPasswordChecks() {
        const password = fields.password.value;
        const pseudo = fields.pseudo.value.trim().toLowerCase();
        const email = fields.email.value.trim().toLowerCase();
        const emailName = email.includes("@") ? email.split("@")[0] : "";
        const lowered = password.toLowerCase();

        return {
            length: password.length >= 12,
            lower: /[a-z]/.test(password),
            upper: /[A-Z]/.test(password),
            number: /\d/.test(password),
            special: /[^A-Za-z0-9]/.test(password),
            identity: Boolean(password)
                && (!pseudo || !lowered.includes(pseudo))
                && (!emailName || !lowered.includes(emailName)),
        };
    }

    function validatePassword() {
        const checks = getPasswordChecks();
        const valid = Object.values(checks).every(Boolean);

        document.querySelectorAll("[data-rule]").forEach((item) => {
            const passed = checks[item.dataset.rule];
            item.classList.toggle("passed", passed);
        });

        state.password = valid;
        if (!fields.password.value) {
            setFieldState("password", "", "");
        } else if (valid) {
            setFieldState("password", "valid", "Mot de passe conforme.");
        } else {
            setFieldState("password", "invalid", "Le mot de passe ne respecte pas encore toutes les règles.");
        }

        validatePasswordConfirm();
        updateSubmitState();
    }

    function validatePasswordConfirm() {
        const password = fields.password.value;
        const confirm = fields.passwordConfirm.value;
        const valid = Boolean(confirm) && password === confirm;

        state.passwordConfirm = valid;
        if (!confirm) {
            setFieldState("passwordConfirm", "", "");
        } else if (valid) {
            setFieldState("passwordConfirm", "valid", "Les mots de passe correspondent.");
        } else {
            setFieldState("passwordConfirm", "invalid", "Les mots de passe ne correspondent pas.");
        }
        updateSubmitState();
    }

    function validateConsent(name) {
        const valid = fields[name].checked;
        state[name] = valid;

        if (valid) {
            setFieldState(name, "valid", "");
        } else {
            const message = name === "cgu"
                ? "L'acceptation des conditions est obligatoire."
                : "La prise de connaissance de la politique de confidentialité est obligatoire.";
            setFieldState(name, "invalid", message);
        }

        updateSubmitState();
    }

    async function checkAvailability(name, value) {
        const trimmed = value.trim();

        if (name === "pseudo" && trimmed.length < 3) {
            state.pseudo = false;
            setFieldState("pseudo", trimmed ? "invalid" : "", trimmed ? "Le pseudo doit contenir au moins 3 caractères." : "");
            updateSubmitState();
            return;
        }

        if (name === "email" && !validateEmailFormat(trimmed)) {
            state.email = false;
            setFieldState("email", trimmed ? "invalid" : "", trimmed ? "Le format de l’adresse e-mail est invalide." : "");
            updateSubmitState();
            return;
        }

        setFieldState(name, "pending", "Vérification en cours...");
        state[name] = false;
        updateSubmitState();

        try {
            const result = await window.AuthAPI.checkRegisterAvailability({ [name]: trimmed });
            const fieldResult = result[name];
            const available = Boolean(fieldResult?.available);
            state[name] = available;
            setFieldState(name, available ? "valid" : "invalid", fieldResult?.message || (available ? "Disponible." : "Déjà utilisé."));
        } catch (_error) {
            state[name] = false;
            setFieldState(name, "invalid", "Vérification impossible pour le moment.");
        } finally {
            updateSubmitState();
        }
    }

    function debounce(name, callback) {
        window.clearTimeout(debounceTimers[name]);
        debounceTimers[name] = window.setTimeout(callback, 350);
    }

    fields.pseudo.addEventListener("input", () => {
        debounce("pseudo", () => checkAvailability("pseudo", fields.pseudo.value));
        validatePassword();
    });

    fields.email.addEventListener("input", () => {
        debounce("email", () => checkAvailability("email", fields.email.value));
        validatePassword();
    });

    fields.password.addEventListener("input", validatePassword);
    fields.passwordConfirm.addEventListener("input", validatePasswordConfirm);
    fields.cgu.addEventListener("change", () => validateConsent("cgu"));
    fields.privacy.addEventListener("change", () => validateConsent("privacy"));
    initializePasswordToggles();

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        setStatus();
        submitButton.disabled = true;

        if (!Object.values(state).every(Boolean)) {
            setStatus("Corrige les champs signalés avant de créer le compte.", "error");
            updateSubmitState();
            return;
        }

        const payload = {
            pseudo: fields.pseudo.value.trim(),
            email: fields.email.value.trim(),
            password: fields.password.value,
            cgu_accepted: fields.cgu.checked,
            privacy_policy_accepted: fields.privacy.checked,
            notifications_accepted: fields.notifications.checked,
        };

        try {
            const result = await window.AuthAPI.register(payload);
            window.AuthAPI.setTokens(result);
            setStatus("Compte créé avec succès. Redirection...", "success");
            window.setTimeout(() => {
                window.location.href = result.user?.is_staff
                    ? "/admin-dashboard.html"
                    : "/dashboard.html";
            }, 700);
        } catch (error) {
            if (error.payload?.email) {
                state.email = false;
                setFieldState("email", "invalid", error.payload.email.join(" "));
            }
            if (error.payload?.pseudo) {
                state.pseudo = false;
                setFieldState("pseudo", "invalid", error.payload.pseudo.join(" "));
            }
            if (error.payload?.password) {
                state.password = false;
                setFieldState("password", "invalid", error.payload.password.join(" "));
            }
            if (error.payload?.cgu_accepted) {
                state.cgu = false;
                setFieldState("cgu", "invalid", error.payload.cgu_accepted.join(" "));
            }
            if (error.payload?.privacy_policy_accepted) {
                state.privacy = false;
                setFieldState("privacy", "invalid", error.payload.privacy_policy_accepted.join(" "));
            }
            setStatus(error.message || "Erreur lors de l’inscription.", "error");
            updateSubmitState();
        }
    });
});
