import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const roots = [
    "js",
    join("src", "pages"),
];
const files = [
    "playwright.config.js",
    "vite.config.js",
    join("..", "raspberry", "app", "app.js"),
    ...roots.flatMap((root) => (
        readdirSync(root, { withFileTypes: true })
            .filter((entry) => entry.isFile() && entry.name.endsWith(".js"))
            .map((entry) => join(root, entry.name))
    )),
];

let hasFailure = false;

function isSafeInnerHtmlClear(line) {
    return /\.innerHTML\s*=\s*(["'`])\s*\1\s*;?\s*$/.test(line.trim());
}

function checkDomSafety(file) {
    const content = readFileSync(file, "utf8");
    const lines = content.split(/\r?\n/);
    const forbiddenPatterns = [
        { pattern: /\.outerHTML\s*=/, reason: "outerHTML assignment" },
        { pattern: /\.insertAdjacentHTML\s*\(/, reason: "insertAdjacentHTML" },
        { pattern: /\beval\s*\(/, reason: "eval()" },
        { pattern: /\bconsole\.log\s*\(/, reason: "console.log" },
    ];

    lines.forEach((line, index) => {
        if (/\.innerHTML\s*=/.test(line) && !isSafeInnerHtmlClear(line)) {
            console.error(`${file}:${index + 1}: unsafe innerHTML assignment`);
            hasFailure = true;
        }

        forbiddenPatterns.forEach(({ pattern, reason }) => {
            if (pattern.test(line)) {
                console.error(`${file}:${index + 1}: forbidden ${reason}`);
                hasFailure = true;
            }
        });
    });
}

for (const file of files) {
    const result = spawnSync(process.execPath, ["--check", file], {
        stdio: "inherit",
        shell: false,
    });

    if (result.status !== 0) {
        hasFailure = true;
    }

    checkDomSafety(file);
}

if (hasFailure) {
    process.exit(1);
}

console.log(`Checked ${files.length} JavaScript files.`);
