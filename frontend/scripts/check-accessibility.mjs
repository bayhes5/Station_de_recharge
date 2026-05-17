import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const htmlFiles = [
    ...readdirSync(".")
        .filter((name) => name.endsWith(".html"))
        .map((name) => join(".", name)),
    join("..", "raspberry", "app", "index.html"),
];

let hasFailure = false;

function report(file, message) {
    console.error(`${file}: ${message}`);
    hasFailure = true;
}

function decodeText(value) {
    return String(value || "")
        .replace(/<[^>]+>/g, " ")
        .replace(/&nbsp;/g, " ")
        .replace(/&[a-zA-Z0-9#]+;/g, "x")
        .replace(/\s+/g, " ")
        .trim();
}

function attributeValue(attributes, name) {
    const pattern = new RegExp(`\\b${name}\\s*=\\s*["']([^"']*)["']`, "i");
    return attributes.match(pattern)?.[1] || "";
}

function hasAttribute(attributes, name) {
    return new RegExp(`\\b${name}(\\s|=|$)`, "i").test(attributes);
}

function isHiddenControl(attributes) {
    return (
        hasAttribute(attributes, "hidden")
        || attributeValue(attributes, "type").toLowerCase() === "hidden"
        || attributeValue(attributes, "aria-hidden").toLowerCase() === "true"
    );
}

function hasWrappedLabel(html, startIndex) {
    const before = html.slice(0, startIndex);
    const labelStart = before.lastIndexOf("<label");
    if (labelStart === -1) return false;

    const nextLabelStart = html.indexOf("<label", labelStart + 1);
    const labelEnd = html.indexOf("</label>", labelStart);
    return labelEnd > startIndex && (nextLabelStart === -1 || nextLabelStart > startIndex);
}

function checkDocumentLandmarks(file, html) {
    if (!/<html\b[^>]*\blang\s*=\s*["']fr["']/i.test(html)) {
        report(file, "la balise html doit declarer lang=\"fr\"");
    }
    if (!/<meta\b[^>]*name\s*=\s*["']viewport["']/i.test(html)) {
        report(file, "la page doit declarer une meta viewport");
    }
    if (!/<title>\s*[^<]+\s*<\/title>/i.test(html)) {
        report(file, "la page doit declarer un titre");
    }
    if (!/<main\b/i.test(html)) {
        report(file, "la page doit contenir un landmark main");
    }
    if (!/<h1\b/i.test(html)) {
        report(file, "la page doit contenir un h1");
    }
    if (/\btabindex\s*=\s*["']?[1-9]/i.test(html)) {
        report(file, "les tabindex positifs sont interdits");
    }
    if (/\son[a-z]+\s*=/i.test(html)) {
        report(file, "les gestionnaires inline on* sont interdits");
    }
}

function checkButtons(file, html) {
    const buttonPattern = /<button\b([^>]*)>([\s\S]*?)<\/button>/gi;
    for (const match of html.matchAll(buttonPattern)) {
        const [, attributes, content] = match;
        if (isHiddenControl(attributes)) continue;
        const label = decodeText(content)
            || attributeValue(attributes, "aria-label")
            || attributeValue(attributes, "title");
        if (!label) {
            report(file, `bouton sans libelle accessible pres de ${match.index}`);
        }
    }
}

function checkLinks(file, html) {
    const linkPattern = /<a\b([^>]*)>([\s\S]*?)<\/a>/gi;
    for (const match of html.matchAll(linkPattern)) {
        const [, attributes, content] = match;
        if (!attributeValue(attributes, "href")) {
            report(file, `lien sans href pres de ${match.index}`);
        }
        const label = decodeText(content)
            || attributeValue(attributes, "aria-label")
            || attributeValue(attributes, "title");
        if (!label) {
            report(file, `lien sans libelle accessible pres de ${match.index}`);
        }
    }
}

function checkFields(file, html) {
    const fieldPattern = /<(input|select|textarea)\b([^>]*)>/gi;
    for (const match of html.matchAll(fieldPattern)) {
        const [, tagName, attributes] = match;
        if (isHiddenControl(attributes)) continue;
        if (attributeValue(attributes, "aria-label") || attributeValue(attributes, "aria-labelledby")) {
            continue;
        }

        const id = attributeValue(attributes, "id");
        if (id && new RegExp(`<label\\b[^>]*for\\s*=\\s*["']${id}["']`, "i").test(html)) {
            continue;
        }

        if (hasWrappedLabel(html, match.index)) {
            continue;
        }

        report(file, `${tagName} sans label accessible pres de ${match.index}`);
    }
}

function checkImages(file, html) {
    const imagePattern = /<img\b([^>]*)>/gi;
    for (const match of html.matchAll(imagePattern)) {
        const attributes = match[1];
        const hidden = attributeValue(attributes, "aria-hidden").toLowerCase() === "true";
        if (!hidden && !hasAttribute(attributes, "alt")) {
            report(file, `image sans attribut alt pres de ${match.index}`);
        }
    }
}

for (const file of htmlFiles) {
    const html = readFileSync(file, "utf8");
    checkDocumentLandmarks(file, html);
    checkButtons(file, html);
    checkLinks(file, html);
    checkFields(file, html);
    checkImages(file, html);
}

if (hasFailure) {
    process.exit(1);
}

process.stdout.write(`Checked accessibility basics for ${htmlFiles.length} HTML files.\n`);
