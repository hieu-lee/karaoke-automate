# Karaoke Automate Desktop Application

A cross-platform desktop application for creating karaoke videos from audio files and YouTube URLs using Electron and Python.

## Architecture Overview

This application uses a hybrid architecture combining:
- **Electron** for the desktop UI and main process
- **Python** for audio processing backend (Whisper, Demucs, etc.)
- **IPC (Inter-Process Communication)** bridge for secure communication

## Phase 1.3 Implementation: Python Backend Integration

### Components

#### 1. Electron Main Process (`electron/main.js`)
- Manages the application window and lifecycle
- Spawns and manages the Python subprocess
- Handles IPC communication between frontend and Python backend
- Provides secure file dialog APIs
- Implements proper security with context isolation

#### 2. Preload Script (`electron/preload.js`)
- Exposes secure APIs to the renderer process
- Implements the context bridge for IPC communication
- Prevents direct Node.js access from the frontend

#### 3. Python Bridge (`backend/python_bridge.py`)
- Handles JSON-based communication with Electron
- Wraps the main karaoke processing functions
- Provides progress updates and logging
- Runs processing tasks in separate threads

#### 4. Frontend Application (`frontend/`)
- Modern web-based UI built with HTML/CSS/JavaScript
- Real-time progress tracking and logging
- File selection and processing options
- Responsive design with status indicators

### IPC Communication Flow

```
Frontend (Renderer) ←→ Preload Script ←→ Main Process ←→ Python Bridge
```

1. **Frontend** sends requests via `window.electronAPI`
2. **Preload script** validates and forwards to main process
3. **Main process** communicates with Python via stdin/stdout
4. **Python bridge** processes requests and sends responses
5. **Responses** flow back through the same chain

### Message Types

#### From Electron to Python:
- `process_audio` - Start karaoke video creation
- `ping` - Health check
- `get_status` - Get backend status
- `stop` - Graceful shutdown

#### From Python to Electron:
- `response` - Request completion/error
- `progress` - Processing progress updates
- `log` - Log messages with levels (info, warning, error)

### Security Features

- **Context Isolation**: Renderer process cannot access Node.js APIs directly
- **Preload Script**: Only exposes necessary APIs to frontend
- **Input Validation**: All IPC messages are validated
- **Process Isolation**: Python runs in separate subprocess

### Development vs Production

#### Development Mode
- Uses system Python with virtual environment
- Python path: `../venv/bin/python`
- Script path: `../backend/python_bridge.py`
- DevTools enabled

#### Production Mode
- Uses bundled Python environment
- Python path: `resources/python/bin/python`
- Script path: `resources/backend/python_bridge.py`
- Optimized for distribution

## File Structure

```
karaoke-automate-desktop/
├── electron/
│   ├── main.js          # Main Electron process
│   └── preload.js       # Security bridge
├── frontend/
│   ├── index.html       # Main UI
│   └── app.js          # Frontend logic
├── backend/
│   ├── python_bridge.py # Python IPC bridge
│   └── test_bridge.py   # Bridge test suite
├── package.json         # Node.js dependencies
└── README.md           # This file
```

## Running the Application

### Development
```bash
cd karaoke-automate-desktop
npm start
```

### Building for Distribution
```bash
npm run build        # Current platform
npm run build-all    # All platforms
```

## Testing

### Test Python Bridge
```bash
cd karaoke-automate
python karaoke-automate-desktop/backend/test_bridge.py
```

### Test Electron App
```bash
cd karaoke-automate-desktop
npm start
```

## Dependencies

### Node.js Dependencies
- `electron` - Desktop application framework
- `electron-builder` - Application packaging

### Python Dependencies
- All dependencies from the main `requirements.txt`
- Standard library modules: `json`, `threading`, `subprocess`

## Error Handling

The application implements comprehensive error handling:

1. **Python Process Failures**: Automatic detection and user notification
2. **IPC Communication Errors**: Timeout handling and retry logic
3. **File Access Errors**: Proper error messages and fallbacks
4. **Processing Errors**: Detailed error reporting with logs

## Logging

Multi-level logging system:
- **Frontend**: Browser console and UI log panel
- **Electron**: Console output with timestamps
- **Python**: Structured JSON logging to Electron

## Next Steps (Phase 1.4)

- Set up electron-builder configuration
- Configure CI/CD for automated builds
- Test packaging on all platforms (Windows, macOS, Linux)
- Optimize Python environment bundling
- Add code signing for distribution 