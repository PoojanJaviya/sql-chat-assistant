import os
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found in .env file")
else:
    print(f"Using API Key: {GEMINI_API_KEY[:5]}...{GEMINI_API_KEY[-4:]}")
    
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        print("\nFetching available models...")
        
        # List models
        pager = client.models.list(config={'page_size': 100})
        
        print("\n--- AVAILABLE MODELS ---")
        for model in pager:
            # Simply print the model name. 
            # We removed the 'supported_generation_methods' check as it causes errors in the new SDK.
            print(f"- {model.name}")
        
        print("\n------------------------")
        print("Copy one of the model names above (e.g., 'gemini-1.5-flash') into your backend/app.py file.")
            
    except Exception as e:
        print(f"\nError listing models: {e}")