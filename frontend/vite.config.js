import { execSync } from "node:child_process";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
function currentBuild() {
    try {
        return execSync("git rev-parse --short HEAD", {
            cwd: process.cwd(),
            encoding: "utf8",
            stdio: ["ignore", "pipe", "ignore"],
        }).trim();
    }
    catch (_a) {
        return "dev";
    }
}
export default defineConfig({
    plugins: [react()],
    define: {
        __APP_BUILD__: JSON.stringify(currentBuild()),
    },
    server: {
        host: "0.0.0.0",
        port: 5173,
    },
});
