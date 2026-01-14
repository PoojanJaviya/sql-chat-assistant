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

# --- CONFIGURATION: HIGH AVAILABILITY MODE ---
# Priority Order:
# 1. gemma-3-27b: Smartest Gemma model. HUGE QUOTA (14k/day). Best for main driver.
# 2. gemma-3-12b: Faster Gemma model. HUGE QUOTA. Good backup.
# 3. gemini-2.5-flash-lite: Smart Gemini model. Small quota (20/day). Use only if Gemma fails.
# 4. gemini-2.5-flash: Standard Gemini. Small quota. Last resort.

MODEL_FALLBACK_LIST = [
    "gemma-3-27b",
    "gemma-3-12b", 
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash"
]

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
    filepath = os.path.join(PROMPTS_DIR, filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

def get_dynamic_schema():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence';")
        tables = cursor.fetchall()
        schema_text = "Current Database Schema:\n"
        for name, sql in tables:
            schema_text += f"\n--- Table: {name} ---\n{sql}\n"
        conn.close()
        return schema_text if schema_text else "No tables found."
    except Exception as e:
        print(f"Schema Error: {e}")
        return load_file_content("schema.txt")

SYSTEM_PROMPT = load_file_content("system_prompt.md")

def parse_gemini_response(text):
    response_data = {
        "sql": "",
        "explanation": "",
        "visualization": {
            "type": "table", 
            "title": "Query Result",
            "x_label": "",
            "y_label": ""
        }
    }
    try:
        # 1. SQL Parsing
        sql_match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL)
        if sql_match:
            sql_candidate = sql_match.group(1).strip()
        else:
            sql_match_loose = re.search(r"(?:##\s*)?SQL\s*(.*?)\s*(?:##\s*)?(?:Explanation|Visualization|$)", text, re.DOTALL | re.IGNORECASE)
            sql_candidate = sql_match_loose.group(1).strip() if sql_match_loose else ""

        if sql_candidate:
            sql_candidate = sql_candidate.replace("```sql", "").replace("```", "").strip()
            command_match = re.search(r'\b(SELECT|WITH|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|PRAGMA)\b', sql_candidate, re.IGNORECASE)
            if command_match:
                response_data["sql"] = sql_candidate[command_match.start():]
            else:
                response_data["sql"] = sql_candidate

        # 2. Explanation Parsing
        explanation_match = re.search(r"(?:##\s*)?Explanation\s*(.*?)\s*(?:##\s*)?(?:Visualization|$)", text, re.DOTALL | re.IGNORECASE)
        if explanation_match:
            response_data["explanation"] = explanation_match.group(1).strip()

        # 3. Visualization Parsing
        vis_section = re.search(r"(?:##\s*)?Visualization\s*(.*?)$", text, re.DOTALL | re.IGNORECASE)
        if vis_section:
            vis_text = vis_section.group(1)
            
            type_match = re.search(r"\[Type:\s*(.*?)\]", vis_text, re.IGNORECASE)
            if type_match:
                response_data["visualization"]["type"] = type_match.group(1).strip().lower()
            
            title_match = re.search(r"\[Title:\s*(.*?)\]", vis_text, re.IGNORECASE)
            if title_match:
                response_data["visualization"]["title"] = title_match.group(1).strip().strip('"')

            x_match = re.search(r"\[X-Axis:\s*(.*?)\]", vis_text, re.IGNORECASE)
            if x_match:
                response_data["visualization"]["x_label"] = x_match.group(1).strip().strip('"')

            y_match = re.search(r"\[Y-Axis:\s*(.*?)\]", vis_text, re.IGNORECASE)
            if y_match:
                response_data["visualization"]["y_label"] = y_match.group(1).strip().strip('"')

    except Exception as e:
        print(f"Parsing error: {e}")
    
    if not response_data["explanation"]:
        response_data["explanation"] = text

    return response_data

