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

function validateVersion(version) {
    const versionRegex = /^v?\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?$/;
    return versionRegex.test(version);
}

function updatePackageVersion(version) {
    const packageJsonPath = 'package.json';
    const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
    
    // Remove 'v' prefix if present
    const cleanVersion = version.startsWith('v') ? version.slice(1) : version;
    packageJson.version = cleanVersion;
    
    fs.writeFileSync(packageJsonPath, JSON.stringify(packageJson, null, 2) + '\n');
    log(`📝 Updated package.json version to ${cleanVersion}`, 'green');
}

function createGitTag(version) {
    // Ensure version has 'v' prefix for git tag
    const tagVersion = version.startsWith('v') ? version : `v${version}`;
    
    execCommand(`git add package.json`, 'Staging package.json changes');
    execCommand(`git commit -m "Bump version to ${tagVersion}"`, 'Committing version bump');
    execCommand(`git tag ${tagVersion}`, 'Creating git tag');
    execCommand(`git push origin main`, 'Pushing changes to main branch');
    execCommand(`git push origin ${tagVersion}`, 'Pushing tag to remote');
}

function checkGitStatus() {
    try {
        const status = execSync('git status --porcelain', { encoding: 'utf8' });
        if (status.trim()) {
            log('⚠️  Warning: You have uncommitted changes:', 'yellow');
            console.log(status);
            
            const readline = require('readline');
            const rl = readline.createInterface({
                input: process.stdin,
                output: process.stdout
            });
            
            return new Promise((resolve) => {
                rl.question('Do you want to continue? (y/N): ', (answer) => {
                    rl.close();
                    if (answer.toLowerCase() !== 'y') {
                        log('❌ Deployment cancelled', 'red');
                        process.exit(1);
                    }
                    resolve();
                });
            });
        }
    } catch (error) {
        log('⚠️  Could not check git status', 'yellow');
    }
}

function generateChangelog(version) {
    log('📋 Generating changelog...', 'cyan');
    
    try {
        // Get commits since last tag
        const lastTag = execSync('git describe --tags --abbrev=0 2>/dev/null || echo "HEAD"', { encoding: 'utf8' }).trim();
        const commits = execSync(`git log ${lastTag}..HEAD --oneline --no-merges`, { encoding: 'utf8' }).trim();
        
        if (commits) {
            const changelogPath = 'CHANGELOG.md';
            let changelog = '';
            
            if (fs.existsSync(changelogPath)) {
                changelog = fs.readFileSync(changelogPath, 'utf8');
            } else {
                changelog = '# Changelog\n\nAll notable changes to this project will be documented in this file.\n\n';
            }
            
            const date = new Date().toISOString().split('T')[0];
            const newEntry = `## [${version}] - ${date}\n\n### Changes\n${commits.split('\n').map(line => `- ${line}`).join('\n')}\n\n`;
            
            // Insert new entry after the header
            const lines = changelog.split('\n');
            const headerEnd = lines.findIndex(line => line.startsWith('## '));
            if (headerEnd === -1) {
                changelog += newEntry;
            } else {
                lines.splice(headerEnd, 0, ...newEntry.split('\n'));
                changelog = lines.join('\n');
            }
            
            fs.writeFileSync(changelogPath, changelog);
            log(`📝 Updated ${changelogPath}`, 'green');
        }
    } catch (error) {
        log('⚠️  Could not generate changelog', 'yellow');
    }
}

async function main() {
    const args = process.argv.slice(2);
    const version = args[0];
    const skipBuild = args.includes('--skip-build');
    const dryRun = args.includes('--dry-run');
    
    log('🚀 Karaoke Automate Deployment Script', 'bright');
    log('====================================', 'bright');
    
    if (!version) {
        log('❌ Please provide a version number', 'red');
        log('Usage: npm run deploy <version> [--skip-build] [--dry-run]', 'yellow');
        log('Example: npm run deploy v1.0.0', 'yellow');
        process.exit(1);
    }
    
    if (!validateVersion(version)) {
        log('❌ Invalid version format. Use semantic versioning (e.g., v1.0.0)', 'red');
        process.exit(1);
    }
    
    try {
        // Check git status
        await checkGitStatus();
        
        // Update package.json version
        if (!dryRun) {
            updatePackageVersion(version);
            generateChangelog(version);
        }
        
        // Build the application
        if (!skipBuild) {
            if (!dryRun) {
                execCommand('node scripts/build.js all', 'Building application for all platforms');
            } else {
                log('🔍 [DRY RUN] Would build application for all platforms', 'yellow');
            }
        } else {
            log('⏭️  Skipping build step', 'yellow');
        }
        
        // Create git tag and push
        if (!dryRun) {
            createGitTag(version);
            log('🏷️  Git tag created and pushed', 'green');
            log('🚀 GitHub Actions will now build and create the release automatically', 'cyan');
        } else {
            log('🔍 [DRY RUN] Would create git tag and push to trigger release', 'yellow');
        }
        
        log('\n🎉 Deployment process completed!', 'green');
        log('📦 Check GitHub Actions for build progress', 'cyan');
        log('🔗 Release will be available at: https://github.com/your-username/karaoke-automate/releases', 'cyan');
        
    } catch (error) {
        log(`\n💥 Deployment failed: ${error.message}`, 'red');
        process.exit(1);
    }
}

if (require.main === module) {
    main();
}

module.exports = { main, validateVersion, updatePackageVersion }; 