#!/usr/bin/env python3
"""
Quick launcher for the GUI Pipeline
Performs basic checks before starting the GUI
"""

import sys
import os
from pathlib import Path

def check_requirements():
    """Check if all requirements are met"""
    issues = []
    
    # Check for .env file
    if not Path('.env').exists():
        issues.append("⚠️  .env file not found - YouTube API key may be missing")
    
    # Check for channels.csv
    if not Path('channels.csv').exists():
        issues.append("⚠️  channels.csv not found - please create this file")
    
    # Check for required packages
    try:
        import tkinter
    except ImportError:
        issues.append("❌ tkinter not available - please install Python with tkinter support")
        return False, issues
    
    try:
        import googleapiclient
    except ImportError:
        issues.append("❌ google-api-python-client not installed - run: pip install -r requirements.txt")
        return False, issues
    
    try:
        import youtube_transcript_api
    except ImportError:
        issues.append("❌ youtube-transcript-api not installed - run: pip install -r requirements.txt")
        return False, issues
    
    try:
        from dotenv import load_dotenv
    except ImportError:
        issues.append("❌ python-dotenv not installed - run: pip install -r requirements.txt")
        return False, issues
    
    # Return True if no critical issues (only warnings allowed)
    critical = any('❌' in issue for issue in issues)
    return not critical, issues

def main():
    """Main launcher"""
    print("="*60)
    print("YouTube Caption Extraction GUI Launcher")
    print("="*60)
    print()
    
    # Check requirements
    print("Checking requirements...")
    can_run, issues = check_requirements()
    
    if issues:
        print()
        for issue in issues:
            print(issue)
        print()
    
    if not can_run:
        print("❌ Cannot start GUI due to missing requirements")
        print("Please install required packages:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    
    if issues:
        print("⚠️  Some warnings detected, but GUI can start")
        print()
    else:
        print("✓ All checks passed")
        print()
    
    # Launch GUI
    print("Launching GUI...")
    print("="*60)
    print()
    
    try:
        from gui_main import main as gui_main
        gui_main()
    except KeyboardInterrupt:
        print("\n\nGUI closed by user")
    except Exception as e:
        print(f"\n❌ Error starting GUI: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
