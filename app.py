from flask import Flask, render_template, request, jsonify
import pandas as pd
import numpy as np
import os

app = Flask(__name__)

# Load CSV data and handle NaN values
csv_path = os.path.join(os.path.dirname(__file__), "Antifouling Paints Info.csv")
df = pd.read_csv(csv_path)

# Replace NaN values in numeric columns with 0
numeric_columns = ["DRYDOCK PERIOD", "FUEL SAVING", "SPEED LOSS", "IDLE DAYS", "COST"]
for col in numeric_columns:
    df[col] = df[col].fillna(0)  # Replace NaN with 0

# Replace NaN in string columns with empty string
string_columns = ["OEM", "OFFERING", "LOCATION", "ACTIVITY LEVEL"]
for col in string_columns:
    df[col] = df[col].fillna("")

# Scoring function
def score_paint(row, user_inputs):
    score = 0
    if row["DRYDOCK PERIOD"] >= user_inputs["drydock_period"]:
        score += (row["DRYDOCK PERIOD"] / user_inputs["drydock_period"]) * user_inputs["w1"]
    score += row["FUEL SAVING"] * user_inputs["w2"]
    score += (1 - row["SPEED LOSS"]) * user_inputs["w3"]
    if row["IDLE DAYS"] >= user_inputs["idle_days"]:
        score += (row["IDLE DAYS"] / user_inputs["idle_days"]) * user_inputs["w4"]
    return score

# Calculate weights
def calculate_weights(selected_priorities):
    weights = {"w1": 0, "w2": 0, "w3": 0, "w4": 0}
    if not selected_priorities:
        weights = {"w1": 25, "w2": 25, "w3": 25, "w4": 25}
        return weights
    
    num_selected = len(selected_priorities)
    equal_weight = 100 / num_selected
    
    if "drydock_period" in selected_priorities:
        weights["w1"] = equal_weight
    if "fuel_saving" in selected_priorities:
        weights["w2"] = equal_weight
    if "speed_loss" in selected_priorities:
        weights["w3"] = equal_weight
    if "idle_days" in selected_priorities:
        weights["w4"] = equal_weight
    
    return weights

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        data = request.form
        drydock_period = float(data.get('drydock_period'))
        idle_days = float(data.get('idle_days'))
        location = data.get('location')
        
        # Get selected priorities
        selected_priorities = []
        if data.get('drydock_period_check'): selected_priorities.append("drydock_period")
        if data.get('fuel_saving_check'): selected_priorities.append("fuel_saving")
        if data.get('speed_loss_check'): selected_priorities.append("speed_loss")
        if data.get('idle_days_check'): selected_priorities.append("idle_days")

        if not selected_priorities:
            return jsonify({"error": "Please select at least one priority."}), 400

        weights = calculate_weights(selected_priorities)
        
        user_inputs = {
            "drydock_period": drydock_period,
            "idle_days": idle_days,
            "location": location,
            "w1": weights["w1"],
            "w2": weights["w2"],
            "w3": weights["w3"],
            "w4": weights["w4"]
        }

        # Filter by location
        filtered_df = df[df["LOCATION"].str.contains(user_inputs["location"], case=False, na=False)].copy()
        
        if filtered_df.empty:
            return jsonify({"error": "No paints match the specified location."}), 400

        # Apply scoring
        filtered_df["Score"] = filtered_df.apply(lambda row: score_paint(row, user_inputs), axis=1)

        # Get top 3
        top_3 = filtered_df.sort_values(by="Score", ascending=False).head(3)

        # Format results
        results = []
        for _, row in top_3.iterrows():
            result = {
                "oem": row["OEM"],
                "offering": row["OFFERING"],
                "speed_loss": row["SPEED LOSS"],
                "cost": row["COST"],
                "fuel_saving": row["FUEL SAVING"],
                "activity": row["ACTIVITY LEVEL"],
                "location": row["LOCATION"]
            }
            results.append(result)

        response = {
            "priorities": selected_priorities,
            "weights": weights,
            "results": results
        }
        return jsonify(response)

    except ValueError:
        return jsonify({"error": "Please enter valid numeric values for idle days and drydock period."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))