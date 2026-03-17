const { app, BrowserWindow, shell, ipcMain } = require("electron");
const path = require("path");
const http = require("http");

// ── Protocol registration ─────────────────────────────────────────
// In development, register the protocol with an explicit app path so
// macOS doesn't launch a plain Electron shell window.
if (!app.isPackaged) {
  const appPathArg = path.resolve(process.argv[1] || app.getAppPath());
  app.setAsDefaultProtocolClient("lifexp", process.execPath, [appPathArg]);
} else {
  app.setAsDefaultProtocolClient("lifexp");
}

// ── Single-instance lock (Windows / Linux deep-link support) ─────
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
  process.exit(0);
}

// ── State ─────────────────────────────────────────────────────────
let mainWindow = null;
let pendingDeepLink = null;

function parseLifeXpDeepLink(rawUrl) {
  if (!rawUrl) return null;
  try {
    const parsed = new URL(rawUrl);
    if ((parsed.protocol || "").toLowerCase() !== "lifexp:") return null;
    return parsed;
  } catch {
    return null;
  }
}

function getDeepLinkRoute(parsed) {
  const host = (parsed.hostname || "").toLowerCase();
  const pathname = ((parsed.pathname || "").toLowerCase() || "/").replace(/\/+$/, "") || "/";
  return host ? `/${host}${pathname}` : pathname;
}

function findDeepLinkArg(args = []) {
  return args.find((arg) => /^lifexp:\/\//i.test(arg)) || null;
}

// ── Deep-link handler ─────────────────────────────────────────────
function handleDeepLink(url) {
  const parsed = parseLifeXpDeepLink(url);
  if (!parsed) return;

  if (!mainWindow || mainWindow.isDestroyed()) {
    pendingDeepLink = url;
    return;
  }

  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.focus();

  // Notify renderer immediately so it can show a "completing…" state
  mainWindow.webContents.send("deep-link", url);

  // Parse and forward OAuth callbacks to the Python backend
  if (getDeepLinkRoute(parsed) === "/oauth/callback") {
    const code  = parsed.searchParams.get("code");
    const state = parsed.searchParams.get("state");
    if (!code) return;

    const body = JSON.stringify({ url, code, state });
    const req = http.request(
      {
        hostname: "127.0.0.1",
        port: 5175,
        path: "/api/oauth/exchange",
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(body),
        },
      },
      (res) => {
        let data = "";
        res.on("data", (chunk) => { data += chunk; });
        res.on("end", () => {
          try {
            const result = JSON.parse(data);
            if (mainWindow && !mainWindow.isDestroyed()) {
              mainWindow.webContents.send("oauth-result", result);
            }
          } catch {}
        });
      }
    );
    req.on("error", (err) => {
      console.error("[deep-link] OAuth exchange error:", err.message);
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send("oauth-result", { ok: false, error: err.message });
      }
    });
    req.write(body);
    req.end();
  }
}

// macOS — deep link when app is already running
app.on("open-url", (event, url) => {
  event.preventDefault();
  handleDeepLink(url);
});

// macOS — deep link when app launches cold (URL arrives as argv on Windows/Linux)
app.on("second-instance", (_, commandLine) => {
  const url = findDeepLinkArg(commandLine);
  if (url) handleDeepLink(url);
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

// ── IPC ───────────────────────────────────────────────────────────
ipcMain.handle("open-external", (_, url) => shell.openExternal(url));

// ── Window ────────────────────────────────────────────────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 750,
    minWidth: 800,
    minHeight: 600,
    titleBarStyle: "hiddenInset",
    backgroundColor: "#0a0a0b",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
  });

  mainWindow.loadFile(path.join(__dirname, "..", "renderer", "index.html"));

  mainWindow.webContents.on("did-finish-load", () => {
    // Flush any deep link that arrived before the window was ready
    if (pendingDeepLink) {
      handleDeepLink(pendingDeepLink);
      pendingDeepLink = null;
    }
  });

  // Open <a target="_blank"> and window.open() in the system browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

app.whenReady().then(() => {
  // Check if launched via cold deep-link (macOS passes it as argv on first launch too)
  const coldUrl = findDeepLinkArg(process.argv);
  if (coldUrl) pendingDeepLink = coldUrl;

  createWindow();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
