import express from "express";
import { spawn } from "child_process";
import path from "path";
import proxy from "express-http-proxy";
import { createServer as createViteServer } from "vite";

async function startServer() {
  const app = express();
  const PORT = 3000;
  const pythonExecutable =
    process.env.PYTHON_EXECUTABLE ||
    (process.platform === "win32" ? "c:/python313/python.exe" : "python3");

  // Start the route-enabled Python FastAPI backend on port 3001.
  const pythonProcess = spawn(pythonExecutable, ["-m", "app.api.server"], {
    stdio: "inherit",
    cwd: process.cwd(),
    env: { ...process.env, PORT: "3001" }
  });

  pythonProcess.on("error", (err) => {
    console.error("Failed to start Python backend:", err);
  });

  // API Proxy
  app.use("/api", proxy("http://localhost:3001", {
    proxyReqPathResolver: (req) => "/api" + req.url,
    // Critical for file uploads: pass request body through without pre-parsing.
    parseReqBody: false
  }));

  // Vite middleware for development
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
      root: path.join(process.cwd(), "frontend")
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "frontend", "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Full-stack server running on http://localhost:${PORT}`);
  });
}

startServer();
