// Frontend JavaScript for Karaoke Automate Desktop App

class KaraokeApp {
    constructor() {
        this.isProcessing = false;
        this.selectedFile = null;
        this.selectedFileObject = null; // For drag-and-drop files
        this.selectedOutputDir = null;
        this.backendConnected = false;
        this.currentTheme = 'light';
        
        this.initializeElements();
        this.setupEventListeners();
        this.setupDragAndDrop();
        this.setupTheme();
        this.setupKeyboardNavigation();
        this.checkBackendConnection();
    }
    
    initializeElements() {
        // Status elements
        this.statusIndicator = document.getElementById('statusIndicator');
        this.statusText = document.getElementById('statusText');
        
        // Theme elements
        this.themeToggle = document.getElementById('themeToggle');
        this.themeIcon = document.getElementById('themeIcon');
        
        // Input elements
        this.selectFileBtn = document.getElementById('selectFileBtn');
        this.fileDropZone = document.getElementById('fileDropZone');
        this.fileDropText = document.getElementById('fileDropText');
        this.youtubeUrl = document.getElementById('youtubeUrl');
        this.urlValidationMessage = document.getElementById('url-validation-message');
        this.selectOutputBtn = document.getElementById('selectOutputBtn');
        this.outputDropZone = document.getElementById('outputDropZone');
        this.outputDropText = document.getElementById('outputDropText');
        
        // Options
        this.enhanceInstrumental = document.getElementById('enhanceInstrumental');
        this.whisperModel = document.getElementById('whisperModel');
        
        // Process button
        this.processBtn = document.getElementById('processBtn');
        
        // Progress elements
        this.progressFill = document.getElementById('progressFill');
        this.progressText = document.getElementById('progressText');
        this.progressMessage = document.getElementById('progressMessage');
    }
    
    setupEventListeners() {
        // File selection
        this.selectFileBtn.addEventListener('click', () => this.selectFile());
        this.fileDropZone.addEventListener('click', () => this.selectFile());
        this.selectOutputBtn.addEventListener('click', () => this.selectOutputDirectory());
        this.outputDropZone.addEventListener('click', () => this.selectOutputDirectory());
        
        // Theme toggle
        this.themeToggle.addEventListener('click', () => this.toggleTheme());
        
        // Process button
        this.processBtn.addEventListener('click', () => this.startProcessing());
        
        // Input validation
        this.youtubeUrl.addEventListener('input', () => this.validateYouTubeUrl());
        this.youtubeUrl.addEventListener('blur', () => this.validateYouTubeUrl());
        
        // Backend event listeners
        if (window.electronAPI) {
            window.electronAPI.onBackendStatus((data) => this.handleBackendStatus(data));
            window.electronAPI.onPythonMessage((data) => this.handlePythonMessage(data));
        }
    }
    
    setupDragAndDrop() {
        // File drop zone
        this.setupDropZone(this.fileDropZone, (files) => {
            if (files.length > 0) {
                const file = files[0];
                if (this.isValidAudioVideoFile(file)) {
                    // For drag-and-drop, we need to use the file object directly
                    // Electron will handle the file path when processing
                    this.selectedFile = file.path || file.name; // Use path if available, fallback to name
                    this.selectedFileObject = file; // Store the actual file object for processing
                    this.updateFileDropZone(this.fileDropZone, this.fileDropText, file.name, true);
                    this.youtubeUrl.value = ''; // Clear YouTube URL
                    this.clearUrlValidation();
                    this.validateInputs();
                    console.log('info', `Selected file: ${file.name}`);
                } else {
                    console.log('error', 'Invalid file type. Please select an audio or video file.');
                }
            }
        });
        
        // Output directory drop zone (for folders)
        this.setupDropZone(this.outputDropZone, (files) => {
            // Note: Electron's drag-and-drop for directories might be limited
            // This is mainly for visual feedback
            this.selectOutputDirectory();
        });
    }
    
    setupDropZone(element, onDrop) {
        let dragCounter = 0;
        
        element.addEventListener('dragenter', (e) => {
            e.preventDefault();
            dragCounter++;
            element.classList.add('drag-over');
        });
        
        element.addEventListener('dragleave', (e) => {
            e.preventDefault();
            dragCounter--;
            if (dragCounter === 0) {
                element.classList.remove('drag-over');
            }
        });
        
        element.addEventListener('dragover', (e) => {
            e.preventDefault();
        });
        
        element.addEventListener('drop', (e) => {
            e.preventDefault();
            dragCounter = 0;
            element.classList.remove('drag-over');
            
            const files = Array.from(e.dataTransfer.files);
            onDrop(files);
        });
    }
    
