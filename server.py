# LHDiff-Project/server.py

import os
import sys

# 🚨 FIX: Add the root project directory to the path FIRST
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root) 

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS 

try:
    from lhdiff_api import generate_web_diff
except ImportError as e:
    print(f"FATAL ERROR: Could not import 'generate_web_diff' from lhdiff_api.py.")
    print(f"Underlying cause: {e}") 
    print("Please check that all 'from lh_diff...' imports inside lhdiff_api.py are correct.")
    sys.exit(1)

# Setup Flask app, pointing to the 'web' folder for static files
# static_url_path='/', static_folder='web' means all requests to / are served from web/
app = Flask(__name__, static_url_path='/', static_folder='web')
CORS(app) 

# --- 1. API Endpoint to Run the LHDiff Logic (No change needed) ---
@app.route('/api/diff', methods=['POST'])
def run_diff():
    # ... (function body unchanged) ...
    data = request.get_json()
    if not data or 'old' not in data or 'new' not in data:
        return jsonify({"error": "Missing 'old' or 'new' file content."}), 400

    old_content = data['old']
    new_content = data['new']

    try:
        diff_result = generate_web_diff(old_content, new_content)
        return jsonify(diff_result)
    except Exception as e:
        print(f"LHDiff Error: {e}")
        return jsonify({"error": f"Internal server error during diff: {str(e)}"}), 500

# --- 2. Static File Serving (REQUIRED ADDITION HERE) ---

# 🚨 NEW: Route to serve files from the 'web/cases' directory
@app.route('/cases/<path:filename>')
def serve_cases(filename):
    # This specifically looks for files in the 'web/cases' directory
    return send_from_directory(os.path.join('web', 'cases'), filename)


@app.route('/')
def serve_index():
    return send_from_directory('web', 'LHDiffer.html')

# This serves all other files (script.js, styles.css)
@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('web', filename)


if __name__ == '__main__':
    print("Starting Flask server...")
    print("Access the web interface at: http://127.0.0.1:5000/")
    app.run(debug=True, port=5000)