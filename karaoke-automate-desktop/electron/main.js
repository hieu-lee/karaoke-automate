const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const AutoUpdater = require("./auto-updater");

let mainWindow;
let pythonProcess = null;
let autoUpdater = null;

// Python process management
function startPythonBackend() {
    console.log("Starting Python backend...");
    
    // Determine Python executable path
    const isDev = process.env.ELECTRON_IS_DEV === "1";
    let pythonPath;
    let scriptPath;
    
    if (isDev) {
        // Development mode - use system Python with venv
        pythonPath = process.platform === "win32" ? 
            path.join(__dirname, "../../venv/Scripts/python.exe") :
            path.join(__dirname, "../../venv/bin/python");
        scriptPath = path.join(__dirname, "../backend/python_bridge.py");
    } else {
        // Production mode - use bundled Python
        pythonPath = process.platform === "win32" ? 
            path.join(process.resourcesPath, "python/Scripts/python.exe") :
            path.join(process.resourcesPath, "python/bin/python");
        scriptPath = path.join(process.resourcesPath, "backend/python_bridge.py");
    }
    
    console.log(`Python path: ${pythonPath}`);
    console.log(`Script path: ${scriptPath}`);
    
    // Check if Python executable exists
    if (!fs.existsSync(pythonPath)) {
        console.error(`Python executable not found at: ${pythonPath}`);
        return false;
    }
    
    // Check if script exists
    if (!fs.existsSync(scriptPath)) {
        console.error(`Python script not found at: ${scriptPath}`);
        return false;
    }
    
    try {
        pythonProcess = spawn(pythonPath, [scriptPath], {
            stdio: ["pipe", "pipe", "pipe"],
            cwd: isDev ? path.join(__dirname, "../..") : process.resourcesPath
        });
        
        pythonProcess.stdout.on("data", (data) => {
            const message = data.toString().trim();
            console.log(`Python stdout: ${message}`);
            
            // Parse JSON messages from Python
            message.split('\n').forEach((line) => {
                if (line.trim().startsWith("{")) {
                    try {
                        const jsonMessage = JSON.parse(line);
                        // Send all messages to frontend for UI updates (progress, logs, etc.)
                        if (mainWindow && !mainWindow.isDestroyed()) {
                            mainWindow.webContents.send("python-message", jsonMessage);
                        }
                        // Additionally, if this is a response message, emit it to ipcMain
                        // so the promise-based handler can receive it
                        if (jsonMessage.type === "response") {
                            ipcMain.emit("python-response", null, jsonMessage);
                        }
                    } catch (e) {
                        console.log("JSON parse error:", e);
                        console.log(`Python log: ${line}`);
                    }
                }
            });
        });
        
        pythonProcess.stderr.on("data", (data) => {
            console.error(`Python stderr: ${data.toString()}`);
        });
        
        pythonProcess.on("close", (code) => {
            console.log(`Python process exited with code ${code}`);
            pythonProcess = null;
        });
        
        pythonProcess.on("error", (error) => {
            console.error(`Failed to start Python process: ${error}`);
            pythonProcess = null;
        });
        
        console.log("Python backend started successfully");
        return true;
    } catch (error) {
        console.error(`Error starting Python backend: ${error}`);
        return false;
    }
}

function stopPythonBackend() {
    if (pythonProcess) {
        console.log("Stopping Python backend...");
        pythonProcess.kill();
        pythonProcess = null;
    }
}

function sendToPython(message) {
    if (pythonProcess && pythonProcess.stdin.writable) {
        pythonProcess.stdin.write(JSON.stringify(message) + "\n");
        return true;
    }
    return false;
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            enableRemoteModule: false,
            preload: path.join(__dirname, "preload.js")
        },
        icon: path.join(__dirname, "../assets/icon.png") // Optional: add app icon
    });
    
    mainWindow.loadFile("frontend/index.html");
    
    // Open DevTools in development
    if (process.env.ELECTRON_IS_DEV === "1") {
        mainWindow.webContents.openDevTools();
    }
    
    mainWindow.on("closed", () => {
        mainWindow = null;
    });
    
    // Start Python backend after window is ready
    mainWindow.webContents.once("did-finish-load", () => {
        const success = startPythonBackend();
        if (success) {
            mainWindow.webContents.send("backend-status", { status: "connected" });
        } else {
            mainWindow.webContents.send("backend-status", { status: "error", message: "Failed to start Python backend" });
        }
        
        // Initialize auto-updater (only in production)
        if (process.env.ELECTRON_IS_DEV !== "1") {
            autoUpdater = new AutoUpdater(mainWindow);
        }
    });
}

// IPC handlers
ipcMain.handle("process-audio", async (event, data) => {
    return new Promise((resolve, reject) => {
        if (!pythonProcess) {
            reject(new Error("Python backend not available"));
            return;
        }
        
        const requestId = Date.now().toString();
        const message = {
            type: "process_audio",
            id: requestId,
            data: data
        };
        
        // Set up response handler
        const responseHandler = (event, response) => {
            if (response.id === requestId) {
                ipcMain.removeListener("python-response", responseHandler);
                if (response.success) {
                    resolve(response.data);
                } else {
                    reject(new Error(response.error));
                }
            }
        };
        
        ipcMain.on("python-response", responseHandler);
        
        // Send request to Python
        if (!sendToPython(message)) {
            ipcMain.removeListener("python-response", responseHandler);
            reject(new Error("Failed to send message to Python backend"));
        }
        
        // Timeout after 5 minutes
        setTimeout(() => {
            ipcMain.removeListener("python-response", responseHandler);
            reject(new Error("Request timeout"));
        }, 300000);
    });
});

ipcMain.handle("select-file", async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
        properties: ["openFile"],
        filters: [
            { name: "Audio Files", extensions: ["mp3", "wav", "flac", "m4a", "aac"] },
            { name: "Video Files", extensions: ["mp4", "avi", "mov", "mkv"] },
            { name: "All Files", extensions: ["*"] }
        ]
    });
    
    return result;
});

ipcMain.handle("select-output-directory", async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
        properties: ["openDirectory"]
    });
    
    return result;
});

ipcMain.handle("get-backend-status", async () => {
    return {
        connected: pythonProcess !== null,
        pid: pythonProcess ? pythonProcess.pid : null
    };
});

// Auto-updater IPC handlers
ipcMain.handle("check-for-updates", async () => {
    if (autoUpdater) {
        autoUpdater.checkForUpdates();
        return { success: true };
    }
    return { success: false, error: "Auto-updater not available" };
});

ipcMain.handle("download-update", async () => {
    if (autoUpdater) {
        autoUpdater.downloadUpdate();
        return { success: true };
    }
    return { success: false, error: "Auto-updater not available" };
});

ipcMain.handle("quit-and-install", async () => {
    if (autoUpdater) {
        autoUpdater.quitAndInstall();
        return { success: true };
    }
    return { success: false, error: "Auto-updater not available" };
});

// Handle Python responses
ipcMain.on("python-response", (event, response) => {
    // This will be handled by the promise-based handlers above
});

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
    stopPythonBackend();
    if (process.platform !== "darwin") {
        app.quit();
    }
});

app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});

app.on("before-quit", () => {
    stopPythonBackend();
});
