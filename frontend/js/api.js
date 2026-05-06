const API_BASE_URL = window.__API_BASE_URL__ || import.meta.env?.VITE_API_BASE_URL || "http://localhost:8000/api";
const LEGACY_ACCESS_TOKEN_KEY = "station_access_token";
const LEGACY_REFRESH_TOKEN_KEY = "station_refresh_token";
let accessTokenMemory = null;
let refreshCookieAvailable = false;

function getHeaders(extraHeaders = {}, includeJson = false, token = null) {
    const headers = {
        Accept: "application/json",
        ...(includeJson ? { "Content-Type": "application/json" } : {}),
        ...extraHeaders,
    };

    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }

    return headers;
}

async function parseResponse(response) {
    const text = await response.text();

    if (!text) {
        return {};
    }

    try {
        return JSON.parse(text);
    } catch (_error) {
        return { detail: text };
    }
}

function base64UrlToBase64(input) {
    return input.replace(/-/g, "+").replace(/_/g, "/").padEnd(
        Math.ceil(input.length / 4) * 4,
        "="
    );
}

function decodeJwt(token) {
    if (!token) {
        return null;
    }

    const parts = token.split(".");
    if (parts.length < 2) {
        return null;
    }

    try {
        const payload = atob(base64UrlToBase64(parts[1]));
        return JSON.parse(payload);
    } catch (_error) {
        return null;
    }
}

function formatDuration(seconds) {
    if (seconds === null || seconds === undefined) {
        return "inconnue";
    }

    if (seconds <= 0) {
        return "expire";
    }

    const totalMinutes = Math.ceil(seconds / 60);
    if (totalMinutes < 60) {
        return `${totalMinutes} min`;
    }

    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;

    if (hours < 24) {
        return minutes > 0 ? `${hours} h ${minutes} min` : `${hours} h`;
    }

    const days = Math.floor(hours / 24);
    const remainingHours = hours % 24;
    return remainingHours > 0 ? `${days} j ${remainingHours} h` : `${days} j`;
}

function getTokenPayload(token) {
    return decodeJwt(token);
}

function getTokenExpiry(token) {
    const payload = getTokenPayload(token);
    if (!payload?.exp) {
        return null;
    }

    return new Date(payload.exp * 1000);
}

function getTokenTimeRemaining(token) {
    const expiry = getTokenExpiry(token);
    if (!expiry) {
        return null;
    }

    return Math.floor((expiry.getTime() - Date.now()) / 1000);
}

function getSessionSnapshot() {
    const accessToken = getAccessToken();
    const accessRemaining = getTokenTimeRemaining(accessToken);

    return {
        hasAccessToken: Boolean(accessToken),
        hasRefreshToken: refreshCookieAvailable,
        accessExpiry: getTokenExpiry(accessToken),
        refreshExpiry: null,
        accessRemaining,
        refreshRemaining: null,
        accessReadable: formatDuration(accessRemaining),
        refreshReadable: refreshCookieAvailable ? "cookie HttpOnly" : "inconnue",
        accessExpired: accessRemaining !== null && accessRemaining <= 0,
        refreshExpired: false,
    };
}

async function doRequest(path, options = {}) {
    const {
        auth = true,
        body,
        headers,
        retryOnAuthFailure = true,
        ...fetchOptions
    } = options;

    const accessToken = auth ? getAccessToken() : null;
    const response = await fetch(`${API_BASE_URL}${path}`, {
        ...fetchOptions,
        credentials: "include",
        headers: getHeaders(headers, Boolean(body), accessToken),
        body,
    });

    const payload = await parseResponse(response);

    if (!response.ok) {
        const error = new Error(payload.detail || payload.error || "Request failed");
        error.payload = payload;
        error.status = response.status;

        if (response.status === 401 && auth && retryOnAuthFailure) {
            try {
                const refreshed = await refreshAccessToken();
                if (refreshed) {
                    return doRequest(path, {
                        ...options,
                        retryOnAuthFailure: false,
                    });
                }
            } catch (_refreshError) {
                clearTokens();
            }
        }

        throw error;
    }

    return payload;
}

