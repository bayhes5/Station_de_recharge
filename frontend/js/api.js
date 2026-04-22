const API_BASE_URL = window.__API_BASE_URL__ || "http://localhost:8000/api";
const ACCESS_TOKEN_KEY = "station_access_token";
const REFRESH_TOKEN_KEY = "station_refresh_token";

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
    const refreshToken = getRefreshToken();
    const accessRemaining = getTokenTimeRemaining(accessToken);
    const refreshRemaining = getTokenTimeRemaining(refreshToken);

    return {
        hasAccessToken: Boolean(accessToken),
        hasRefreshToken: Boolean(refreshToken),
        accessExpiry: getTokenExpiry(accessToken),
        refreshExpiry: getTokenExpiry(refreshToken),
        accessRemaining,
        refreshRemaining,
        accessReadable: formatDuration(accessRemaining),
        refreshReadable: formatDuration(refreshRemaining),
        accessExpired: accessRemaining !== null && accessRemaining <= 0,
        refreshExpired: refreshRemaining !== null && refreshRemaining <= 0,
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

async function refreshAccessToken() {
    const refresh = getRefreshToken();
    if (!refresh) {
        return null;
    }

    const payload = await doRequest("/token/refresh/", {
        method: "POST",
        auth: false,
        retryOnAuthFailure: false,
        body: JSON.stringify({ refresh }),
    });

    if (payload.access) {
        setTokens({ access: payload.access });
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

async function ensureSession() {
    if (!getAccessToken() && !getRefreshToken()) {
        return null;
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
        localStorage.setItem(ACCESS_TOKEN_KEY, access);
    }
    if (refresh) {
        localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
    }
}

function getAccessToken() {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
}

function getRefreshToken() {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
}

function clearTokens() {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
}

function logout() {
    clearTokens();
    window.location.href = "/login.html";
}

window.AuthAPI = {
    API_BASE_URL,
    register,
    login,
    getMe,
    getDashboard,
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
