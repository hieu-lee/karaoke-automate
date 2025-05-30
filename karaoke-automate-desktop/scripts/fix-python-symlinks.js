const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

function fixPythonSymlinks(pythonDir) {
    const binDir = path.join(pythonDir, 'bin');
    
    if (!fs.existsSync(binDir)) {
        console.log('Python bin directory not found:', binDir);
        return;
    }
    
    const pythonSymlink = path.join(binDir, 'python');
    const python3Symlink = path.join(binDir, 'python3');
    
    try {
        // Get the actual Python executable path
        const actualPythonPath = execSync('which python3', { encoding: 'utf8' }).trim();
        
        if (fs.existsSync(pythonSymlink) && fs.lstatSync(pythonSymlink).isSymbolicLink()) {
            console.log('Fixing python symlink...');
            fs.unlinkSync(pythonSymlink);
            fs.copyFileSync(actualPythonPath, pythonSymlink);
            fs.chmodSync(pythonSymlink, 0o755);
        }
        
        if (fs.existsSync(python3Symlink) && fs.lstatSync(python3Symlink).isSymbolicLink()) {
            console.log('Fixing python3 symlink...');
            fs.unlinkSync(python3Symlink);
            fs.copyFileSync(actualPythonPath, python3Symlink);
            fs.chmodSync(python3Symlink, 0o755);
        }
        
        console.log('Python symlinks fixed successfully');
    } catch (error) {
        console.error('Error fixing Python symlinks:', error.message);
    }
}

// If called directly
if (require.main === module) {
    const pythonDir = process.argv[2];
    if (!pythonDir) {
        console.error('Usage: node fix-python-symlinks.js <python-directory>');
        process.exit(1);
    }
    fixPythonSymlinks(pythonDir);
}

module.exports = { fixPythonSymlinks }; 