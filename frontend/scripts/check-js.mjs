import { readdirSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const roots = [
    "js",
    join("src", "pages"),
];
const files = [
    "playwright.config.js",
    "vite.config.js",
    ...roots.flatMap((root) => (
        readdirSync(root, { withFileTypes: true })
            .filter((entry) => entry.isFile() && entry.name.endsWith(".js"))
            .map((entry) => join(root, entry.name))
    )),
];

let hasFailure = false;

for (const file of files) {
    const result = spawnSync(process.execPath, ["--check", file], {
        stdio: "inherit",
        shell: false,
    });

    if (result.status !== 0) {
        hasFailure = true;
    }
}

if (hasFailure) {
    process.exit(1);
}

console.log(`Checked ${files.length} JavaScript files.`);
