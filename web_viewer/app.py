from flask import Flask, render_template, send_from_directory, abort
from werkzeug.utils import secure_filename
import os
import re

app = Flask(__name__)

# Configuration
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'output'))

@app.route('/')
def index():
    # List all directories in output that look like dates (YYYY-MM-DD)
    if not os.path.exists(OUTPUT_DIR):
        return render_template('index.html', dates=[])
    
    dirs = [d for d in os.listdir(OUTPUT_DIR) if os.path.isdir(os.path.join(OUTPUT_DIR, d))]
    # Filter for date format roughly
    date_dirs = [d for d in dirs if re.match(r'\d{4}-\d{2}-\d{2}', d)]
    # Sort descending (newest first)
    date_dirs.sort(reverse=True)
    
    return render_template('index.html', dates=date_dirs)

@app.route('/<date>')
def show_date(date):
    # Security check for path traversal
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
        abort(404)
        
    pdf_dir = os.path.join(OUTPUT_DIR, date, 'pdf')
    
    files = []
    if os.path.exists(pdf_dir):
        files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
        files.sort()
    
    return render_template('date.html', date=date, files=files)

@app.route('/pdf/<date>/<filename>')
def serve_pdf(date, filename):
    # Security check
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
        abort(404)

    # Sanitize filename to prevent path traversal
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        abort(404)

    pdf_dir = os.path.join(OUTPUT_DIR, date, 'pdf')
    return send_from_directory(pdf_dir, safe_name)

if __name__ == '__main__':
    # Listen on all interfaces so it's accessible externally if needed
    app.run(host='0.0.0.0', port=5001, debug=os.getenv('FLASK_DEBUG', '').lower() == 'true')
