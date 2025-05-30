const { autoUpdater } = require('electron-updater');
const { dialog, BrowserWindow } = require('electron');
const log = require('electron-log');

class AutoUpdater {
    constructor(mainWindow) {
        this.mainWindow = mainWindow;
        this.setupLogging();
        this.setupAutoUpdater();
    }

    setupLogging() {
        // Configure logging
        log.transports.file.level = 'info';
        autoUpdater.logger = log;
        autoUpdater.logger.transports.file.level = 'info';
    }

    setupAutoUpdater() {
        // Configure auto-updater
        autoUpdater.checkForUpdatesAndNotify();
        
        // Set update server URL (GitHub releases)
        autoUpdater.setFeedURL({
            provider: 'github',
            owner: 'your-github-username', // Replace with actual GitHub username
            repo: 'karaoke-automate'
        });

        // Auto-updater events
        autoUpdater.on('checking-for-update', () => {
            log.info('Checking for update...');
            this.sendStatusToWindow('Checking for updates...');
        });

        autoUpdater.on('update-available', (info) => {
            log.info('Update available:', info);
            this.sendStatusToWindow('Update available');
            this.showUpdateAvailableDialog(info);
        });

        autoUpdater.on('update-not-available', (info) => {
            log.info('Update not available:', info);
            this.sendStatusToWindow('App is up to date');
        });

        autoUpdater.on('error', (err) => {
            log.error('Error in auto-updater:', err);
            this.sendStatusToWindow('Error checking for updates');
        });

        autoUpdater.on('download-progress', (progressObj) => {
            let log_message = "Download speed: " + progressObj.bytesPerSecond;
            log_message = log_message + ' - Downloaded ' + progressObj.percent + '%';
            log_message = log_message + ' (' + progressObj.transferred + "/" + progressObj.total + ')';
            log.info(log_message);
            this.sendStatusToWindow('Downloading update: ' + Math.round(progressObj.percent) + '%');
        });

        autoUpdater.on('update-downloaded', (info) => {
            log.info('Update downloaded:', info);
            this.sendStatusToWindow('Update downloaded');
            this.showUpdateDownloadedDialog(info);
        });
    }

    sendStatusToWindow(text) {
        if (this.mainWindow && this.mainWindow.webContents) {
            this.mainWindow.webContents.send('update-status', text);
        }
    }

    async showUpdateAvailableDialog(info) {
        const response = await dialog.showMessageBox(this.mainWindow, {
            type: 'info',
            title: 'Update Available',
            message: `A new version (${info.version}) is available!`,
            detail: 'Would you like to download and install it now?',
            buttons: ['Download Now', 'Later'],
            defaultId: 0,
            cancelId: 1
        });

        if (response.response === 0) {
            autoUpdater.downloadUpdate();
        }
    }

    async showUpdateDownloadedDialog(info) {
        const response = await dialog.showMessageBox(this.mainWindow, {
            type: 'info',
            title: 'Update Ready',
            message: `Update (${info.version}) has been downloaded.`,
            detail: 'The application will restart to apply the update.',
            buttons: ['Restart Now', 'Later'],
            defaultId: 0,
            cancelId: 1
        });

        if (response.response === 0) {
            autoUpdater.quitAndInstall();
        }
    }

    checkForUpdates() {
        autoUpdater.checkForUpdatesAndNotify();
    }

    downloadUpdate() {
        autoUpdater.downloadUpdate();
    }

    quitAndInstall() {
        autoUpdater.quitAndInstall();
    }
}

module.exports = AutoUpdater; 