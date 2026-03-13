import { app, BrowserWindow, Tray, Menu, Notification, nativeImage } from 'electron';
import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as http from 'http';

const API_PORT = 8111;
const API_URL = `http://localhost:${API_PORT}`;
const POLL_INTERVAL = 5000; // 5 seconds

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let pythonProcess: ChildProcess | null = null;
let notificationPoller: ReturnType<typeof setInterval> | null = null;

const isDev = !app.isPackaged;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#0a0a0f',
    titleBarStyle: 'hiddenInset',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
    show: false,
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
  });

  // Hide window instead of closing (tray app behavior)
  mainWindow.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault();
      mainWindow?.hide();
    }
  });
}

function startPythonBackend() {
  const pythonCmd = isDev ? 'uvicorn' : path.join(process.resourcesPath, 'life-xp-server');
  const args = isDev
    ? ['life_xp.api:app', '--port', String(API_PORT), '--log-level', 'info']
    : ['--port', String(API_PORT)];

  pythonProcess = spawn(pythonCmd, args, {
    cwd: isDev ? path.join(__dirname, '../../..') : undefined,
    stdio: 'pipe',
  });

  pythonProcess.stdout?.on('data', (data: Buffer) => {
    console.log(`[Python] ${data.toString().trim()}`);
  });

  pythonProcess.stderr?.on('data', (data: Buffer) => {
    console.error(`[Python] ${data.toString().trim()}`);
  });

  pythonProcess.on('exit', (code: number | null) => {
    console.log(`Python backend exited with code ${code}`);
    if (!isQuitting) {
      // Restart after crash
      setTimeout(startPythonBackend, 2000);
    }
  });
}

async function waitForBackend(retries = 30): Promise<boolean> {
  for (let i = 0; i < retries; i++) {
    try {
      const ok = await new Promise<boolean>((resolve) => {
        http.get(`${API_URL}/api/health`, (res) => {
          resolve(res.statusCode === 200);
        }).on('error', () => resolve(false));
      });
      if (ok) return true;
    } catch {}
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

function createTray() {
  // Simple tray icon (in production, use a proper .png icon)
  const icon = nativeImage.createFromDataURL(
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAYklEQVQ4T2NkoBAwUqifAacBjP///2dhYGD4D8L4NMDkGBkZ/zMxMf0H0XgNAJkOMh1uAMh0kGkwA0AuwGcAzBZCXoC5ACZHyAVgQ5A9AXIB2BRGL4ANIeQFqF4gJCckBQBKUzcAZUd1VAAAAABJRU5ErkJggg=='
  );

  tray = new Tray(icon);
  tray.setToolTip('Life XP');

  updateTrayMenu();

  tray.on('click', () => {
    mainWindow?.show();
    mainWindow?.focus();
  });
}

async function updateTrayMenu() {
  try {
    const stats = await fetchAPI('/api/stats');
    const menu = Menu.buildFromTemplate([
      {
        label: `Lv.${stats.level} ${stats.title} — ${stats.total_xp.toLocaleString()} XP`,
        enabled: false,
      },
      { type: 'separator' },
      {
        label: 'Open Dashboard',
        click: () => {
          mainWindow?.show();
          mainWindow?.focus();
        },
      },
      { type: 'separator' },
      {
        label: 'Quit Life XP',
        click: () => {
          isQuitting = true;
          app.quit();
        },
      },
    ]);
    tray?.setContextMenu(menu);
  } catch {
    // Backend not ready yet
  }
}

async function fetchAPI(endpoint: string): Promise<any> {
  return new Promise((resolve, reject) => {
    http.get(`${API_URL}${endpoint}`, (res) => {
      let data = '';
      res.on('data', (chunk: string) => (data += chunk));
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch {
          reject(new Error('Invalid JSON'));
        }
      });
    }).on('error', reject);
  });
}

function startNotificationPolling() {
  notificationPoller = setInterval(async () => {
    try {
      const notifications = await fetchAPI('/api/notifications/pending');
      for (const n of notifications) {
        if (Notification.isSupported()) {
          const notification = new Notification({
            title: n.title,
            body: n.message,
            silent: false,
          });

          notification.on('click', () => {
            mainWindow?.show();
            mainWindow?.focus();
          });

          notification.show();
        }

        // Mark as read
        await new Promise<void>((resolve) => {
          const req = http.request(
            `${API_URL}/api/notifications/${n.id}/read`,
            { method: 'PUT' },
            () => resolve()
          );
          req.end();
        });
      }

      // Update tray menu periodically
      updateTrayMenu();
    } catch {
      // Backend might not be ready
    }
  }, POLL_INTERVAL);
}

// Track quit state outside of app object to avoid type issues
let isQuitting = false;

app.whenReady().then(async () => {
  startPythonBackend();
  createTray();
  createWindow();

  const ready = await waitForBackend();
  if (ready) {
    console.log('Backend is ready');
    startNotificationPolling();
    updateTrayMenu();
  } else {
    console.error('Backend failed to start');
  }
});

app.on('before-quit', () => {
  isQuitting = true;
  if (notificationPoller) clearInterval(notificationPoller);
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }
});

app.on('window-all-closed', () => {
  // Don't quit on macOS — keep running in tray
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (!mainWindow) {
    createWindow();
  } else {
    mainWindow.show();
  }
});
