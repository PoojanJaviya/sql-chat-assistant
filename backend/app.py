import os
import re
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication

# Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")

# Configure Gemini
if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not found in environment variables.")
else:
    genai.configure(api_key=GEMINI_API_KEY)
    # Using the latest model
    model = genai.GenerativeModel('gemini-2.0-flash-exp') 

def load_file_content(filename):
    """Safe file reading helper"""
    filepath = os.path.join(PROMPTS_DIR, filename)
    try:
        with open(filepath, "r") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Could not find {filepath}")
        return ""

# Load context files at startup
SYSTEM_PROMPT = load_file_content("system_prompt.md")
SCHEMA_CONTEXT = load_file_content("schema.txt")

def parse_gemini_response(text):
    """
    Parses the Markdown response from Gemini into a structured dictionary.
    Expected format defined in system_prompt.md
    """
    response_data = {
        "sql": "",
        "explanation": "",
        "visualization": {"type": "table", "reason": "Default view"}
    }

    try:
        # Extract SQL
        sql_match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL)
        if sql_match:
            response_data["sql"] = sql_match.group(1).strip()

        # Extract Explanation
        # Looks for text between ## Explanation and ## Visualization
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
        # Fallback: if parsing fails, at least return the explanation as the raw text
        if not response_data["explanation"]:
            response_data["explanation"] = text

    return response_data

@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.json
        user_question = data.get("question")

        if not user_question:
            return jsonify({"success": False, "error": "No question provided"}), 400

        # Construct the full prompt
        full_prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"--- DATABASE SCHEMA ---\n"
            f"{SCHEMA_CONTEXT}\n\n"
            f"--- USER QUESTION ---\n"
            f"{user_question}"
        )

        # Call Gemini
        response = model.generate_content(full_prompt)
        raw_text = response.text

        # Parse the structured response
        parsed_data = parse_gemini_response(raw_text)

        return jsonify({
            "success": True,
            **parsed_data
        })

    except Exception as e:
        print(f"API Error: {str(e)}")
        return jsonify({
            "success": False, 
            "error": str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, port=port)