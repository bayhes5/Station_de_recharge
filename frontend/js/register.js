document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("register-form");
    const status = document.getElementById("register-status");

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        status.classList.remove("error");
        status.textContent = "";
        const submitButton = form.querySelector('button[type="submit"]');
        submitButton.disabled = true;

        const payload = {
            pseudo: form.pseudo.value.trim(),
            email: form.email.value.trim(),
            telephone: form.telephone.value.trim(),
            password: form.password.value,
        };
        const passwordConfirm = form.passwordConfirm.value;

        if (!payload.pseudo || !payload.email || !payload.password) {
            status.classList.add("error");
            status.textContent = "Le pseudo, l'email et le mot de passe sont obligatoires.";
            return;
        }

        if (payload.password !== passwordConfirm) {
            status.classList.add("error");
            status.textContent = "Les mots de passe ne correspondent pas.";
            return;
        }

        try {
            const result = await window.AuthAPI.register(payload);
            window.AuthAPI.setTokens(result);
            status.textContent = "Compte cree avec succes.";
            window.setTimeout(() => {
                window.location.href = result.user?.is_staff
                    ? "/admin-dashboard.html"
                    : "/dashboard.html";
            }, 800);
        } catch (error) {
            status.classList.add("error");
            if (error.payload?.email) {
                status.textContent = `Email: ${error.payload.email.join(" ")}`;
                return;
            }
            if (error.payload?.pseudo) {
                status.textContent = `Pseudo: ${error.payload.pseudo.join(" ")}`;
                return;
            }
            if (error.payload?.password) {
                status.textContent = `Mot de passe: ${error.payload.password.join(" ")}`;
                return;
            }
            status.textContent = error.message || "Erreur lors de l'inscription.";
        } finally {
            submitButton.disabled = false;
        }
    });
});
