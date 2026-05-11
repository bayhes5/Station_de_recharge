import { resolve } from "node:path";
import { defineConfig } from "vite";

const pageNames = [
  "index",
  "login",
  "mobile-session",
  "register",
  "dashboard",
  "profile",
  "reservation",
  "admin-dashboard",
  "admin-form",
  "technician-dashboard",
];

export default defineConfig({
  root: ".",
  server: {
    port: 5173,
    strictPort: true,
  },
  preview: {
    port: 4173,
    strictPort: true,
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: Object.fromEntries(
        pageNames.map((name) => [name, resolve(__dirname, `${name}.html`)])
      ),
    },
  },
});
