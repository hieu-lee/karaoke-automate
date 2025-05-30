# Build Documentation

This document explains how to build and package the Karaoke Automate desktop application for different platforms.

## Prerequisites

### Development Environment
- **Node.js** 18+ with npm
- **Python** 3.10+ with pip
- **Git** for version control

### Platform-Specific Requirements

#### macOS
- **Xcode Command Line Tools**: `xcode-select --install`
- **Code Signing Certificate** (optional, for distribution)

#### Windows
- **Visual Studio Build Tools** or **Visual Studio Community**
- **Windows SDK**

#### Linux
- **Build essentials**: `sudo apt-get install build-essential`
- **Additional libraries**: `sudo apt-get install libnss3-dev libatk-bridge2.0-dev libdrm2 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libxss1 libasound2-dev`

## Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd karaoke-automate
   ```

2. **Set up Python environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Install Node.js dependencies**:
   ```bash
   cd karaoke-automate-desktop
   npm install
   ```

## Build Commands

### Development Build
```bash
npm run start          # Start in development mode
npm run electron-dev   # Alternative development command
```

### Production Builds

#### Current Platform
```bash
npm run build          # Build for current platform
npm run dist           # Alias for build
```

#### Specific Platforms
```bash
npm run build-mac      # Build for macOS
npm run build-win      # Build for Windows
npm run build-linux    # Build for Linux
```

#### All Platforms (requires platform-specific tools)
```bash
npm run build-all      # Build for all platforms
npm run dist-all       # Alias for build-all
```

### Utility Commands
```bash
npm run clean          # Clean build artifacts
```

## Build Outputs

### macOS
- **DMG**: `dist/Karaoke Automate-{version}-{arch}.dmg`
- **ZIP**: `dist/Karaoke Automate-{version}-{arch}-mac.zip`

### Windows
- **NSIS Installer**: `dist/Karaoke Automate Setup {version}.exe`
- **Portable**: `dist/Karaoke Automate {version}.exe`

### Linux
- **AppImage**: `dist/Karaoke Automate-{version}.AppImage`
- **DEB Package**: `dist/karaoke-automate_{version}_amd64.deb`
- **RPM Package**: `dist/karaoke-automate-{version}.x86_64.rpm`

## CI/CD

### GitHub Actions
The project includes automated builds via GitHub Actions:

- **Triggers**: Push to main/develop, pull requests, version tags
- **Platforms**: macOS, Windows, Linux
- **Artifacts**: Automatically uploaded for each platform
- **Releases**: Auto-created for version tags

### Manual Release Process
1. Update version in `package.json`
2. Create and push a version tag:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
3. GitHub Actions will automatically build and create a release

## Code Signing

### macOS
- Set up Apple Developer account
- Install certificates in Keychain
- Configure `CSC_LINK` and `CSC_KEY_PASSWORD` environment variables

### Windows
- Obtain code signing certificate
- Configure `CSC_LINK` and `CSC_KEY_PASSWORD` environment variables

## Troubleshooting

### Common Issues

#### Python Dependencies
- Ensure virtual environment is activated
- Check Python version compatibility
- Install platform-specific dependencies

#### Node.js Build Errors
- Clear node_modules: `rm -rf node_modules && npm install`
- Check Node.js version compatibility
- Ensure all native dependencies are installed

#### Platform-Specific Builds
- Install platform-specific build tools
- Check electron-builder documentation for requirements
- Verify code signing setup (if applicable)

### Build Size Optimization
- The Python virtual environment is packaged with the app
- Consider using `pip install --no-deps` for production builds
- Exclude unnecessary files in `package.json` build configuration

## Security Considerations

- Code signing is recommended for distribution
- Entitlements are configured for macOS security requirements
- Network permissions are included for YouTube download functionality
- File system permissions are configured for audio/video processing

## Performance Notes

- First build may take longer due to dependency downloads
- Subsequent builds use cached dependencies
- Cross-platform builds require significant disk space
- Consider using build servers for CI/CD to avoid local resource usage 