document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("login-form");
    const status = document.getElementById("login-status");

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        status.classList.remove("error");
        status.textContent = "";
        const submitButton = form.querySelector('button[type="submit"]');
        submitButton.disabled = true;

        const payload = {
            identifiant: form.identifiant.value.trim(),
            password: form.password.value,
        };

        if (!payload.identifiant || !payload.password) {
            status.classList.add("error");
            status.textContent = "Le pseudo/email et le mot de passe sont obligatoires.";
            return;
        }

        try {
            const result = await window.AuthAPI.login(payload);
            window.AuthAPI.setTokens(result);
            status.textContent = "Connexion réussie.";
            window.setTimeout(() => {
                window.location.href = "/dashboard.html";
            }, 800);
        } catch (error) {
            status.classList.add("error");
            status.textContent = error.message || "Identifiants invalides.";
        } finally {
            submitButton.disabled = false;
        }
    });
});
