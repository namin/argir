#!/usr/bin/env python3
"""
Simple startup script for ARGIR web frontend.

Usage:
    python run_web.py [--port PORT] [--host HOST] [--debug]

Environment variables needed (same as CLI):
- GEMINI_API_KEY or (GOOGLE_CLOUD_PROJECT + GOOGLE_CLOUD_LOCATION)

Optional:
- LLM_MODEL (default: gemini-2.5-flash)
- CACHE_LLM (enable LLM caching)
- LLM_CACHE_DIR (default: .cache/llm)
"""

import argparse
import sys
import os

def check_environment():
    """Check if required environment variables are set"""
    has_gemini = os.getenv('GEMINI_API_KEY')
    has_vertex = os.getenv('GOOGLE_CLOUD_PROJECT')
    
    if not (has_gemini or has_vertex):
        print("❌ LLM not configured!")
        print("\nPlease set one of:")
        print("  • GEMINI_API_KEY=your_key_here")
        print("  • GOOGLE_CLOUD_PROJECT=your-project")
        print("\nOptional:")
        print("  • LLM_MODEL (default: gemini-2.5-flash)")
        print("  • CACHE_LLM=1 (enable caching)")
        print("  • LLM_CACHE_DIR=.cache/llm")
        return False
    
    if has_gemini:
        print("✓ Using Gemini API")
    else:
        print(f"✓ Using Vertex AI (Project: {os.getenv('GOOGLE_CLOUD_PROJECT')}, Location: {os.getenv('GOOGLE_CLOUD_LOCATION')})")
    
    model = os.getenv('LLM_MODEL', 'gemini-2.5-flash')
    print(f"✓ Model: {model}")
    
    if os.getenv('CACHE_LLM'):
        cache_dir = os.getenv('LLM_CACHE_DIR', '.cache/llm')
        print(f"✓ Caching enabled: {cache_dir}")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="ARGIR Web Frontend")
    parser.add_argument("--port", type=int, default=5000, help="Port to run on (default: 5000)")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    parser.add_argument("--public", action="store_true", help="Make server accessible from other machines (binds to 0.0.0.0)")
    parser.add_argument("--production", action="store_true", help="Run with Gunicorn production server")
    parser.add_argument("--workers", type=int, default=4, help="Number of Gunicorn workers (default: 4)")
    
    args = parser.parse_args()
    
    print("🚀 Starting ARGIR Web Frontend...")
    print()
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    print()
    
    # Adjust host if public access requested
    if args.public:
        args.host = "0.0.0.0"
        print(f"⚠️  Server will be accessible from other machines on port {args.port}")
    
    try:
        if args.production:
            # Run with Gunicorn production server
            print("🏭 Starting production server with Gunicorn...")
            print(f"👥 Workers: {args.workers}")
            print(f"🌐 Server: http://{args.host}:{args.port}")
            print("🔄 Press Ctrl+C to stop the server")
            print()
            
            # Check if Gunicorn is available
            import shutil
            if not shutil.which("gunicorn"):
                print("❌ Gunicorn not found. Install with: pip install gunicorn")
                sys.exit(1)
            
            # Build Gunicorn command
            cmd = [
                "gunicorn",
                "--bind", f"{args.host}:{args.port}",
                "--workers", str(args.workers),
                "--worker-class", "sync",
                "--timeout", "120",  # Longer timeout for LLM calls
                "--max-requests", "1000",
                "--max-requests-jitter", "100",
                "--preload",  # Preload app for better memory usage
                "wsgi:application"
            ]
            
            # Add logging in production
            if not args.debug:
                cmd.extend([
                    "--access-logfile", "-",
                    "--error-logfile", "-",
                    "--log-level", "info"
                ])
            
            # Run Gunicorn from the web directory
            import subprocess
            import os
            web_dir = os.path.dirname(os.path.abspath(__file__))
            subprocess.run(cmd, cwd=web_dir)
        else:
            # Run with Flask development server
            from web_frontend import app
            
            if not args.debug:
                print("⚠️  Using Flask development server (not for production)")
                print("💡 For production, use: --production flag")
            
            print(f"🌐 Starting server at http://{args.host}:{args.port}")
            print("📝 Open this URL in your browser to use the web interface")
            print("🔄 Press Ctrl+C to stop the server")
            print()
            
            app.run(
                host=args.host,
                port=args.port,
                debug=args.debug
            )
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("\nMake sure Flask is installed:")
        print("  pip install flask")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