@app.route('/')
def serve_frontend():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.json
        user_question = data.get("question")
        if not user_question: return jsonify({"success": False, "error": "No question"}), 400

        current_schema = get_dynamic_schema()
        full_prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"--- DATABASE SCHEMA (LIVE) ---\n"
            f"{current_schema}\n\n"
            f"--- USER QUESTION ---\n"
            f"{user_question}"
        )

        if not client: return jsonify({"success": False, "error": "Gemini API Key missing"}), 500

        # --- MODEL ROTATION LOGIC ---
        response = None
        last_error = None
        used_model = None

        for model_name in MODEL_FALLBACK_LIST:
            try:
                # print(f"Trying model: {model_name}...") # Debug
                response = client.models.generate_content(model=model_name, contents=full_prompt)
                used_model = model_name
                print(f"SUCCESS: Connected using {model_name}")
                break # It worked! Exit loop
            except Exception as e:
                error_msg = str(e)
                last_error = error_msg
                print(f"FAILED {model_name}: {error_msg[:100]}...") # Print first 100 chars of error
                continue # Try next model

        if not response:
            print("ALL MODELS FAILED.")
            return jsonify({"success": False, "error": f"All AI models exhausted. Last error: {last_error}"}), 500

        parsed_data = parse_gemini_response(response.text)
        
        # Intent Override for Forecasting
        q_lower = user_question.lower()
        is_forecast_intent = "forecast" in q_lower or "predict" in q_lower or "trend" in q_lower or "future" in q_lower
        
        if is_forecast_intent:
            parsed_data["visualization"]["type"] = "forecast"

        if parsed_data["visualization"]["type"] == "forecast" and parsed_data["sql"]:
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute(parsed_data["sql"])
                rows = cursor.fetchall()
                conn.close()

                if len(rows) < 2:
                    parsed_data["visualization"]["error"] = "Not enough data points to forecast."
                else:
                    forecast_data = calculate_forecast(rows)
                    if isinstance(forecast_data, dict) and "error" in forecast_data:
                        parsed_data["visualization"]["error"] = forecast_data["error"]
                    else:
                        parsed_data["visualization"]["data"] = forecast_data
                    
            except Exception as db_err:
                print(f"Forecast Execution Error: {db_err}")
                parsed_data["visualization"]["error"] = f"Could not forecast: {str(db_err)}"

        return jsonify({"success": True, **parsed_data})

    except Exception as e:
        print(f"API Error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/execute', methods=['POST'])
def execute_sql():
    try:
        data = request.json
        sql = data.get("sql")
        if not sql: return jsonify({"success": False, "error": "No query"}), 400

        safe, reason = is_safe_query(sql)
        if not safe: return jsonify({"success": False, "error": f"Safety Violation: {reason}"}), 403

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            if ";" in sql.strip()[:-1]: 
                cursor.executescript(sql)
                was_mod = True
                columns, rows = [], []
            else:
                cursor.execute(sql)
                if cursor.description:
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()
                    was_mod = False
                else:
                    conn.commit()
                    was_mod = True
                    columns, rows = [], []
                
            conn.close()
            return jsonify({"success": True, "columns": columns, "rows": rows, "was_modification": was_mod})
            
        except Exception as db_err:
            conn.close()
            return jsonify({"success": False, "error": str(db_err)}), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/forecast', methods=['GET', 'POST'])
def forecast():
    try:
        query = "SELECT strftime('%Y-%m', order_date) as month, SUM(total_amount) as revenue FROM orders GROUP BY month ORDER BY month ASC"
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        forecast_data = calculate_forecast(rows)
        if isinstance(forecast_data, dict) and "error" in forecast_data:
             return jsonify({"success": False, "error": forecast_data["error"]})
        return jsonify({"success": True, "data": forecast_data, "explanation": "Forecast generated."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"--- SERVER STARTED with AUTO-ROTATION ---")
    app.run(debug=True, port=port)