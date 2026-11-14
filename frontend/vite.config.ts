import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const EVAL_RUNS_DIR = path.resolve(__dirname, "..", "eval", "runs");
const SAFE_ID_RE = /^[A-Za-z0-9_-]+$/;

function devEvalRunsPlugin(): Plugin {
  return {
    name: "dev-eval-runs",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use("/__eval_runs", (req, res) => {
        if (req.method !== "GET" && req.method !== "HEAD") {
          res.statusCode = 404;
          res.end("Not found");
          return;
        }
        const rawUrl = (req.url || "").split("?")[0];
        const parts = rawUrl.replace(/^\/+/, "").split("/");
        if (parts.length !== 3) {
          res.statusCode = 404;
          res.end("Not found");
          return;
        }
        const [run, clip, filename] = parts;
        if (
          !SAFE_ID_RE.test(run) ||
          !SAFE_ID_RE.test(clip) ||
          (filename !== "results.json" && filename !== "output.mp4")
        ) {
          res.statusCode = 404;
          res.end("Not found");
          return;
        }

        const targetPath = path.resolve(EVAL_RUNS_DIR, run, clip, filename);
        const rel = path.relative(EVAL_RUNS_DIR, targetPath);
        if (rel.startsWith("..") || path.isAbsolute(rel)) {
          res.statusCode = 404;
          res.end("Not found");
          return;
        }

        let stat: fs.Stats;
        try {
          stat = fs.statSync(targetPath);
          if (!stat.isFile()) {
            res.statusCode = 404;
            res.end("Not found");
            return;
          }
        } catch {
          res.statusCode = 404;
          res.end("Not found");
          return;
        }

        if (filename === "results.json") {
          res.statusCode = 200;
          res.setHeader("Content-Type", "application/json; charset=utf-8");
          res.setHeader("Content-Length", String(stat.size));
          if (req.method === "HEAD") {
            res.end();
            return;
          }
          fs.createReadStream(targetPath).pipe(res);
          return;
        }

        // output.mp4 with HTTP Range request support
        const totalSize = stat.size;
        const rangeHeader = req.headers.range;
        res.setHeader("Accept-Ranges", "bytes");
        res.setHeader("Content-Type", "video/mp4");

        if (rangeHeader) {
          const match = /^bytes=(\d*)-(\d*)$/.exec(rangeHeader.trim());
          if (!match) {
            res.statusCode = 416;
            res.setHeader("Content-Range", `bytes */${totalSize}`);
            res.end();
            return;
          }
          const start = match[1] ? parseInt(match[1], 10) : 0;
          const end = match[2] ? parseInt(match[2], 10) : totalSize - 1;
          if (
            Number.isNaN(start) ||
            Number.isNaN(end) ||
            start > end ||
            start >= totalSize
          ) {
            res.statusCode = 416;
            res.setHeader("Content-Range", `bytes */${totalSize}`);
            res.end();
            return;
          }
          const clampedEnd = Math.min(end, totalSize - 1);
          const chunkLen = clampedEnd - start + 1;
          res.statusCode = 206;
          res.setHeader(
            "Content-Range",
            `bytes ${start}-${clampedEnd}/${totalSize}`,
          );
          res.setHeader("Content-Length", String(chunkLen));
          if (req.method === "HEAD") {
            res.end();
            return;
          }
          fs.createReadStream(targetPath, { start, end: clampedEnd }).pipe(res);
          return;
        }

        res.statusCode = 200;
        res.setHeader("Content-Length", String(totalSize));
        if (req.method === "HEAD") {
          res.end();
          return;
        }
        fs.createReadStream(targetPath).pipe(res);
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), devEvalRunsPlugin()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
    },
  },
});
