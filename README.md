## Introduction
Input: a song, output: karaoke video for that song GG

## Features
- Cross-platform support (Windows, macOS, Linux)
- Desktop application with modern UI (Electron-based)
- Command-line interface for advanced users
- Automatic font detection for different operating systems
- YouTube URL support for direct video downloading
- High-quality vocal separation using Demucs
- Accurate speech transcription with Whisper
- Progressive word highlighting in karaoke videos

## Desktop Application

The easiest way to use Karaoke Automate is through the desktop application:

```bash
cd karaoke-automate-desktop
npm install
npm start
```

## Command Line Usage

For advanced users, you can use the command-line interface:

```bash
# Install Python dependencies
pip install -U demucs
pip install git+https://github.com/openai/whisper.git
pip install blobfile
pip install noisereduce soundfile
pip install yt-dlp

# Run the script
python karaoke-automate-desktop/backend/main.py /path/to/your/audiofile.mp3
python karaoke-automate-desktop/backend/main.py https://www.youtube.com/watch?v=VIDEO_ID
```

## Install dependencies

For the desktop app, dependencies are managed automatically. For command-line usage:

```bash
pip install -U demucs
pip install git+https://github.com/openai/whisper.git
pip install blobfile
pip install noisereduce soundfile
pip install yt-dlp
```

## Font Installation (Optional)
The script automatically detects system fonts. For best results, install DejaVu Sans:

**macOS:**
```bash
brew install --cask font-dejavu
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update && sudo apt-get install -y fonts-dejavu-core
```

**Windows:**
Download and install from [DejaVu Fonts website](https://dejavu-fonts.github.io/)

# Project Structure

```
karaoke-automate/
├── karaoke-automate-desktop/     # Desktop application
│   ├── backend/                  # Python backend
│   │   ├── main.py              # Main processing script
│   │   ├── python_bridge.py     # IPC bridge
│   │   └── requirements.txt     # Python dependencies
│   ├── frontend/                # React frontend
│   ├── electron/                # Electron main process
│   └── package.json            # Node.js dependencies
├── venv/                        # Python virtual environment
└── README.md                   # This file
```