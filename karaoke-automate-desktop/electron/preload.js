const { contextBridge, ipcRenderer } = require("electron");

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld("electronAPI", {
    // File operations
    selectFile: () => ipcRenderer.invoke("select-file"),
    selectOutputDirectory: () => ipcRenderer.invoke("select-output-directory"),
    
    // Python backend communication
    processAudio: (data) => ipcRenderer.invoke("process-audio", data),
    getBackendStatus: () => ipcRenderer.invoke("get-backend-status"),
    
    // Auto-updater
    checkForUpdates: () => ipcRenderer.invoke("check-for-updates"),
    downloadUpdate: () => ipcRenderer.invoke("download-update"),
    quitAndInstall: () => ipcRenderer.invoke("quit-and-install"),
    
    // Event listeners
    onBackendStatus: (callback) => {
        ipcRenderer.on("backend-status", (event, data) => callback(data));
    },
    onPythonMessage: (callback) => {
        ipcRenderer.on("python-message", (event, data) => callback(data));
    },
    onUpdateStatus: (callback) => {
        ipcRenderer.on("update-status", (event, data) => callback(data));
    },
    
    // Remove listeners
    removeAllListeners: (channel) => {
        ipcRenderer.removeAllListeners(channel);
    },
    
    // Platform info
    platform: process.platform,
    
    // Development mode check
    isDev: process.env.ELECTRON_IS_DEV === "1"
}); 