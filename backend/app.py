import os
import re
import json
import sqlite3
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from google import genai
from dotenv import load_dotenv
from safety import is_safe_query
from forecast import calculate_forecast

# Load environment variables
load_dotenv()

# Define Base Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")
DB_PATH = os.path.join(BASE_DIR, "data", "hackathon.db")

# Initialize Flask
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

SYSTEM_PROMPT = load_file_content("system_prompt.md")
SCHEMA_CONTEXT = load_file_content("schema.txt")

def parse_gemini_response(text):
    """Parses the Markdown response from Gemini (Robust Version)."""
    response_data = {
        "sql": "",
        "explanation": "",
        "visualization": {"type": "table", "reason": "Default view"}
    }

    try:
        # 1. SQL Extraction
        sql_match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL)
        if sql_match:
            sql_candidate = sql_match.group(1).strip()
        else:
            sql_match_loose = re.search(r"(?:##\s*)?SQL\s*(.*?)\s*(?:##\s*)?(?:Explanation|Visualization|$)", text, re.DOTALL | re.IGNORECASE)
            if sql_match_loose:
                sql_candidate = sql_match_loose.group(1).strip()
            else:
                select_match = re.search(r"(SELECT\s+.*?;)", text, re.DOTALL | re.IGNORECASE)
                sql_candidate = select_match.group(1).strip() if select_match else ""

        if sql_candidate:
            sql_candidate = sql_candidate.replace("```sql", "").replace("```", "").strip()
            command_match = re.search(r'\b(SELECT|WITH|INSERT|UPDATE|DELETE)\b', sql_candidate, re.IGNORECASE)
            if command_match:
                response_data["sql"] = sql_candidate[command_match.start():]
            else:
                response_data["sql"] = sql_candidate

        # 2. Explanation Extraction
        explanation_match = re.search(r"(?:##\s*)?Explanation\s*(.*?)\s*(?:##\s*)?(?:Visualization|$)", text, re.DOTALL | re.IGNORECASE)
        if explanation_match:
            response_data["explanation"] = explanation_match.group(1).strip()

        # 3. Visualization Extraction
        vis_type_match = re.search(r"\[Type:\s*(.*?)\]", text, re.IGNORECASE)
        if vis_type_match:
             response_data["visualization"]["type"] = vis_type_match.group(1).strip().lower()
        else:
             vis_section = re.search(r"(?:##\s*)?Visualization\s*(.*?)$", text, re.DOTALL | re.IGNORECASE)
             if vis_section:
                 vis_text = vis_section.group(1).lower()
                 if "bar" in vis_text: response_data["visualization"]["type"] = "bar"
                 elif "line" in vis_text: response_data["visualization"]["type"] = "line"
                 elif "pie" in vis_text: response_data["visualization"]["type"] = "pie"

    except Exception as e:
        print(f"Parsing error: {e}")
    
    if not response_data["explanation"] and not response_data["sql"]:
        response_data["explanation"] = text
    elif not response_data["explanation"]:
        response_data["explanation"] = "Here is the SQL query for your request."

    return response_data

@app.route('/')
def serve_frontend():
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

        # UPDATE: Trying 'gemini-2.0-flash' (Non-experimental alias)
        # If this fails, switch back to 'gemini-flash-latest' which is 100% working.
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash', 
                contents=full_prompt
            )
        except Exception as api_error:
            # Fallback to the reliable model if 2.0 fails
            print(f"Gemini 2.0 failed: {api_error}. Falling back to Flash Latest.")
            response = client.models.generate_content(
                model='gemini-flash-latest',
                contents=full_prompt
            )

        parsed_data = parse_gemini_response(response.text)

        return jsonify({"success": True, **parsed_data})

    except Exception as e:
        print(f"CRITICAL API ERROR: {str(e)}") # Check your terminal for this!
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

# NEW: Forecast Endpoint
@app.route('/forecast', methods=['GET', 'POST'])
def forecast():
    try:
        # 1. Fetch Historical Revenue Data (Monthly)
        query = """
            SELECT strftime('%Y-%m', order_date) as month, SUM(total_amount) as revenue 
            FROM orders 
            GROUP BY month 
            ORDER BY month ASC
        """
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()

        # 2. Calculate Forecast
        # rows is list of tuples: [('2023-01', 99.99), ...]
        forecast_data = calculate_forecast(rows)
        
        if isinstance(forecast_data, dict) and "error" in forecast_data:
             return jsonify({"success": False, "error": forecast_data["error"]})

        return jsonify({
            "success": True,
            "data": forecast_data,
            "explanation": "I analyzed the historical monthly revenue and projected the trend for the next 6 months using Linear Regression (Scikit-Learn)."
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Server running at http://127.0.0.1:{port}/")
    app.run(debug=True, port=port)