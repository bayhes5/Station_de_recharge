import { expect, test } from "@playwright/test";

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

async function mockApi(page, { admin = false, technician = false } = {}) {
  let mobileSessionStatus = "pending";
  let mobileSessionReadsAfterAuthorization = 0;

  await page.route("**/api/**", async (route) => {
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
            pseudo: admin ? "admin" : technician ? "tech" : "alice",
            email: admin ? "admin@example.com" : technician ? "tech@example.com" : "alice@example.com",
            statut: "actif",
            is_staff: admin,
            is_technician: technician,
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
          pseudo: admin ? "admin" : technician ? "tech" : "alice",
          email: admin ? "admin@example.com" : technician ? "tech@example.com" : "alice@example.com",
          statut: "actif",
          is_staff: admin,
          is_technician: technician,
        },
        profile: { nom: admin ? "Admin" : technician ? "Technicien" : "Alice" },
      }));
      return;
    }

    if (url.pathname === "/api/dashboard/") {
      await route.fulfill(jsonResponse({
        user: {
          id: admin ? "admin-id" : "user-id",
          pseudo: admin ? "admin" : technician ? "tech" : "alice",
          email: admin ? "admin@example.com" : technician ? "tech@example.com" : "alice@example.com",
          statut: "actif",
          is_staff: admin,
          is_technician: technician,
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
          devices_firmware_update_required: 0,
          active_alerts: 0,
          critical_alerts: 0,
          telemetry_samples_24h: 4,
        },
        devices: [],
        alerts: [],
        measurements: [],
        commands: [],
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

    if (url.pathname === "/api/admin/stations/station-1/") {
      await route.fulfill(jsonResponse({
        id_station: "station-1",
        nom: "Station Centre",
        localisation_text: "Centre-ville",
        latitude: 48.8566,
        longitude: 2.3522,
        statut: "active",
      }));
      return;
    }

    if (url.pathname === "/api/admin/bornes/") {
      await route.fulfill(jsonResponse({
        results: [
          {
            id_borne: "borne-1",
            station: "station-1",
            station_nom: "Station Centre",
            numero: 1,
            nom: "Borne 1",
            mqtt_prefix: "station/station-1/borne-1",
            statut: "active",
            emplacements_count: 2,
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
            borne: "borne-1",
            borne_nom: "Borne 1",
            borne_numero: 1,
            numero: 1,
            statut: "disponible",
            lock_state: "verrouille",
          },
          {
            id_emplacement: "slot-2",
            station: "station-1",
            station_nom: "Station Centre",
            borne: "borne-1",
            borne_nom: "Borne 1",
            borne_numero: 1,
            numero: 2,
            statut: "maintenance",
            lock_state: "deverrouille",
          },
        ],
      }));
      return;
    }

    if (
      url.pathname === "/api/admin/technicians/" ||
      url.pathname === "/api/admin/technician-stations/" ||
      url.pathname === "/api/admin/maintenances/"
    ) {
      await route.fulfill(jsonResponse({
        count: 0,
        next: null,
        previous: null,
        results: [],
      }));
      return;
    }

    if (url.pathname === "/api/technician/maintenances/") {
      await route.fulfill(jsonResponse({
        count: 2,
        next: null,
        previous: null,
        results: [
          {
            id_maintenance: "maintenance-1",
            station: "station-1",
            station_nom: "Station Centre",
            type: "Contrôle préventif",
            status: "planifiee",
            date_planifiee: "2026-05-25T08:00:00Z",
            description: "Contrôle visuel des emplacements.",
          },
          {
            id_maintenance: "maintenance-2",
            station: "station-2",
            station_nom: "Station Nord",
            type: "Intervention",
            status: "planifiee",
            date_planifiee: "2026-05-25T10:00:00Z",
            description: "Vérification d'un contrôleur hors ligne.",
          },
        ],
      }));
      return;
    }

    if (url.pathname === "/api/technician/supervision/") {
      await route.fulfill(jsonResponse({
        stats: {
          devices_total: 2,
          devices_online: 1,
          devices_offline: 1,
          active_alerts: 1,
          critical_alerts: 0,
          telemetry_samples_24h: 2,
        },
        devices: [
          {
            id_device: "device-1",
            station_id: "station-1",
            station_nom: "Station Centre",
            slot_label: "Station Centre - Borne 1 - emplacement 1",
            online: true,
            status_display: "Disponible",
            lock_state: "verrouillé",
            firmware_version: "1.0.0",
            ip_address: "192.168.1.20",
            last_seen: "2026-05-25T08:00:00Z",
          },
          {
            id_device: "device-2",
            station_id: "station-2",
            station_nom: "Station Nord",
            slot_label: "Station Nord - Borne 2 - emplacement 1",
            online: false,
            status_display: "Hors ligne",
            lock_state: "verrouillé",
            firmware_version: "1.0.0",
            ip_address: "192.168.1.21",
            last_seen: null,
          },
        ],
        alerts: [
          {
            id_alerte: "11111111-1111-4111-8111-111111111111",
            station_id: "station-2",
            station_nom: "Station Nord",
            borne_nom: "Borne 2",
            emplacement_numero: 1,
            type: "offline",
            message: "Contrôleur hors ligne.",
            niveau_severite: "warning",
            status: "active",
            status_display: "Active",
            timestamp: "2026-05-25T08:00:00Z",
          },
        ],
        measurements: [
          { id_data: "data-1", station_id: "station-1", station_nom: "Station Centre" },
          { id_data: "data-2", station_id: "station-2", station_nom: "Station Nord" },
        ],
        commands: [
          {
            id_command: "command-1",
            station_id: "station-1",
            station_nom: "Station Centre",
            timestamp: "2026-05-25T08:00:00Z",
            slot_label: "Station Centre - Borne 1 - emplacement 1",
            action: "START",
            status: "acknowledged",
            message: "Commande exécutée.",
          },
          {
            id_command: "command-2",
            station_id: "station-2",
            station_nom: "Station Nord",
            timestamp: "2026-05-25T08:05:00Z",
            slot_label: "Station Nord - Borne 2 - emplacement 1",
            action: "STATUS",
            status: "timeout",
            message: "Contrôleur muet.",
          },
        ],
      }));
      return;
    }

    if (url.pathname === "/api/mobile-sessions/demo-token/") {
      if (mobileSessionStatus === "authorized") {
        mobileSessionReadsAfterAuthorization += 1;
        if (mobileSessionReadsAfterAuthorization >= 1) {
          mobileSessionStatus = "consumed";
        }
      }

      await route.fulfill(jsonResponse({
        mobile_session: {
          token: "demo-token",
          status: mobileSessionStatus,
          station_nom: "Station Centre",
          borne_nom: "Borne 1",
          expires_in: 540,
        },
        reservations: mobileSessionStatus === "pending"
          ? [
              {
                id_reservation: "reservation-1",
                station_id: "station-1",
                station_nom: "Station Centre",
                borne_id: "borne-1",
                borne_nom: "Borne 1",
                emplacement_numero: 1,
                reference_code: "DEMOQR1",
                date_debut: "2026-05-25T08:00:00Z",
                date_fin: "2026-05-25T09:00:00Z",
                compatible_terminal: true,
              },
            ]
          : [],
      }));
      return;
    }

    if (url.pathname === "/api/mobile-sessions/demo-token/authorize/") {
      mobileSessionStatus = "authorized";
      mobileSessionReadsAfterAuthorization = 0;
      await route.fulfill(jsonResponse({
        mobile_session: {
          token: "demo-token",
          status: "authorized",
          station_nom: "Station Centre",
          borne_nom: "Borne 1",
          expires_in: 540,
        },
        reservation: {
          id_reservation: "reservation-1",
          station_id: "station-1",
          station_nom: "Station Centre",
          borne_id: "borne-1",
          borne_nom: "Borne 1",
          emplacement_numero: 1,
          reference_code: "DEMOQR1",
          date_debut: "2026-05-25T08:00:00Z",
          date_fin: "2026-05-25T09:00:00Z",
          compatible_terminal: true,
        },
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
  await page.goto("/offline.html");
  await expect(page.getByRole("heading", { name: "Connexion indisponible" })).toBeVisible();

  expect(consoleErrors).toEqual([]);
});

test("PWA manifest exposes only direct user destinations", async ({ request }) => {
  const response = await request.get("/manifest.webmanifest");
  expect(response.ok()).toBeTruthy();

  const manifest = await response.json();
  const shortcutUrls = (manifest.shortcuts || []).map((shortcut) => shortcut.url);

  expect(shortcutUrls).toContain("/reservation.html");
  expect(shortcutUrls).toContain("/dashboard.html#reservations");
  expect(shortcutUrls).toContain("/profile.html");
  expect(shortcutUrls).not.toContain("/mobile-session.html");
});

test("reservation page does not depend on external CDN assets", async ({ request }) => {
  const response = await request.get("/reservation.html");
  expect(response.ok()).toBeTruthy();

  const html = await response.text();
  expect(html).not.toContain("unpkg.com");
  expect(html).not.toContain("leaflet@");
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
  await expect(page.getByRole("heading", { name: "Tableau de bord" })).toBeVisible();
});

test("admin infrastructure opens a station profile", async ({ page }) => {
  await mockApi(page, { admin: true });

  await page.goto("/admin-dashboard.html#infrastructure");

  await expect(page.getByRole("heading", { name: /Administration/i })).toBeVisible();
  const stationLink = page.getByRole("link", { name: "Ouvrir" }).first();
  await expect(stationLink).toBeVisible();
  await expect(page.getByText("Station Centre")).toBeVisible();

  await stationLink.click();

  await expect(page).toHaveURL(/admin-station\.html\?id=station-1/);
  await expect(page.getByRole("heading", { name: "Station Centre" })).toBeVisible();
  await expect(page.getByText("Borne 1")).toBeVisible();
  await expect(page.getByText("Emplacement 1")).toBeVisible();
  await expect(page.getByText("Emplacement 2")).toBeVisible();
});

test("admin supervision links directly to the Grafana dashboard", async ({ page }) => {
  await mockApi(page, { admin: true });

  await page.goto("/admin-dashboard.html#supervision");

  const grafanaLink = page.getByRole("link", { name: "Ouvrir Grafana" });
  await expect(grafanaLink).toHaveAttribute(
    "href",
    "http://127.0.0.1:3000/grafana/d/station-overview/station-vue-globale-supervision?orgId=1&from=now-6h&to=now&refresh=10s",
  );
  await expect(page.getByRole("button", { name: "Précédent" }).first()).toBeVisible();
});

test("technician supervision can be filtered by station", async ({ page }) => {
  await mockApi(page, { technician: true });

  await page.goto("/login.html");
  await page.getByLabel("Pseudo ou e-mail").fill("tech");
  await page.getByLabel("Mot de passe").fill("ValidPass123!");
  await page.getByRole("button", { name: "Se connecter" }).click();
  await page.waitForURL("**/technician-dashboard.html");
  await expect(page.getByRole("heading", { name: "Tableau de bord technicien" })).toBeVisible();
  await expect(page.locator("#tech-devices-list").getByText("Station Centre - Borne 1 - emplacement 1")).toBeVisible();
  await expect(page.locator("#tech-devices-list").getByText("Station Nord - Borne 2 - emplacement 1")).toBeVisible();

  await page.getByLabel("Station").selectOption("station-2");

  await expect(page.locator("#tech-devices-list").getByText("Station Nord - Borne 2 - emplacement 1")).toBeVisible();
  await expect(page.getByText("Station Centre - Borne 1 - emplacement 1")).toHaveCount(0);
  await expect(page.locator("#tech-stat-online")).toHaveText("0");
  await expect(page.locator("#tech-stat-offline")).toHaveText("1");
  await expect(page.locator("#tech-alerts-list").getByText("Contrôleur hors ligne.")).toBeVisible();
});

test("mobile session follows authorization until the kiosk consumes it", async ({ page }) => {
  await mockApi(page);

  await page.goto("/mobile-session.html?token=demo-token");

  await expect(page.getByRole("heading", { name: "Autoriser la borne" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Station Centre" })).toBeVisible();
  await page.getByRole("button", { name: "Autoriser cette borne" }).click();

  await expect(page.locator("#mobile-session-authorized-title")).toHaveText("Autorisation envoyée");
  await expect(page.locator("#mobile-step-authorized")).toHaveClass(/active/);
  await expect(page.locator("#mobile-session-authorized-title")).toHaveText("Borne autorisée", { timeout: 5000 });
  await expect(page.locator("#mobile-step-consumed")).toHaveClass(/active/);
});
