# ARGIR Web Frontend

A simple web-based interface for the ARGIR argument analysis pipeline.

## Quick Start

1. **Install dependencies** (if not already installed):
   ```bash
   pip install flask gunicorn
   ```

2. **Configure LLM** (same as CLI - choose one):
   ```bash
   # Option 1: Gemini API
   export GEMINI_API_KEY=your_key_here
   
   # Option 2: Vertex AI
   export GOOGLE_CLOUD_PROJECT=your-project-id
   ```

3. **Start the web server**:
   ```bash
   # Development mode (Flask dev server)
   python web.py
   
   # Production mode (Gunicorn)
   python web.py --production
   ```

4. **Open your browser** to: http://127.0.0.1:5000

## Features

- **Simple Interface**: Clean, mobile-responsive web form for text input
- **All CLI Options**: Support for defeasible FOL mode, goal selection, and soft pipeline
- **Soft Pipeline**: Two-stage extraction for more robust argument analysis
- **Rich Results**: Human-readable reports, argument graphs, FOL output, and debug info
- **API Endpoint**: Programmatic access via `/api/process`
- **Examples**: Built-in example arguments to get started

## Usage

### Web Interface

1. Enter your natural language argument text
2. Optional settings:
   - Set a specific goal node ID for FOL conjecture
   - Enable defeasible FOL mode (exceptions as negated conditions)
   - Enable soft pipeline for more robust extraction
   - Set number of samples (1-10) when using soft pipeline
3. Click "Analyze Arguments" to process
4. View comprehensive results including:
   - Human-readable analysis report
   - Structured argument graph (JSON)
   - First-Order Logic (TPTP format)
   - Analysis findings and semantics
   - Debug information

### API Access

Send POST requests to `/api/process`:

```bash
# Standard pipeline
curl -X POST http://localhost:5000/api/process \
  -H "Content-Type: application/json" \
  -d '{
    "text": "If it rains, the streets get wet. It is raining. So, the streets will get wet.",
    "fol_mode": "classical",
    "goal_id": null
  }'

# Soft pipeline with multiple samples
curl -X POST http://localhost:5000/api/process \
  -H "Content-Type: application/json" \
  -d '{
    "text": "If it rains, the streets get wet. It is raining. So, the streets will get wet.",
    "fol_mode": "classical",
    "use_soft": true,
    "k_samples": 3
  }'
```

## Command Line Options

```bash
python web.py --help
```

### Development Options
- `--port PORT`: Port to run on (default: 5000)
- `--host HOST`: Host to bind to (default: 127.0.0.1)
- `--debug`: Run in debug mode with auto-reload
- `--public`: Make accessible from other machines (binds to 0.0.0.0)

### Production Options
- `--production`: Use Gunicorn production server (recommended for production)
- `--workers N`: Number of Gunicorn worker processes (default: 4)

### Examples

```bash
# Development with debug mode
python web.py --debug

# Production on port 8000 with 8 workers
python web.py --production --port 8000 --workers 8

# Public production server
python web.py --production --public --port 80
```

## Environment Variables

Same as the CLI:

- `GEMINI_API_KEY` or (`GOOGLE_CLOUD_PROJECT` + `GOOGLE_CLOUD_LOCATION`)
- `LLM_MODEL` (default: `gemini-2.5-flash`)
- `CACHE_LLM` (enable caching)
- `LLM_CACHE_DIR` (default: `.cache/llm`)

## File Structure

```
argir/
├── web.py                  # Simple launcher (in root)
├── web/                    # Web frontend package
│   ├── __init__.py        # Package init
│   ├── web_frontend.py    # Flask application
│   ├── run_web.py         # Full startup script
│   ├── wsgi.py           # WSGI entry point
│   └── templates/        # HTML templates
│       ├── base.html     # Base template with styling
│       ├── index.html    # Main input form
│       └── results.html  # Results display
└── WEB_FRONTEND.md       # This file
```

## Mobile Support

The interface is fully responsive and optimized for mobile devices with:
- Touch-friendly form controls
- Readable text on small screens
- Collapsible sections for complex output
- Optimized font sizes and spacing

## Production Deployment

### Using the Built-in Production Mode

```bash
python web.py --production --public --port 8000 --workers 4
```

### Manual Gunicorn Deployment

```bash
# Install Gunicorn
pip install gunicorn

# Run directly with Gunicorn
gunicorn --bind 0.0.0.0:8000 --workers 4 --timeout 120 wsgi:application
```

### Docker Deployment

Create a `Dockerfile`:
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY . .

RUN pip install -e .

EXPOSE 8000
CMD ["python", "web.py", "--production", "--host", "0.0.0.0", "--port", "8000"]
```

### Production Considerations

- **Workers**: Use 2-4 workers per CPU core
- **Timeout**: Set to 120+ seconds for LLM processing
- **Memory**: Each worker needs ~200-500MB RAM
- **Load Balancer**: Use nginx or similar for SSL termination
- **Environment**: Set production environment variables
- **Logging**: Configure proper logging and monitoring

## Development

To run in development mode:

```bash
python web.py --debug
```

This enables:
- Auto-reload on code changes
- Detailed error messages
- Flask debug toolbar (if installed)
