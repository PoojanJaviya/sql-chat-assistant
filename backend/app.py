import os
import re
import json
import sqlite3
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from google import genai
from dotenv import load_dotenv
from safety import is_safe_query

# Load environment variables
load_dotenv()

# Define Base Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")
DB_PATH = os.path.join(BASE_DIR, "data", "hackathon.db")

# Initialize Flask to serve static files from the frontend folder
app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
CORS(app)

# Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini Client
client = None
if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not found in environment variables.")
else:
    client = genai.Client(api_key=GEMINI_API_KEY)

def load_file_content(filename):
    """Safe file reading helper"""
    filepath = os.path.join(PROMPTS_DIR, filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Could not find {filepath}")
        return ""

# Load context files at startup
SYSTEM_PROMPT = load_file_content("system_prompt.md")
SCHEMA_CONTEXT = load_file_content("schema.txt")

def parse_gemini_response(text):
    """Parses the Markdown response from Gemini."""
    response_data = {
        "sql": "",
        "explanation": "",
        "visualization": {"type": "table", "reason": "Default view"}
    }

    try:
        # Extract SQL
        sql_match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL)
        if sql_match:
            sql_candidate = sql_match.group(1).strip()
            
            # FIX: Clean up potential prefix hallucinations (like "ite SELECT")
            # We look for the first occurrence of a standard SQL command
            command_match = re.search(r'\b(SELECT|WITH|INSERT|UPDATE|DELETE)\b', sql_candidate, re.IGNORECASE)
            if command_match:
                # Start the string from the found command, removing any garbage prefix
                response_data["sql"] = sql_candidate[command_match.start():]
            else:
                # Fallback if no keyword found (unlikely for valid SQL)
                response_data["sql"] = sql_candidate

        # Extract Explanation
        explanation_match = re.search(r"## Explanation\s*(.*?)\s*(?:## Visualization|$)", text, re.DOTALL)
        if explanation_match:
            response_data["explanation"] = explanation_match.group(1).strip()

        # Extract Visualization Type
        vis_type_match = re.search(r"\[Type:\s*(.*?)\]", text, re.IGNORECASE)
        if vis_type_match:
            response_data["visualization"]["type"] = vis_type_match.group(1).strip().lower()

        # Extract Visualization Reason
        vis_reason_match = re.search(r"\[Reason:\s*(.*?)\]", text, re.IGNORECASE)
        if vis_reason_match:
            response_data["visualization"]["reason"] = vis_reason_match.group(1).strip()

    except Exception as e:
        print(f"Parsing error: {e}")
    
    # FINAL FALLBACK: If regex failed to find a structured "## Explanation",
    # it means the AI just gave a plain text answer (like a clarification).
    # In this case, we use the ENTIRE text as the explanation so the user sees it.
    if not response_data["explanation"]:
        response_data["explanation"] = text

    return response_data

# --- ROUTES ---

@app.route('/')
def serve_frontend():
    """Serves the index.html file from the frontend directory"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.json
        user_question = data.get("question")

        if not user_question:
            return jsonify({"success": False, "error": "No question provided"}), 400

        full_prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"--- DATABASE SCHEMA ---\n"
            f"{SCHEMA_CONTEXT}\n\n"
            f"--- USER QUESTION ---\n"
            f"{user_question}"
        )

        if not client:
             return jsonify({"success": False, "error": "Gemini API Key missing"}), 500

        # Using gemini-flash-latest to ensure free tier quota works
        response = client.models.generate_content(
            model='gemini-flash-latest', 
            contents=full_prompt
        )
        parsed_data = parse_gemini_response(response.text)

        return jsonify({"success": True, **parsed_data})

    except Exception as e:
        print(f"API Error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/execute', methods=['POST'])
def execute_sql():
    try:
        data = request.json
        sql = data.get("sql")

        if not sql:
            return jsonify({"success": False, "error": "No SQL query provided"}), 400

        safe, reason = is_safe_query(sql)
        if not safe:
            return jsonify({"success": False, "error": f"Safety Violation: {reason}"}), 403

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            cursor.execute(sql)
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
            else:
                conn.commit()
                columns = []
                rows = []
                
            conn.close()
            return jsonify({"success": True, "columns": columns, "rows": rows})
            
        except Exception as db_err:
            conn.close()
            return jsonify({"success": False, "error": str(db_err)}), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Server running at http://127.0.0.1:{port}/")
    app.run(debug=True, port=port)