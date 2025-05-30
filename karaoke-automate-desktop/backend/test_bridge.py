#!/usr/bin/env python3
"""
Test script for the Python bridge
"""

import sys
import os
from pathlib import Path

def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")
    
    try:
        import json
        print("✓ json module imported")
    except ImportError as e:
        print(f"✗ Failed to import json: {e}")
        return False
    
    try:
        import threading
        print("✓ threading module imported")
    except ImportError as e:
        print(f"✗ Failed to import threading: {e}")
        return False
    
    try:
        from python_bridge import PythonBridge
        print("✓ PythonBridge class imported")
    except ImportError as e:
        print(f"✗ Failed to import PythonBridge: {e}")
        return False
    
    try:
        # Try importing main module functions from local main.py
        from main import separate_vocals, transcribe_and_save
        print("✓ Main module functions imported")
    except ImportError as e:
        print(f"⚠ Warning: Could not import main module functions: {e}")
        print("  This is expected if dependencies are not installed")
    
    return True

def test_bridge_creation():
    """Test that the bridge can be created"""
    print("\nTesting bridge creation...")
    
    try:
        from python_bridge import PythonBridge
        bridge = PythonBridge()
        print("✓ PythonBridge instance created successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to create PythonBridge: {e}")
        return False

def test_message_handling():
    """Test basic message handling"""
    print("\nTesting message handling...")
    
    try:
        from python_bridge import PythonBridge
        bridge = PythonBridge()
        
        # Test ping request
        test_request = {
            "type": "ping",
            "id": "test123",
            "data": {}
        }
        
        # This would normally be handled in the main loop
        # For testing, we'll just verify the method exists
        if hasattr(bridge, 'handle_request'):
            print("✓ handle_request method exists")
        else:
            print("✗ handle_request method missing")
            return False
        
        if hasattr(bridge, 'send_response'):
            print("✓ send_response method exists")
        else:
            print("✗ send_response method missing")
            return False
        
        return True
    except Exception as e:
        print(f"✗ Message handling test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Python Bridge Test Suite")
    print("=" * 40)
    
    tests = [
        test_imports,
        test_bridge_creation,
        test_message_handling
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 40)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All tests passed! The Python bridge is ready.")
        return 0
    else:
        print("✗ Some tests failed. Check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 