function withQuery(path, params = {}) {
    const query = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") {
            query.set(key, value);
        }
    });
    const queryString = query.toString();
    return queryString ? `${path}?${queryString}` : path;
}

async function refreshAccessToken() {
    const payload = await doRequest("/token/refresh/", {
        method: "POST",
        auth: false,
        retryOnAuthFailure: false,
    });

    if (payload.access) {
        setTokens({ access: payload.access });
        refreshCookieAvailable = true;
        return payload.access;
    }

    return null;
}

async function register(data) {
    return doRequest("/register/", {
        method: "POST",
        auth: false,
        body: JSON.stringify(data),
    });
}

async function checkRegisterAvailability(params = {}) {
    const query = new URLSearchParams(params).toString();
    return doRequest(`/register/availability/${query ? `?${query}` : ""}`, {
        method: "GET",
        auth: false,
    });
}

async function login(data) {
    return doRequest("/login/", {
        method: "POST",
        auth: false,
        body: JSON.stringify(data),
    });
}

async function getMe() {
    return doRequest("/me/", {
        method: "GET",
    });
}

async function getDashboard() {
    return doRequest("/dashboard/", {
        method: "GET",
    });
}

async function getStations() {
    return doRequest("/stations/", {
        method: "GET",
    });
}

async function getReservations() {
    return doRequest("/reservations/", {
        method: "GET",
    });
}

async function createReservation(data) {
    return doRequest("/reservations/", {
        method: "POST",
        body: JSON.stringify(data),
    });
}

async function cancelReservation(id) {
    return doRequest(`/reservations/${id}/cancel/`, {
        method: "POST",
    });
}

async function getReservationAccessPayload(id) {
    return doRequest(`/reservations/${id}/access-payload/`, {
        method: "POST",
    });
}

async function getReservationAvailability(params) {
    const query = new URLSearchParams(params || {}).toString();
    return doRequest(`/reservations/availability/${query ? `?${query}` : ""}`, {
        method: "GET",
    });
}

async function getProfile() {
    return doRequest("/me/profile/", {
        method: "GET",
    });
}

async function updateProfile(data) {
    return doRequest("/me/profile/", {
        method: "PATCH",
        body: JSON.stringify(data),
    });
}

async function changePassword(data) {
    return doRequest("/me/change-password/", {
        method: "POST",
        body: JSON.stringify(data),
    });
}

async function exportAccount() {
    return doRequest("/me/export/", {
        method: "GET",
    });
}

async function getAuthMethods() {
    return doRequest("/me/auth-methods/", {
        method: "GET",
    });
}

async function getAuthHistory() {
    return doRequest("/me/auth-history/", {
        method: "GET",
    });
}

async function createAuthMethod(data) {
    return doRequest("/me/auth-methods/create/", {
        method: "POST",
        body: JSON.stringify(data),
    });
}

async function createRfidLinkCode() {
    return doRequest("/me/auth-methods/link-code/", {
        method: "POST",
    });
}

async function deleteAuthMethod(authId) {
    return doRequest(`/me/auth-methods/${authId}/`, {
        method: "DELETE",
    });
}

async function deleteAccount() {
    return doRequest("/me/profile/", {
        method: "DELETE",
    });
}

async function getAdminOverview() {
    return doRequest("/admin/overview/", {
        method: "GET",
    });
}

async function getAdminSupervision() {
    return doRequest("/admin/supervision/", {
        method: "GET",
    });
}

async function getAdminReservations() {
    return doRequest("/admin/reservations/", {
        method: "GET",
    });
}

async function cancelAdminReservation(id) {
    return doRequest(`/admin/reservations/${id}/cancel/`, {
        method: "POST",
    });
}

