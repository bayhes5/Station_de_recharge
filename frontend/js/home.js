document.addEventListener("DOMContentLoaded", async () => {
    const accountLink = document.getElementById("home-account-link");
    const registerLink = document.getElementById("home-register-link");
    const loginLink = document.getElementById("home-login-link");
    const ctaStack = accountLink?.closest(".home-cta-stack");
    if (!accountLink) {
        return;
    }

    const session = await window.AuthAPI.ensureSession();
    if (!session?.user) {
        return;
    }

    accountLink.hidden = false;
    ctaStack?.classList.add("is-authenticated");
    if (registerLink) {
        registerLink.hidden = true;
    }
    if (loginLink) {
        loginLink.hidden = true;
    }
    if (session.user.is_staff) {
        accountLink.href = "/admin-dashboard.html";
        accountLink.textContent = "Mon compte";
        return;
    }
    if (session.user.is_technician) {
        accountLink.href = "/technician-dashboard.html";
        accountLink.textContent = "Mon compte";
        return;
    }
    accountLink.href = "/dashboard.html";
    accountLink.textContent = "Mon compte";
});
