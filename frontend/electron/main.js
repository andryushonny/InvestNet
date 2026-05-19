'use strict';

const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const net = require('net');
const http = require('http');
const log = require('electron-log/main');

log.transports.file.level = 'info';
log.initialize();

let backendProcess = null;
let backendPort = 0;
let mainWindow = null;
const isDev = process.env.NODE_ENV === 'development';

function pickFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on('error', reject);
    srv.listen(0, '127.0.0.1', () => {
      const port = srv.address().port;
      srv.close(() => resolve(port));
    });
  });
}

function backendExecPath() {
  const exeName = process.platform === 'win32' ? 'backend.exe' : 'backend';
  if (isDev) {
    return path.join(__dirname, '..', '..', 'backend-dist', 'backend', exeName);
  }
  return path.join(process.resourcesPath, 'backend', exeName);
}

function waitForHealth(port, timeoutMs = 30000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const tick = () => {
      const req = http.get(`http://127.0.0.1:${port}/api/v1/healthz`, (res) => {
        if (res.statusCode === 200) return resolve();
        retry();
      });
      req.on('error', retry);
      function retry() {
        if (Date.now() - start > timeoutMs) return reject(new Error('backend health timeout'));
        setTimeout(tick, 400);
      }
    };
    tick();
  });
}

async function startBackend() {
  const exe = backendExecPath();
  if (!fs.existsSync(exe)) {
    throw new Error(`backend executable not found: ${exe}`);
  }
  backendPort = await pickFreePort();
  const userData = app.getPath('userData');
  fs.mkdirSync(path.join(userData, 'logs'), { recursive: true });
  log.info(`spawn backend ${exe} --port ${backendPort} --data-dir ${userData}`);
  backendProcess = spawn(exe, ['--port', String(backendPort), '--data-dir', userData], {
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  });
  const logStream = fs.createWriteStream(path.join(userData, 'logs', 'backend.log'), { flags: 'a' });
  backendProcess.stdout.pipe(logStream);
  backendProcess.stderr.pipe(logStream);
  backendProcess.on('exit', (code) => log.warn(`backend exited code=${code}`));
  await waitForHealth(backendPort);
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    backgroundColor: '#0b0d12',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist-renderer', 'index.html'));
  }
}

ipcMain.handle('backend:port', () => backendPort);

ipcMain.handle('dialog:openFile', async (_, opts) => {
  const r = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: opts?.filters || [],
  });
  return r.canceled ? null : r.filePaths[0];
});

ipcMain.handle('shell:openExternal', (_, url) => shell.openExternal(url));
ipcMain.handle('shell:openMailto', (_, payload) => {
  const url = `mailto:${encodeURIComponent(payload.to || '')}?subject=${encodeURIComponent(payload.subject || '')}&body=${encodeURIComponent(payload.body || '')}`;
  return shell.openExternal(url);
});

app.whenReady().then(async () => {
  try {
    await startBackend();
    createWindow();
  } catch (e) {
    log.error('startup error', e);
    dialog.showErrorBox('InvestNet — backend error', String(e && e.message || e));
    app.quit();
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  if (backendProcess) {
    try { backendProcess.kill(); } catch (_) {}
  }
});
