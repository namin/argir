# ARGIR Web Application

A modern FastAPI/React web application for ARGIR (Argument Graph Intermediate Representation).

## Setup

### Backend (FastAPI)

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Run the backend server:
```bash
python server.py
```

The backend will start on http://localhost:8000

### Frontend (React)

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install Node dependencies:
```bash
npm install
```

3. Run the development server:
```bash
npm run dev
```

The frontend will start on http://localhost:5173

## Features

- Natural language argument analysis
- Argument graph generation
- First-Order Logic (FOL) output in TPTP format
- Classical and defeasible FOL modes
- Soft pipeline option for more robust extraction
- Argumentation Framework (AF) semantics
- Gemini API key management (bring your own key)

## API Endpoints

- `GET /api/health` - Health check
- `POST /api/analyze` - Analyze natural language arguments

## Environment Variables

- `PORT` - Backend server port (default: 8000)
- `GEMINI_API_KEY` - Default Gemini API key (optional, can be set per-request)
- `LLM_MODEL` - LLM model to use (default: gemini-2.5-flash)

## Usage

1. Start both the backend and frontend servers
2. Open http://localhost:5173 in your browser
3. (Optional) Enter your Gemini API key in the header
4. Enter natural language arguments in the text area
5. Configure options (FOL mode, soft pipeline, etc.)
6. Click "Analyze Arguments" to process
7. View results in different tabs (Report, Graph, FOL, etc.)