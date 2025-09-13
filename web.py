#!/usr/bin/env python3
"""
Simple launcher for ARGIR web frontend.

Usage:
    python web.py                    # Development server
    python web.py --production       # Production server
    python web.py --help            # Show all options
"""

import sys
import os

def main():
    # Import the full launcher from web directory
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'web'))
    
    try:
        from run_web import main as web_main
        web_main()
    except ImportError as e:
        print(f"❌ Error importing web frontend: {e}")
        print("\nMake sure Flask and Gunicorn are installed:")
        print("  pip install flask gunicorn")
        sys.exit(1)

if __name__ == "__main__":
    main()
