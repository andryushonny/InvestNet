'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('investnet', {
  backendPort: () => ipcRenderer.invoke('backend:port'),
  openFile: (opts) => ipcRenderer.invoke('dialog:openFile', opts),
  openExternal: (url) => ipcRenderer.invoke('shell:openExternal', url),
  openMailto: (payload) => ipcRenderer.invoke('shell:openMailto', payload),
});
