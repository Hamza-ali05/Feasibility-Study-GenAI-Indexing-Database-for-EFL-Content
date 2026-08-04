/**
 * Create a stub for stylis-plugin-rtl's missing source map target.
 * Harmless; only prevents CRA source-map-loader ENOENT warnings.
 */
const fs = require("fs");
const path = require("path");

const targetDir = path.join(__dirname, "..", "node_modules", "stylis-plugin-rtl", "src");
const targetFile = path.join(targetDir, "stylis-rtl.ts");

const stub = `export default function stylisPluginRtl() {\n  return undefined;\n}\n`;

try {
  if (!fs.existsSync(path.join(__dirname, "..", "node_modules", "stylis-plugin-rtl"))) {
    process.exit(0);
  }
  fs.mkdirSync(targetDir, { recursive: true });
  if (!fs.existsSync(targetFile)) {
    fs.writeFileSync(targetFile, stub, "utf8");
  }
} catch (_) {
  // never fail npm install because of this cosmetic fix
}
