import random
import pandas as pd
from ews_logic import calculate_news, get_risk_level

def generate_patient_db(n=50):
    problems = [
        "Stable – under observation",
        "Tachycardia",
        "Hypoxia",
        "Post-operative recovery",
        "Sepsis suspected",
        "Hypertension",
        "Bradycardia",
        "Respiratory distress",
        "Dehydration",
        "Fever – infection suspected"
    ]

    rows = []

    for i in range(1, n + 1):
        hr = random.randint(55, 160)
        spo2 = random.randint(80, 100)
        temp = round(random.uniform(36.0, 39.5), 1)
        sys = random.randint(90, 160)
        dia = random.randint(60, 100)

        news = calculate_news(hr, spo2, sys, temp)
        _, status = get_risk_level(news)

        rows.append({
            "Bed ID": f"BED-{i:03d}",
            "Heart Rate (bpm)": hr,
            "SpO₂ (%)": spo2,
            "Blood Pressure": f"{sys}/{dia}",
            "Temperature (°C)": temp,
            "NEWS Score": news,
            "Status": status,
            "Clinical Notes": random.choice(problems)
        })

    return pd.DataFrame(rows)
