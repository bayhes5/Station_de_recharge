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

async function mockApi(page) {
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
            pseudo: "alice",
            email: "alice@example.com",
            statut: "actif",
            is_staff: false,
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
          pseudo: "alice",
          email: "alice@example.com",
          statut: "actif",
          is_staff: false,
        },
        profile: { nom: "Alice" },
      }));
      return;
    }

    if (url.pathname === "/api/dashboard/") {
      await route.fulfill(jsonResponse({
        user: {
          pseudo: "alice",
          email: "alice@example.com",
          statut: "actif",
          is_staff: false,
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