async function getAdminSessions() {
    return doRequest("/admin/sessions/", {
        method: "GET",
    });
}

async function getAdminUsers(params) {
    return doRequest(withQuery("/admin/users/", params), {
        method: "GET",
    });
}

async function createAdminUser(data) {
    return doRequest("/admin/users/", {
        method: "POST",
        body: JSON.stringify(data),
    });
}

async function updateAdminUser(id, data) {
    return doRequest(`/admin/users/${id}/`, {
        method: "PATCH",
        body: JSON.stringify(data),
    });
}

async function deleteAdminUser(id) {
    return doRequest(`/admin/users/${id}/`, {
        method: "DELETE",
    });
}

async function resetAdminUserPassword(id) {
    return doRequest(`/admin/users/${id}/reset-password/`, {
        method: "POST",
    });
}

async function getAdminUserAuthMethods(id) {
    return doRequest(`/admin/users/${id}/auth-methods/`, {
        method: "GET",
    });
}

async function createAdminUserRfid(id, data) {
    return doRequest(`/admin/users/${id}/auth-methods/`, {
        method: "POST",
        body: JSON.stringify(data),
    });
}

async function revokeAdminUserAuthMethod(userId, authId) {
    return doRequest(`/admin/users/${userId}/auth-methods/${authId}/revoke/`, {
        method: "POST",
    });
}

async function regenerateAdminReservationAccess(id) {
    return doRequest(`/admin/reservations/${id}/access-payload/`, {
        method: "POST",
    });
}

async function revokeAdminReservationAccess(id) {
    return doRequest(`/admin/reservations/${id}/revoke-access/`, {
        method: "POST",
    });
}

async function getAdminStations(params) {
    return doRequest(withQuery("/admin/stations/", params), {
        method: "GET",
    });
}

async function createAdminStation(data) {
    return doRequest("/admin/stations/", {
        method: "POST",
        body: JSON.stringify(data),
    });
}

async function updateAdminStation(id, data) {
    return doRequest(`/admin/stations/${id}/`, {
        method: "PATCH",
        body: JSON.stringify(data),
    });
}

async function deleteAdminStation(id) {
    return doRequest(`/admin/stations/${id}/`, {
        method: "DELETE",
    });
}

async function getAdminEmplacements(params) {
    return doRequest(withQuery("/admin/emplacements/", params), {
        method: "GET",
    });
}

async function createAdminEmplacement(data) {
    return doRequest("/admin/emplacements/", {
        method: "POST",
        body: JSON.stringify(data),
    });
}

async function updateAdminEmplacement(id, data) {
    return doRequest(`/admin/emplacements/${id}/`, {
        method: "PATCH",
        body: JSON.stringify(data),
    });
}

async function deleteAdminEmplacement(id) {
    return doRequest(`/admin/emplacements/${id}/`, {
        method: "DELETE",
    });
}

async function getAdminTechnicians(params) {
    return doRequest(withQuery("/admin/technicians/", params), {
        method: "GET",
    });
}

async function createAdminTechnician(data) {
    return doRequest("/admin/technicians/", {
        method: "POST",
        body: JSON.stringify(data),
    });
}

async function updateAdminTechnician(id, data) {
    return doRequest(`/admin/technicians/${id}/`, {
        method: "PATCH",
        body: JSON.stringify(data),
    });
}

async function deleteAdminTechnician(id) {
    return doRequest(`/admin/technicians/${id}/`, {
        method: "DELETE",
    });
}

async function getAdminMaintenances(params) {
    return doRequest(withQuery("/admin/maintenances/", params), {
        method: "GET",
    });
}

async function createAdminMaintenance(data) {
    return doRequest("/admin/maintenances/", {
        method: "POST",
        body: JSON.stringify(data),
    });
}

async function updateAdminMaintenance(id, data) {
    return doRequest(`/admin/maintenances/${id}/`, {
        method: "PATCH",
        body: JSON.stringify(data),
    });
}

