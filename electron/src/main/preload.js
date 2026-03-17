const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("lifeXP", {
  apiBase: "http://127.0.0.1:5175",

  // Called when a lifexp:// URL is intercepted — receives the full URL string
  onDeepLink: (cb) => {
    ipcRenderer.on("deep-link", (_, url) => cb(url));
  },

  // Called when the Python backend finishes exchanging the OAuth code
  onOAuthResult: (cb) => {
    ipcRenderer.on("oauth-result", (_, result) => cb(result));
  },

  // Open a URL in the system browser (used to kick off OAuth flows)
  openExternal: (url) => ipcRenderer.invoke("open-external", url),
});
