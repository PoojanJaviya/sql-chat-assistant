🔮 InsightAI: SQL Chat Assistant

[!NOTE]
Talk to your data. A natural language interface that executes safe SQL queries, generates visualizations, and forecasts future trends using Google Gemini Flash.

🚀 Features

Natural Language to SQL: Converts plain English (e.g., "Show sales for 2023") into executable SQL.

Live Execution: Connects to a real SQLite database to fetch live results (not just text generation).

Auto-Visualization: Intelligently chooses between Data Tables, Bar Charts, or Line Charts based on data shape.

🔮 Future Forecasting: Uses Linear/Polynomial Regression (Scikit-Learn) to predict future trends based on historical data.

🛡️ Enterprise Safety: Custom middleware blocks destructive commands (DROP, DELETE) to prevent data loss.

🛠️ Tech Stack

Backend: Python, Flask, Scikit-Learn (Forecasting)

Frontend: React (Single File Architecture), Tailwind CSS, Recharts

Database: SQLite

AI Engine: Google Gemini 1.5 Flash / 2.0 Flash (via google-genai SDK)

⚡ Quick Start Guide

Follow these steps to get the project running locally in 5 minutes.

1. Clone the Repository

git clone <your-repo-url>
cd sql-chat-assistant


2. Install Dependencies

Make sure you have Python installed. Then run:

pip install -r requirements.txt


3. Setup Environment Variables

[!IMPORTANT]
You must have a valid API Key for the application to work.

Get a free key from Google AI Studio.

Create a .env file in the root directory.

Paste the key as shown below:

GEMINI_API_KEY=AIzaSy...YourKeyHere


4. Initialize Database

Create the SQLite database and seed it with dummy data:

python backend/init_db.py


5. Run the Server

Start the Flask backend (which also serves the Frontend):

python backend/app.py


6. Open the App

Go to your browser and visit:

https://www.google.com/search?q=http://127.0.0.1:5000

🧪 Demo Scenarios

[!TIP]
Use this script during your hackathon demo to showcase all features:

Simple Query: "Show me all products."

Aggregation: "What is the total revenue by country?" (Triggers Bar Chart)

Time-Series: "Show orders for 2023 ordered by date."

Forecasting: Click the "Predict Future" button in the top right.

[!CAUTION]
Safety Demo: Try asking "DELETE all customers."
The middleware will block this request to demonstrate enterprise security features.

📂 Project Structure

sql-chat-assistant/
├── backend/
│   ├── app.py          # Main Flask Server & API Routes
│   ├── safety.py       # SQL Sanitization Middleware
│   ├── forecast.py     # ML Forecasting Logic
│   └── init_db.py      # Database Seeding Script
├── data/
│   ├── hackathon.db    # SQLite Database (Created on init)
│   └── seed_data.sql   # Raw SQL data for testing
├── frontend/
│   └── index.html      # Single-file React Application
├── prompts/
│   ├── system_prompt.md # AI Persona & Rules
│   └── schema.txt       # Database Schema Context
└── README.md


📜 License

MIT License
