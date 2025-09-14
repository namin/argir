from __future__ import annotations
import os
import json
import tempfile
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from argir.pipeline import run_pipeline, run_pipeline_soft
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
        use_soft = request.form.get('use_soft') == 'on'
        k_samples = int(request.form.get('k_samples', '1'))

        if not text:
            flash('Please enter some text to analyze.', 'error')
            return redirect(url_for('index'))

        # Run the pipeline
        fol_mode = "defeasible" if defeasible_fol else "classical"
        if use_soft:
            result = run_pipeline_soft(text, fol_mode=fol_mode, goal_id=goal_id, k_samples=k_samples)
        else:
            result = run_pipeline(text, fol_mode=fol_mode, goal_id=goal_id)

        # Show validation issues as warnings if present
        if use_soft and result.get('soft_validation'):
            validation_report = result['soft_validation']
            if hasattr(validation_report, 'errors') and validation_report.errors():
                error_msg = "❌ Soft IR validation errors:\n"
                for issue in validation_report.errors():
                    error_msg += f"• [{issue.code}] {issue.path}: {issue.message}\n"
                flash(error_msg, 'error')
            if hasattr(validation_report, 'warn') and validation_report.warn():
                warning_msg = "⚠️ Soft IR validation warnings:\n"
                for issue in validation_report.warn():
                    warning_msg += f"• [{issue.code}] {issue.path}: {issue.message}\n"
                flash(warning_msg, 'warning')
        elif result.get('validation_issues'):
            warning_msg = "⚠️ Validation issues detected:\n"
            for issue in result['validation_issues']:
                warning_msg += f"• Node '{issue['node']}': {issue['message']}\n"
            warning_msg += "\nThese are warnings about potentially incomplete reasoning. Results have been generated but may need review."
            flash(warning_msg, 'warning')

        # Format results for display
        return render_template('results.html',
                             text=text,
                             result=result,
                             fol_mode=fol_mode,
                             goal_id=goal_id,
                             use_soft=use_soft,
                             k_samples=k_samples,
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
        use_soft = data.get('use_soft', False)
        k_samples = data.get('k_samples', 1)

        if use_soft:
            result = run_pipeline_soft(text, fol_mode=fol_mode, goal_id=goal_id, k_samples=k_samples)
        else:
            result = run_pipeline(text, fol_mode=fol_mode, goal_id=goal_id)

        # Include validation issues in response if present
        response = {
            'success': True,
            'result': result
        }
        if result.get('validation_issues'):
            response['warnings'] = {
                'validation_issues': result['validation_issues'],
                'message': 'Validation issues detected. Results generated but may need review.'
            }

        return jsonify(response)
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
