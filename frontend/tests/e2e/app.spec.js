import { expect, test } from "@playwright/test";

const apiOrigin = "http://localhost:8000";
const frontendOrigin = "http://127.0.0.1:4173";

function encodeBase64Url(payload) {
  return Buffer.from(JSON.stringify(payload))
    .toString("base64url");
}

function createAccessToken() {
  const now = Math.floor(Date.now() / 1000);
  return [
    encodeBase64Url({ alg: "HS256", typ: "JWT" }),
    encodeBase64Url({ exp: now + 3600, user_id: "e2e-user" }),
    "signature",
  ].join(".");
}

function jsonResponse(payload, { status = 200, headers = {} } = {}) {
  return {
    status,
    contentType: "application/json",
    headers: {
      "Access-Control-Allow-Origin": frontendOrigin,
      "Access-Control-Allow-Credentials": "true",
      ...headers,
    },
    body: JSON.stringify(payload),
  };
}

async function mockApi(page, { admin = false } = {}) {
  await page.route(`${apiOrigin}/api/**`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());

    if (request.method() === "OPTIONS") {
      await route.fulfill({
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": frontendOrigin,
          "Access-Control-Allow-Credentials": "true",
          "Access-Control-Allow-Headers": "content-type, authorization",
          "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
        },
      });
      return;
    }

    if (url.pathname === "/api/login/") {
      await route.fulfill(jsonResponse(
        {
          access: createAccessToken(),
          user: {
            pseudo: admin ? "admin" : "alice",
            email: admin ? "admin@example.com" : "alice@example.com",
            statut: "actif",
            is_staff: admin,
            is_technician: false,
          },
        },
        {
          headers: {
            "Set-Cookie": "station_refresh_token=e2e-refresh; HttpOnly; Path=/api/; SameSite=Lax",
          },
        },
      ));
      return;
    }

    if (url.pathname === "/api/token/refresh/") {
      await route.fulfill(jsonResponse({ access: createAccessToken() }));
      return;
    }

    if (url.pathname === "/api/me/") {
      await route.fulfill(jsonResponse({
        user: {
          pseudo: admin ? "admin" : "alice",
          email: admin ? "admin@example.com" : "alice@example.com",
          statut: "actif",
          is_staff: admin,
        },
        profile: { nom: admin ? "Admin" : "Alice" },
      }));
      return;
    }

    if (url.pathname === "/api/dashboard/") {
      await route.fulfill(jsonResponse({
        user: {
          id: admin ? "admin-id" : "user-id",
          pseudo: admin ? "admin" : "alice",
          email: admin ? "admin@example.com" : "alice@example.com",
          statut: "actif",
          is_staff: admin,
        },
        stats: {
          sessions_total: 0,
          reservations_total: 0,
          reservations_upcoming: 0,
        },
        active_session: null,
        recharge_history: [],
        upcoming_reservations: [],
        reservations_history: [],
      }));
      return;
    }

    if (url.pathname === "/api/admin/overview/") {
      await route.fulfill(jsonResponse({
        stats: {
          users_total: 2,
          stations_total: 1,
          emplacements_total: 2,
          reservations_upcoming: 0,
          sessions_active: 0,
          sessions_archived: 0,
        },
        recent_users: [],
        recent_stations: [],
        recent_emplacements: [],
      }));
      return;
    }

    if (url.pathname === "/api/admin/supervision/") {
      await route.fulfill(jsonResponse({
        stats: {
          devices_total: 1,
          devices_online: 1,
          devices_offline: 0,
          active_alerts: 0,
          critical_alerts: 0,
          telemetry_samples_24h: 4,
        },
        devices: [],
        alerts: [],
        measurements: [],
      }));
      return;
    }

    if (url.pathname === "/api/admin/users/") {
      await route.fulfill(jsonResponse({ results: [] }));
      return;
    }

    if (url.pathname === "/api/admin/stations/") {
      await route.fulfill(jsonResponse({
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id_station: "station-1",
            nom: "Station Centre",
            localisation_text: "Centre-ville",
            latitude: 48.8566,
            longitude: 2.3522,
            statut: "active",
          },
        ],
      }));
      return;
    }

    if (url.pathname === "/api/admin/emplacements/") {
      await route.fulfill(jsonResponse({
        results: [
          {
            id_emplacement: "slot-1",
            station: "station-1",
            station_nom: "Station Centre",
            numero: 1,
            statut: "disponible",
            lock_state: "verrouille",
          },
          {
            id_emplacement: "slot-2",
            station: "station-1",
            station_nom: "Station Centre",
            numero: 2,
            statut: "maintenance",
            lock_state: "deverrouille",
          },
        ],
      }));
      return;
    }

    if (url.pathname === "/api/admin/technicians/" || url.pathname === "/api/admin/maintenances/") {
      await route.fulfill(jsonResponse({
        count: 0,
        next: null,
        previous: null,
        results: [],
      }));
      return;
    }

    if (url.pathname === "/api/admin/reservations/") {
      await route.fulfill(jsonResponse({ upcoming: [], archived: [] }));
      return;
    }

    if (url.pathname === "/api/admin/sessions/") {
      await route.fulfill(jsonResponse({ active: [], archived: [] }));
      return;
    }

    await route.fulfill(jsonResponse({ detail: "Unhandled mocked route" }, { status: 404 }));
  });
}