    setupTheme() {
        // Load saved theme preference
        const savedTheme = localStorage.getItem('karaoke-theme') || 'light';
        this.setTheme(savedTheme);
    }
    
    setupKeyboardNavigation() {
        // Add keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + D for dark mode toggle
            if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
                e.preventDefault();
                this.toggleTheme();
            }
            
            // Ctrl/Cmd + O for open file
            if ((e.ctrlKey || e.metaKey) && e.key === 'o') {
                e.preventDefault();
                this.selectFile();
            }
            
            // Enter key on drop zones
            if (e.key === 'Enter' && (e.target === this.fileDropZone || e.target === this.outputDropZone)) {
                e.preventDefault();
                e.target.click();
            }
            
            // Escape to clear selections
            if (e.key === 'Escape') {
                if (this.selectedFile) {
                    this.clearFileSelection();
                }
            }
        });
        
        // Improve tab navigation
        this.setupTabOrder();
    }
    
    setupTabOrder() {
        const focusableElements = [
            this.themeToggle,
            this.fileDropZone,
            this.selectFileBtn,
            this.youtubeUrl,
            this.outputDropZone,
            this.selectOutputBtn,
            this.enhanceInstrumental,
            this.whisperModel,
            this.processBtn
        ];
        
        focusableElements.forEach((element, index) => {
            if (element) {
                element.setAttribute('tabindex', index + 1);
            }
        });
    }
    
    toggleTheme() {
        const newTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        this.setTheme(newTheme);
    }
    
    setTheme(theme) {
        this.currentTheme = theme;
        document.documentElement.setAttribute('data-theme', theme);
        this.themeIcon.textContent = theme === 'light' ? '🌙' : '☀️';
        this.themeToggle.setAttribute('aria-label', `Switch to ${theme === 'light' ? 'dark' : 'light'} theme`);
        localStorage.setItem('karaoke-theme', theme);
        
        console.log(`Switched to ${theme} theme`);
    }
    
    validateYouTubeUrl() {
        const url = this.youtubeUrl.value.trim();
        
        if (!url) {
            this.clearUrlValidation();
            this.validateInputs();
            return;
        }
        
        if (this.isValidYouTubeUrl(url)) {
            this.showUrlValidation(true, '✓ Valid YouTube URL');
            this.selectedFile = null; // Clear file selection
            this.updateFileDropZone(this.fileDropZone, this.fileDropText, 'Drop files here or click to browse', false);
        } else {
            this.showUrlValidation(false, '✗ Please enter a valid YouTube URL');
        }
        
        this.validateInputs();
    }
    
    showUrlValidation(isValid, message) {
        this.youtubeUrl.classList.remove('valid', 'invalid');
        this.urlValidationMessage.classList.remove('valid', 'invalid');
        
        if (isValid) {
            this.youtubeUrl.classList.add('valid');
            this.urlValidationMessage.classList.add('valid');
        } else {
            this.youtubeUrl.classList.add('invalid');
            this.urlValidationMessage.classList.add('invalid');
        }
        
        this.urlValidationMessage.textContent = message;
    }
    
    clearUrlValidation() {
        this.youtubeUrl.classList.remove('valid', 'invalid');
        this.urlValidationMessage.classList.remove('valid', 'invalid');
        this.urlValidationMessage.textContent = '';
    }
    
    isValidYouTubeUrl(url) {
        const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com\/(watch\?v=|embed\/|v\/)|youtu\.be\/)[\w-]+(&[\w=]*)?$/;
        return youtubeRegex.test(url);
    }
    
    isValidAudioVideoFile(file) {
        const validExtensions = ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.mp4', '.avi', '.mov', '.mkv', '.webm'];
        const fileName = file.name.toLowerCase();
        return validExtensions.some(ext => fileName.endsWith(ext));
    }
    
    updateFileDropZone(zone, textElement, text, hasFile) {
        textElement.textContent = text;
        zone.classList.toggle('has-file', hasFile);
        
        if (hasFile) {
            zone.setAttribute('aria-label', `Selected file: ${text}`);
        } else {
            zone.setAttribute('aria-label', 'Drop files here or click to browse');
        }
    }
    
    clearFileSelection() {
        this.selectedFile = null;
        this.selectedFileObject = null;
        this.updateFileDropZone(this.fileDropZone, this.fileDropText, 'Drop files here or click to browse', false);
        this.validateInputs();
        console.log('info', 'File selection cleared');
    }
    
    async checkBackendConnection() {
        try {
            if (window.electronAPI) {
                const status = await window.electronAPI.getBackendStatus();
                this.updateBackendStatus(status.connected);
            } else {
                console.log('error', 'Electron API not available');
                this.updateBackendStatus(false);
            }
        } catch (error) {
            console.log('error', `Failed to check backend status: ${error.message}`);
            this.updateBackendStatus(false);
        }
    }
    
    updateBackendStatus(connected) {
        this.backendConnected = connected;
        
        if (connected) {
            this.statusIndicator.classList.add('connected');
            this.statusText.textContent = 'Backend connected';
            console.log('info', 'Python backend connected successfully');
        } else {
            this.statusIndicator.classList.remove('connected');
            this.statusText.textContent = 'Backend disconnected';
            console.log('error', 'Python backend not available');
        }
        
        this.validateInputs();
    }
    
    handleBackendStatus(data) {
        if (data.status === 'connected') {
            this.updateBackendStatus(true);
        } else if (data.status === 'error') {
            this.updateBackendStatus(false);
            console.log('error', data.message || 'Backend connection failed');
        }
    }
    
    handlePythonMessage(data) {
        switch (data.type) {
            case 'progress':
                this.updateProgress(data.progress, data.message);
                break;
            case 'log':
                console.log(data.level, data.message);
                break;
            case 'response':
                // This will be handled by the promise-based API calls
                break;
            default:
                console.log('Unknown Python message:', data);
        }
    }
    
    async selectFile() {
        try {
            if (!window.electronAPI) {
                throw new Error('Electron API not available');
            }
            
            const result = await window.electronAPI.selectFile();
            
            if (!result.canceled && result.filePaths.length > 0) {
                this.selectedFile = result.filePaths[0];
                this.selectedFileObject = null; // Clear file object when using browse
                const fileName = this.selectedFile.split(/[\\/]/).pop();
                this.updateFileDropZone(this.fileDropZone, this.fileDropText, fileName, true);
                
                // Clear YouTube URL when file is selected
                this.youtubeUrl.value = '';
                this.clearUrlValidation();
                
                console.log('info', `Selected file: ${fileName}`);
                this.validateInputs();
            }
        } catch (error) {
            console.log('error', `Failed to select file: ${error.message}`);
        }
    }
    
    async selectOutputDirectory() {
        try {
            if (!window.electronAPI) {
                throw new Error('Electron API not available');
            }
            
            const result = await window.electronAPI.selectOutputDirectory();
            
            if (!result.canceled && result.filePaths.length > 0) {
                this.selectedOutputDir = result.filePaths[0];
                const dirName = this.selectedOutputDir.split(/[\\/]/).pop();
                this.updateFileDropZone(this.outputDropZone, this.outputDropText, dirName, true);
                
                console.log('info', `Selected output directory: ${dirName}`);
                this.validateInputs();
            }
        } catch (error) {
            console.log('error', `Failed to select output directory: ${error.message}`);
        }
    }
    
    validateInputs() {
        // Check for input: either a selected file (path or object) or a valid YouTube URL
        const hasFileInput = this.selectedFile || this.selectedFileObject;
        const hasUrlInput = this.youtubeUrl.value.trim() && this.isValidYouTubeUrl(this.youtubeUrl.value.trim());
        const hasInput = hasFileInput || hasUrlInput;
        const hasOutput = this.selectedOutputDir;
        const canProcess = hasInput && hasOutput && this.backendConnected && !this.isProcessing;
        
        this.processBtn.disabled = !canProcess;
        
        // Update button text and ARIA attributes
        if (canProcess) {
            this.processBtn.textContent = 'Create Karaoke Video';
            this.processBtn.setAttribute('aria-describedby', 'process-help');
        } else if (this.isProcessing) {
            this.processBtn.textContent = 'Processing...';
            this.processBtn.setAttribute('aria-describedby', 'process-help');
        } else if (!this.backendConnected) {
            this.processBtn.textContent = 'Backend Not Connected';
            this.processBtn.setAttribute('aria-label', 'Cannot process: backend not connected');
        } else if (!hasInput) {
            this.processBtn.textContent = 'Select File or Enter URL';
            this.processBtn.setAttribute('aria-label', 'Cannot process: no input selected');
        } else if (!hasOutput) {
            this.processBtn.textContent = 'Select Output Directory';
            this.processBtn.setAttribute('aria-label', 'Cannot process: no output directory selected');
        }
        
        // Update progress bar ARIA attributes
        this.updateProgressAria();
    }
    
    updateProgressAria() {
        const progressBar = document.querySelector('.progress-bar');
        const currentProgress = parseInt(this.progressText.textContent) || 0;
        progressBar.setAttribute('aria-valuenow', currentProgress);
        
        if (this.isProcessing) {
            progressBar.setAttribute('aria-label', `Processing: ${currentProgress}% complete`);
        } else {
            progressBar.setAttribute('aria-label', 'Processing progress');
        }
    }
    
    async startProcessing() {
        if (this.isProcessing || !this.backendConnected) {
            return;
        }
        
        try {
            this.isProcessing = true;
            this.validateInputs();
            
            // Prepare processing data
            const processingData = {
                output_dir: this.selectedOutputDir,
                options: {
                    enhance_instrumental: this.enhanceInstrumental.checked,
                    whisper_model: this.whisperModel.value
                }
            };
            
            // Add input source
            if (this.selectedFile || this.selectedFileObject) {
                if (this.selectedFile) {
                    // File selected via browse button
                    processingData.input_file = this.selectedFile;
                    console.log('info', `Starting processing with file: ${this.selectedFile.split(/[\\/]/).pop()}`);
                } else if (this.selectedFileObject) {
                    // File selected via drag-and-drop
                    processingData.input_file = this.selectedFileObject.path || this.selectedFileObject.name;
                    processingData.file_object = this.selectedFileObject; // Pass the file object for Electron to handle
                    console.log('info', `Starting processing with file: ${this.selectedFileObject.name}`);
                }
            } else if (this.youtubeUrl.value.trim()) {
                processingData.youtube_url = this.youtubeUrl.value.trim();
                console.log('info', `Starting processing with YouTube URL: ${processingData.youtube_url}`);
            } else {
                throw new Error('No input source specified');
            }
            
            console.log('info', 'Sending processing request to backend...');
            this.updateProgress(0, 'Initializing...');
            
            // Start processing
            const result = await window.electronAPI.processAudio(processingData);
            
            // Processing completed successfully
            this.updateProgress(100, 'Processing completed successfully!');
            console.log('info', `Karaoke video created: ${result.output_video}`);
            console.log('info', `Vocal track: ${result.vocal_track}`);
            console.log('info', `Instrumental track: ${result.instrumental_track}`);
            console.log('info', `Transcription: ${result.transcription}`);
            
            // Show success message
            this.showCompletionMessage(result);
            
        } catch (error) {
            console.log('error', `Processing failed: ${error.message}`);
            this.updateProgress(0, 'Processing failed');
        } finally {
            this.isProcessing = false;
            this.validateInputs();
        }
    }
    
    updateProgress(percentage, message = '') {
        this.progressFill.style.width = `${percentage}%`;
        this.progressText.textContent = `${Math.round(percentage)}%`;
        
        if (message) {
            this.progressMessage.textContent = message;
        }
        
        // Add processing animation
        if (percentage > 0 && percentage < 100) {
            this.progressFill.classList.add('processing');
        } else {
            this.progressFill.classList.remove('processing');
        }
        
        // Update ARIA attributes
        this.updateProgressAria();
        
        // Announce progress to screen readers at key milestones
        if (percentage === 25 || percentage === 50 || percentage === 75 || percentage === 100) {
            this.announceToScreenReader(`Processing ${percentage}% complete`);
        }
    }
    
    announceToScreenReader(message) {
        const announcement = document.createElement('div');
        announcement.setAttribute('aria-live', 'assertive');
        announcement.setAttribute('aria-atomic', 'true');
        announcement.className = 'sr-only';
        announcement.textContent = message;
        
        document.body.appendChild(announcement);
        
        // Remove after announcement
        setTimeout(() => {
            document.body.removeChild(announcement);
        }, 1000);
    }
    
    showCompletionMessage(result) {
        // Create a temporary success message
        const successDiv = document.createElement('div');
        successDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--success-color);
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            box-shadow: var(--shadow);
            z-index: 1000;
            max-width: 300px;
            font-weight: 600;
        `;
        successDiv.innerHTML = `
            <div>✅ Karaoke video created successfully!</div>
            <div style="font-size: 12px; margin-top: 5px; opacity: 0.9;">
                Check your output directory for the results.
            </div>
        `;
        
        // Add ARIA attributes for accessibility
        successDiv.setAttribute('role', 'alert');
        successDiv.setAttribute('aria-live', 'assertive');
        
        document.body.appendChild(successDiv);
        
        // Announce to screen readers
        this.announceToScreenReader('Karaoke video created successfully! Check your output directory for the results.');
        
        // Remove after 5 seconds
        setTimeout(() => {
            if (successDiv.parentNode) {
                successDiv.parentNode.removeChild(successDiv);
            }
        }, 5000);
    }
}

// Initialize the app when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.karaokeApp = new KaraokeApp();
});

// Handle any unhandled errors
window.addEventListener('error', (event) => {
    if (window.karaokeApp) {
        window.karaokeApp.log('error', `Unhandled error: ${event.error.message}`);
    }
});

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', (event) => {
    if (window.karaokeApp) {
        window.karaokeApp.log('error', `Unhandled promise rejection: ${event.reason}`);
    }
});