from __future__ import annotations
import os
import json
import tempfile
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from argir.pipeline import run_pipeline
import argir as _argir_pkg

app = Flask(__name__)
app.secret_key = os.urandom(24)

@app.route('/')
def index():
    """Main page with input form"""
    return render_template('index.html', version=_argir_pkg.__version__)

@app.route('/process', methods=['POST'])
def process_text():
    """Process the input text through ARGIR pipeline"""
    try:
        # Get form data
        text = request.form.get('text', '').strip()
        defeasible_fol = request.form.get('defeasible_fol') == 'on'
        goal_id = request.form.get('goal_id', '').strip() or None
        # Strict mode is ON by default, user can opt out
        strict = request.form.get('disable_strict') != 'on'

        if not text:
            flash('Please enter some text to analyze.', 'error')
            return redirect(url_for('index'))

        # Run the pipeline
        fol_mode = "defeasible" if defeasible_fol else "classical"
        result = run_pipeline(text, fol_mode=fol_mode, goal_id=goal_id, strict=strict)
        
        # Format results for display
        return render_template('results.html', 
                             text=text,
                             result=result,
                             fol_mode=fol_mode,
                             goal_id=goal_id,
                             version=_argir_pkg.__version__)
    
    except Exception as e:
        flash(f'Error processing text: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/api/process', methods=['POST'])
def api_process():
    """API endpoint for programmatic access"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'Missing text parameter'}), 400
        
        text = data['text'].strip()
        if not text:
            return jsonify({'error': 'Text cannot be empty'}), 400

        fol_mode = data.get('fol_mode', 'classical')
        goal_id = data.get('goal_id')
        # Strict mode is ON by default in API, can be disabled with strict=false
        strict = data.get('strict', True)

        result = run_pipeline(text, fol_mode=fol_mode, goal_id=goal_id, strict=strict)
        
        return jsonify({
            'success': True,
            'result': result
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'version': _argir_pkg.__version__,
        'package_path': _argir_pkg.__file__
    })

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Run the app
    app.run(debug=True, host='0.0.0.0', port=5000)
