import random
import pandas as pd
from ews_logic import calculate_news, get_risk_level

def generate_patient_db(n=50):
    rows = []
    for i in range(1, n + 1):
        hr = random.randint(55, 160)
        pulse = hr - random.randint(0, 5) # Pulse usually <= HR
        spo2 = random.randint(80, 100)
        temp = round(random.uniform(36.0, 39.5), 1)
        sys = random.randint(90, 160)
        dia = random.randint(60, 100)
        rr = random.randint(12, 25)

        # PASS ALL 6 ARGS NOW
        news = calculate_news(hr, pulse, spo2, sys, temp, rr)
        _, status = get_risk_level(news)

        rows.append({
            "Bed ID": f"BED-{i:03d}",
            "HR (Electrical)": hr,    # <--- NEW LABEL
            "Pulse (Mech)": pulse,    # <--- NEW COLUMN
            "Resp. Rate": rr,
            "SpO₂ (%)": spo2,
            "Blood Pressure": f"{sys}/{dia}",
            "Temperature (°C)": temp,
            "NEWS Score": news,
            "Status": status,
            "Clinical Notes": "Generated Record"
        })

    return pd.DataFrame(rows)