test("public pages render without console errors", async ({ page }) => {
  await mockApi(page);

  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Réservez votre borne/i })).toBeVisible();

  await page.goto("/login.html");
  await expect(page.getByRole("heading", { name: /Accéder au compte/i })).toBeVisible();

  await page.goto("/register.html");
  await expect(page.getByRole("heading", { name: /Créer un compte/i })).toBeVisible();

  expect(consoleErrors).toEqual([]);
});

test("login flow uses mocked API and opens the dashboard", async ({ page }) => {
  await mockApi(page);

  await page.goto("/login.html");
  await page.getByLabel("Pseudo ou e-mail").fill("alice");
  await page.getByLabel("Mot de passe").fill("ValidPass123!");
  await page.getByRole("button", { name: "Se connecter" }).click();

  await expect(page.getByText("Connexion réussie.")).toBeVisible();
  await page.waitForURL("**/dashboard.html");
  await expect(page.locator("#dashboard-pseudo")).toHaveText("alice");
  await expect(page.getByText("Cookie HttpOnly actif")).toBeVisible();
});

test("admin infrastructure expands station emplacements", async ({ page }) => {
  await mockApi(page, { admin: true });

  await page.goto("/admin-dashboard.html#infrastructure");

  await expect(page.getByRole("heading", { name: /Administration/i })).toBeVisible();
  const stationToggle = page.getByRole("button", { name: /Afficher les emplacements de Station Centre/i });
  await expect(stationToggle).toBeVisible();
  await expect(page.getByText("Emplacement 1")).not.toBeVisible();

  await stationToggle.click();

  await expect(page.getByText("Emplacements de Station Centre")).toBeVisible();
  await expect(page.getByText("Emplacement 1")).toBeVisible();
  await expect(page.getByText("Emplacement 2")).toBeVisible();
});

test("admin supervision links directly to the Grafana dashboard", async ({ page }) => {
  await mockApi(page, { admin: true });

  await page.goto("/admin-dashboard.html#supervision");

  const grafanaLink = page.getByRole("link", { name: "Ouvrir Grafana" });
  await expect(grafanaLink).toHaveAttribute(
    "href",
    "http://127.0.0.1:3000/grafana/d/station-supervision/station-supervision-technique?orgId=1&from=now-6h&to=now&refresh=5s",
  );
  await expect(page.getByRole("button", { name: "Précédent" }).first()).toBeVisible();
});