async function deleteAdminMaintenance(id) {
    return doRequest(`/admin/maintenances/${id}/`, {
        method: "DELETE",
    });
}

async function getTechnicianMaintenances() {
    return doRequest("/technician/maintenances/", {
        method: "GET",
    });
}

async function terminalAuthenticate(data) {
    return doRequest("/terminal/authenticate/", {
        method: "POST",
        body: JSON.stringify(data),
    });
}

async function ensureSession() {
    if (!getAccessToken()) {
        try {
            await refreshAccessToken();
        } catch (_error) {
            clearTokens();
            return null;
        }
    }

    try {
        return await getMe();
    } catch (_error) {
        clearTokens();
        return null;
    }
}

function setTokens({ access, refresh }) {
    if (access) {
        accessTokenMemory = access;
        refreshCookieAvailable = true;
    }
    if (refresh) {
        refreshCookieAvailable = true;
    }
    localStorage.removeItem(LEGACY_ACCESS_TOKEN_KEY);
    localStorage.removeItem(LEGACY_REFRESH_TOKEN_KEY);
    sessionStorage.removeItem(LEGACY_ACCESS_TOKEN_KEY);
    sessionStorage.removeItem(LEGACY_REFRESH_TOKEN_KEY);
}

function getAccessToken() {
    return accessTokenMemory;
}

function getRefreshToken() {
    return null;
}

function clearTokens() {
    accessTokenMemory = null;
    refreshCookieAvailable = false;
    localStorage.removeItem(LEGACY_ACCESS_TOKEN_KEY);
    localStorage.removeItem(LEGACY_REFRESH_TOKEN_KEY);
    sessionStorage.removeItem(LEGACY_ACCESS_TOKEN_KEY);
    sessionStorage.removeItem(LEGACY_REFRESH_TOKEN_KEY);
}

async function logout() {
    try {
        await doRequest("/logout/", {
            method: "POST",
            auth: false,
            retryOnAuthFailure: false,
        });
    } catch (_error) {
        // Local logout must still happen even if the API is unavailable.
    } finally {
        clearTokens();
        window.location.href = "/login.html";
    }
}

window.AuthAPI = {
    API_BASE_URL,
    register,
    checkRegisterAvailability,
    login,
    getMe,
    getDashboard,
    getStations,
    getReservations,
    createReservation,
    cancelReservation,
    getReservationAccessPayload,
    getReservationAvailability,
    getProfile,
    updateProfile,
    changePassword,
    exportAccount,
    getAuthMethods,
    getAuthHistory,
    createAuthMethod,
    createRfidLinkCode,
    deleteAuthMethod,
    deleteAccount,
    getAdminOverview,
    getAdminSupervision,
    getAdminReservations,
    cancelAdminReservation,
    getAdminSessions,
    getAdminUsers,
    createAdminUser,
    updateAdminUser,
    deleteAdminUser,
    resetAdminUserPassword,
    getAdminUserAuthMethods,
    createAdminUserRfid,
    revokeAdminUserAuthMethod,
    regenerateAdminReservationAccess,
    revokeAdminReservationAccess,
    getAdminStations,
    createAdminStation,
    updateAdminStation,
    deleteAdminStation,
    getAdminEmplacements,
    createAdminEmplacement,
    updateAdminEmplacement,
    deleteAdminEmplacement,
    getAdminTechnicians,
    createAdminTechnician,
    updateAdminTechnician,
    deleteAdminTechnician,
    getAdminMaintenances,
    createAdminMaintenance,
    updateAdminMaintenance,
    deleteAdminMaintenance,
    getTechnicianMaintenances,
    terminalAuthenticate,
    ensureSession,
    refreshAccessToken,
    getTokenPayload,
    getTokenExpiry,
    getTokenTimeRemaining,
    getSessionSnapshot,
    formatDuration,
    setTokens,
    getAccessToken,
    getRefreshToken,
    clearTokens,
    logout,
};
