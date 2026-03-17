const { contextBridge } = require("electron");

// Expose a safe API to the renderer
contextBridge.exposeInMainWorld("lifeXP", {
  apiBase: "http://127.0.0.1:5175",
});
