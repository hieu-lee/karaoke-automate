#!/usr/bin/env node

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// Colors for console output
const colors = {
    reset: '\x1b[0m',
    bright: '\x1b[1m',
    red: '\x1b[31m',
    green: '\x1b[32m',
    yellow: '\x1b[33m',
    blue: '\x1b[34m',
    magenta: '\x1b[35m',
    cyan: '\x1b[36m'
};

function log(message, color = 'reset') {
    console.log(`${colors[color]}${message}${colors.reset}`);
}

function execCommand(command, description) {
    log(`\n${description}...`, 'cyan');
    try {
        execSync(command, { stdio: 'inherit' });
        log(`✅ ${description} completed successfully`, 'green');
    } catch (error) {
        log(`❌ ${description} failed`, 'red');
        throw error;
    }
}

function checkPrerequisites() {
    log('🔍 Checking prerequisites...', 'yellow');
    
    // Check if we're in the right directory
    if (!fs.existsSync('package.json')) {
        throw new Error('package.json not found. Please run this script from the karaoke-automate-desktop directory.');
    }
    
    // Check if node_modules exists
    if (!fs.existsSync('node_modules')) {
        log('📦 Installing dependencies...', 'cyan');
        execSync('npm install', { stdio: 'inherit' });
    }
    
    // Check if Python backend exists
    if (!fs.existsSync('backend/main.py')) {
        throw new Error('Python backend (main.py) not found in backend directory.');
    }
    
    // Check if virtual environment exists
    if (!fs.existsSync('../venv')) {
        throw new Error('Python virtual environment not found. Please set up the Python environment first.');
    }
    
    log('✅ All prerequisites met', 'green');
}

function cleanBuild() {
    log('🧹 Cleaning previous builds...', 'yellow');
    if (fs.existsSync('dist')) {
        execCommand('rm -rf dist', 'Removing dist directory');
    }
    if (fs.existsSync('build/output')) {
        execCommand('rm -rf build/output', 'Removing build output directory');
    }
}

function buildForPlatform(platform) {
    const platformCommands = {
        'mac': 'npm run build-mac',
        'win': 'npm run build-win',
        'linux': 'npm run build-linux',
        'all': 'npm run build-all'
    };
    
    if (!platformCommands[platform]) {
        throw new Error(`Unknown platform: ${platform}`);
    }
    
    execCommand(platformCommands[platform], `Building for ${platform}`);
}

function createChecksums() {
    log('🔐 Creating checksums...', 'cyan');
    
    const distDir = 'dist';
    if (!fs.existsSync(distDir)) {
        log('⚠️  No dist directory found, skipping checksums', 'yellow');
        return;
    }
    
    const files = fs.readdirSync(distDir).filter(file => {
        const ext = path.extname(file).toLowerCase();
        return ['.dmg', '.exe', '.deb', '.rpm', '.AppImage', '.zip'].includes(ext);
    });
    
    if (files.length === 0) {
        log('⚠️  No distributable files found, skipping checksums', 'yellow');
        return;
    }
    
    const checksumFile = path.join(distDir, 'checksums.txt');
    let checksumContent = '# Karaoke Automate - File Checksums\n\n';
    
    files.forEach(file => {
        const filePath = path.join(distDir, file);
        try {
            const checksum = execSync(`shasum -a 256 "${filePath}"`, { encoding: 'utf8' }).trim();
            checksumContent += `${checksum}\n`;
            log(`✅ Checksum created for ${file}`, 'green');
        } catch (error) {
            log(`❌ Failed to create checksum for ${file}`, 'red');
        }
    });
    
    fs.writeFileSync(checksumFile, checksumContent);
    log(`📝 Checksums saved to ${checksumFile}`, 'green');
}

function generateReleaseNotes() {
    log('📋 Generating release notes...', 'cyan');
    
    const packageJson = JSON.parse(fs.readFileSync('package.json', 'utf8'));
    const version = packageJson.version;
    
    const releaseNotes = `# Karaoke Automate v${version}

## 🎵 Features
- Create karaoke videos from audio files and YouTube URLs
- Advanced vocal separation using Demucs
- Automatic transcription with OpenAI Whisper
- Cross-platform desktop application (Windows, macOS, Linux)
- Modern, accessible user interface

## 📦 Downloads
Choose the appropriate package for your operating system:

### Windows
- **karaoke-automate-${version}.exe** - Windows installer (recommended)
- **karaoke-automate-${version}-portable.exe** - Portable version

### macOS
- **karaoke-automate-${version}.dmg** - macOS installer (Intel & Apple Silicon)
- **karaoke-automate-${version}-mac.zip** - macOS app bundle

### Linux
- **karaoke-automate-${version}.AppImage** - Universal Linux package
- **karaoke-automate-${version}.deb** - Debian/Ubuntu package
- **karaoke-automate-${version}.rpm** - Red Hat/Fedora package

## 🔐 Verification
Verify your download using the checksums in \`checksums.txt\`:
\`\`\`bash
shasum -a 256 -c checksums.txt
\`\`\`

## 🚀 Installation
1. Download the appropriate package for your system
2. Install using your system's package manager or run the installer
3. Launch Karaoke Automate from your applications menu

## 📋 System Requirements
- **Windows**: Windows 10 or later (64-bit)
- **macOS**: macOS 10.15 or later (Intel or Apple Silicon)
- **Linux**: Ubuntu 18.04+ or equivalent (64-bit)
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 2GB free space for installation + space for processing files

## 🐛 Known Issues
- First launch may take longer as dependencies are initialized
- Large video files may require significant processing time
- Internet connection required for YouTube URL processing

## 📞 Support
- Report issues: [GitHub Issues](https://github.com/your-username/karaoke-automate/issues)
- Documentation: [README.md](https://github.com/your-username/karaoke-automate/blob/main/README.md)
`;

    fs.writeFileSync('dist/RELEASE_NOTES.md', releaseNotes);
    log('📝 Release notes generated', 'green');
}

function main() {
    const args = process.argv.slice(2);
    const platform = args[0] || 'all';
    
    log('🎵 Karaoke Automate Build Script', 'bright');
    log('================================', 'bright');
    
    try {
        checkPrerequisites();
        cleanBuild();
        buildForPlatform(platform);
        createChecksums();
        generateReleaseNotes();
        
        log('\n🎉 Build completed successfully!', 'green');
        log('📦 Check the dist/ directory for your distributable files', 'cyan');
        
    } catch (error) {
        log(`\n💥 Build failed: ${error.message}`, 'red');
        process.exit(1);
    }
}

if (require.main === module) {
    main();
}

module.exports = { main, buildForPlatform, createChecksums }; 