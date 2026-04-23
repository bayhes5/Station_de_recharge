function downloadJson(filename, data) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
}

document.addEventListener("DOMContentLoaded", async () => {
    const status = document.getElementById("profile-status");
    const logoutBtn = document.getElementById("logout-btn");
    const exportBtn = document.getElementById("export-btn");
    const deleteBtn = document.getElementById("delete-btn");
    const profileForm = document.getElementById("profile-form");
    const passwordForm = document.getElementById("password-form");

    logoutBtn.addEventListener("click", () => window.AuthAPI.logout());

    const session = await window.AuthAPI.ensureSession();
    if (!session) {
        status.classList.add("error");
        status.textContent = "Session absente ou expiree. Redirection vers la connexion.";
        window.setTimeout(() => {
            window.location.href = "/login.html";
        }, 1200);
        return;
    }

    let currentProfile = null;

    async function loadProfile() {
        const result = await window.AuthAPI.getProfile();
        currentProfile = result;
        const user = result.user;
        const profile = result.profile || {};

        profileForm.pseudo.value = user.pseudo || "";
        profileForm.email.value = user.email || "";
        profileForm.telephone.value = user.telephone || "";
        profileForm.nom.value = profile.nom || user.nom || "";
        profileForm.statut.value = user.statut || "";

        status.classList.remove("error");
        status.textContent = "Profil charge.";
    }

    try {
        await loadProfile();
    } catch (_error) {
        status.classList.add("error");
        status.textContent = "Impossible de charger le profil.";
        return;
    }

    profileForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        status.classList.remove("error");

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
            status.textContent = "Profil mis a jour.";
        } catch (error) {
            status.classList.add("error");
            if (error.payload?.email) {
                status.textContent = `Email: ${error.payload.email.join(" ")}`;
            } else if (error.payload?.pseudo) {
                status.textContent = `Pseudo: ${error.payload.pseudo.join(" ")}`;
            } else {
                status.textContent = error.message || "Erreur lors de la mise a jour du profil.";
            }
        } finally {
            submitButton.disabled = false;
        }
    });

    passwordForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        status.classList.remove("error");

        const submitButton = passwordForm.querySelector('button[type="submit"]');
        submitButton.disabled = true;

        const payload = {
            current_password: passwordForm.current_password.value,
            new_password: passwordForm.new_password.value,
            confirm_password: passwordForm.confirm_password.value,
        };

        if (payload.new_password !== payload.confirm_password) {
            status.classList.add("error");
            status.textContent = "Les mots de passe ne correspondent pas.";
            submitButton.disabled = false;
            return;
        }

        try {
            await window.AuthAPI.changePassword(payload);
            passwordForm.reset();
            status.textContent = "Mot de passe mis a jour.";
        } catch (error) {
            status.classList.add("error");
            if (error.payload?.current_password) {
                status.textContent = error.payload.current_password;
            } else if (error.payload?.new_password) {
                status.textContent = `Nouveau mot de passe: ${error.payload.new_password.join(" ")}`;
            } else {
                status.textContent = error.message || "Erreur lors du changement de mot de passe.";
            }
        } finally {
            submitButton.disabled = false;
        }
    });

    exportBtn.addEventListener("click", async () => {
        try {
            const account = await window.AuthAPI.exportAccount();
            downloadJson(`compte-${currentProfile.user.pseudo || "utilisateur"}.json`, account);
            status.textContent = "Export RGPD telecharge.";
        } catch (_error) {
            status.classList.add("error");
            status.textContent = "Impossible de telecharger tes donnees.";
        }
    });

    deleteBtn.addEventListener("click", async () => {
        const confirmed = window.confirm(
            "Cette action supprime ton compte et les donnees associees. Continuer ?"
        );

        if (!confirmed) {
            return;
        }

        try {
            await window.AuthAPI.deleteAccount();
            window.AuthAPI.clearTokens();
            window.location.href = "/register.html";
        } catch (_error) {
            status.classList.add("error");
            status.textContent = "Impossible de supprimer le compte.";
        }
    });
});
