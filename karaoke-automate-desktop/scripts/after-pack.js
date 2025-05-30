const path = require('path');
const fs = require('fs');
const { fixPythonSymlinks } = require('./fix-python-symlinks');

exports.default = async function(context) {
    console.log('Running after-pack script...');
    
    const { electronPlatformName, appOutDir } = context;
    
    let resourcesPath;
    if (electronPlatformName === 'darwin') {
        resourcesPath = path.join(appOutDir, 'Karaoke Automate.app', 'Contents', 'Resources');
    } else if (electronPlatformName === 'win32') {
        resourcesPath = path.join(appOutDir, 'resources');
    } else {
        resourcesPath = path.join(appOutDir, 'resources');
    }
    
    const pythonDir = path.join(resourcesPath, 'python');
    const backendDir = path.join(resourcesPath, 'backend');
    
    console.log('Resources path:', resourcesPath);
    console.log('Python directory:', pythonDir);
    console.log('Backend directory:', backendDir);
    
    // Fix Python symlinks
    if (fs.existsSync(pythonDir)) {
        console.log('Fixing Python symlinks...');
        fixPythonSymlinks(pythonDir);
    } else {
        console.warn('Python directory not found:', pythonDir);
    }
    
    // Verify backend files
    if (fs.existsSync(backendDir)) {
        console.log('Backend directory found');
        const pythonBridge = path.join(backendDir, 'python_bridge.py');
        if (fs.existsSync(pythonBridge)) {
            console.log('python_bridge.py found');
        } else {
            console.warn('python_bridge.py not found in backend directory');
        }
    } else {
        console.warn('Backend directory not found:', backendDir);
    }
    
    console.log('After-pack script completed');
}; 