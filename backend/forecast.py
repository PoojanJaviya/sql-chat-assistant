import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline
from datetime import datetime

def calculate_forecast(historical_data, months_to_predict=6):
    """
    Takes historical data: list of tuples [(date_str, value), ...]
    Returns: List of dicts formatted for Recharts consumption.
    Format: [{date: '2023-01', revenue: 100, forecast: null}, ...]
    """
    if not historical_data or len(historical_data) < 2:
        return {"error": "Not enough data points to forecast (need at least 2)."}

    # 1. Prepare Data
    # Sort by date to ensure linearity
    historical_data.sort(key=lambda x: x[0])
    
    dates_ordinal = []
    values = []
    
    for i, (d_str, val) in enumerate(historical_data):
        dates_ordinal.append([i]) # Scikit-learn requires 2D array
        values.append(float(val))

    X = np.array(dates_ordinal)
    y = np.array(values)

    # 2. Scikit-Learn Polynomial Regression (Degree 2 = Curve)
    # This fits a curve (parabola) instead of a straight line
    degree = 2 
    model = make_pipeline(PolynomialFeatures(degree), LinearRegression())
    model.fit(X, y)

    # 3. Build Result Set (Historical)
    results = []
    for i, (d_str, val) in enumerate(historical_data):
        results.append({
            "date": d_str,
            "revenue": val,
            "forecast": None, 
            "type": "historical"
        })

    # 4. Generate Future Points
    last_date_str = historical_data[-1][0]
    try:
        # Try YYYY-MM format
        last_date = datetime.strptime(last_date_str, "%Y-%m")
    except ValueError:
        # Fallback to YYYY-MM-DD
        last_date = datetime.strptime(last_date_str[:7], "%Y-%m")

    for i in range(1, months_to_predict + 1):
        next_index = len(dates_ordinal) - 1 + i
        next_X = np.array([[next_index]])
        
        predicted_val = model.predict(next_X)[0]
        
        # Calculate next month date
        next_month = last_date.month + 1
        next_year = last_date.year
        if next_month > 12:
            next_month = 1
            next_year += 1
        last_date = last_date.replace(year=next_year, month=next_month)
        
        results.append({
            "date": last_date.strftime("%Y-%m"),
            "revenue": None,
            "forecast": round(max(0, predicted_val), 2), # Clamp to 0
            "type": "prediction"
        })

    return results