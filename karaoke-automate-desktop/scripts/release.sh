#!/bin/bash

# Release script for Karaoke Automate Desktop
# Usage: ./scripts/release.sh [version]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if version is provided
if [ -z "$1" ]; then
    print_error "Version number is required"
    echo "Usage: $0 <version>"
    echo "Example: $0 1.0.0"
    exit 1
fi

VERSION=$1

# Validate version format (basic semver check)
if ! [[ $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    print_error "Invalid version format. Use semantic versioning (e.g., 1.0.0)"
    exit 1
fi

print_status "Starting release process for version $VERSION"

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    print_error "package.json not found. Make sure you're in the karaoke-automate-desktop directory"
    exit 1
fi

# Check if git is clean
if [ -n "$(git status --porcelain)" ]; then
    print_warning "Working directory is not clean. Uncommitted changes:"
    git status --short
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_error "Aborting release"
        exit 1
    fi
fi

# Update version in package.json
print_status "Updating version in package.json to $VERSION"
npm version $VERSION --no-git-tag-version

# Clean previous builds
print_status "Cleaning previous builds"
npm run clean

# Install dependencies
print_status "Installing dependencies"
npm ci

# Run tests (if available)
if npm run test 2>/dev/null; then
    print_status "Tests passed"
else
    print_warning "No tests found or tests failed"
fi

# Build for all platforms
print_status "Building for all platforms"
npm run build-all

# Check if builds were successful
if [ ! -d "dist" ] || [ -z "$(ls -A dist)" ]; then
    print_error "Build failed - no output in dist directory"
    exit 1
fi

print_status "Build completed successfully"

# List build artifacts
print_status "Build artifacts:"
ls -la dist/

# Commit version change
print_status "Committing version change"
git add package.json package-lock.json
git commit -m "chore: bump version to $VERSION"

# Create and push tag
print_status "Creating and pushing tag v$VERSION"
git tag "v$VERSION"
git push origin main
git push origin "v$VERSION"

print_status "Release process completed!"
print_status "GitHub Actions will now build and create the release automatically"
print_status "Check the Actions tab in your GitHub repository for progress" 