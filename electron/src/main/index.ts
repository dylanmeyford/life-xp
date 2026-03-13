import { app, BrowserWindow, Tray, Notification, nativeImage, screen } from 'electron';
import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as http from 'http';

const API_PORT = 8111;
const API_URL = `http://localhost:${API_PORT}`;
const POLL_INTERVAL = 5000;

const TRAY_WIDTH = 380;
const TRAY_HEIGHT = 560;

let mainWindow: BrowserWindow | null = null;
let trayWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let pythonProcess: ChildProcess | null = null;
let notificationPoller: ReturnType<typeof setInterval> | null = null;
let isQuitting = false;

const isDev = !app.isPackaged;

function getRendererURL(route: string): string {
  if (isDev) {
    return `http://localhost:5173/#${route}`;
  }
  return `file://${path.join(__dirname, '../renderer/index.html')}#${route}`;
}

function createMainWindow() {
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

  mainWindow.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault();
      mainWindow?.hide();
    }
  });
}

function createTrayWindow() {
  trayWindow = new BrowserWindow({
    width: TRAY_WIDTH,
    height: TRAY_HEIGHT,
    show: false,
    frame: false,
    resizable: false,
    movable: false,
    fullscreenable: false,
    skipTaskbar: true,
    transparent: true,
    hasShadow: true,
    alwaysOnTop: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // Load the tray route
  if (isDev) {
    trayWindow.loadURL('http://localhost:5173/#/tray');
  } else {
    trayWindow.loadFile(path.join(__dirname, '../renderer/index.html'), {
      hash: '/tray',
    });
  }

  trayWindow.on('blur', () => {
    trayWindow?.hide();
  });
}

function toggleTrayWindow() {
  if (!trayWindow) return;

  if (trayWindow.isVisible()) {
    trayWindow.hide();
    return;
  }

  positionTrayWindow();
  trayWindow.show();
  trayWindow.focus();
}

function positionTrayWindow() {
  if (!tray || !trayWindow) return;

  const trayBounds = tray.getBounds();
  const windowBounds = trayWindow.getBounds();
  const display = screen.getDisplayNearestPoint({
    x: trayBounds.x,
    y: trayBounds.y,
  });

  // Center horizontally under tray icon, anchor to top of screen (macOS menu bar)
  let x = Math.round(trayBounds.x + trayBounds.width / 2 - windowBounds.width / 2);
  let y = Math.round(trayBounds.y + trayBounds.height + 4);

  // Keep within screen bounds
  const maxX = display.workArea.x + display.workArea.width - windowBounds.width;
  const maxY = display.workArea.y + display.workArea.height - windowBounds.height;
  x = Math.min(Math.max(x, display.workArea.x), maxX);
  y = Math.min(y, maxY);

  trayWindow.setPosition(x, y, false);
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
  const icon = nativeImage.createFromDataURL(
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAYklEQVQ4T2NkoBAwUqifAacBjP///2dhYGD4D8L4NMDkGBkZ/zMxMf0H0XgNAJkOMh1uAMh0kGkwA0AuwGcAzBZCXoC5ACZHyAVgQ5A9AXIB2BRGL4ANIeQFqF4gJCckBQBKUzcAZUd1VAAAAABJRU5ErkJggg=='
  );

  tray = new Tray(icon);
  tray.setToolTip('Life XP');

  tray.on('click', () => {
    toggleTrayWindow();
  });

  // Right-click shows minimal context menu
  tray.on('right-click', () => {
    const { Menu } = require('electron');
    const menu = Menu.buildFromTemplate([
      {
        label: 'Open Full Dashboard',
        click: () => {
          mainWindow?.show();
          mainWindow?.focus();
        },
      },
      { type: 'separator' as const },
      {
        label: 'Quit Life XP',
        click: () => {
          isQuitting = true;
          app.quit();
        },
      },
    ]);
    tray?.popUpContextMenu(menu);
  });
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
            toggleTrayWindow();
          });

          notification.show();
        }

        await new Promise<void>((resolve) => {
          const req = http.request(
            `${API_URL}/api/notifications/${n.id}/read`,
            { method: 'PUT' },
            () => resolve()
          );
          req.end();
        });
      }
    } catch {
      // Backend might not be ready
    }
  }, POLL_INTERVAL);
}

app.whenReady().then(async () => {
  startPythonBackend();
  createTray();
  createTrayWindow();
  createMainWindow();

  const ready = await waitForBackend();
  if (ready) {
    console.log('Backend is ready');
    startNotificationPolling();
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
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (!mainWindow) {
    createMainWindow();
  } else {
    mainWindow.show();
  }
});
