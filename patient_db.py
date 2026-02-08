import pandas as pd
import random

# Embedded EWS Logic (so this file runs standalone)
def calculate_news_internal(hr, spo2, sys_bp, temp, rr):
    score = 0
    if rr <= 8 or rr >= 25: score += 3
    elif 21 <= rr <= 24: score += 2
    elif 9 <= rr <= 11: score += 1
    if spo2 <= 91: score += 3
    elif 92 <= spo2 <= 93: score += 2
    elif 94 <= spo2 <= 95: score += 1
    if sys_bp <= 90: score += 3
    elif 91 <= sys_bp <= 100: score += 2
    elif sys_bp >= 220: score += 3
    if hr <= 40: score += 3
    elif 131 <= hr: score += 3
    elif 111 <= hr <= 130: score += 2
    if temp <= 35.0: score += 3
    elif temp >= 39.1: score += 2
    return score

def generate_patient_db(n=50):
    first_names = ["Arjun", "Aditi", "Rahul", "Priya", "Amit", "Sneha", "Vikram", "Anjali", "Rohan", "Kavita"]
    last_names = ["Sharma", "Verma", "Gupta", "Singh", "Patel", "Das", "Rao", "Nair", "Mehta", "Kumar"]
    conditions = ["Post-Op Recovery", "Dengue Fever", "Hypertension", "Viral Fever", "Cardiac Obs", "Stable", "Respiratory Infection"]
    
    rows = []
    for i in range(1, n + 1):
        bed_id = f"BED-{i:03d}"
        # Generate random vitals for the baseline
        hr = random.randint(60, 100)
        spo2 = random.randint(90, 100)
        sys = random.randint(100, 140)
        temp = round(random.uniform(36.5, 37.5), 1)
        rr = random.randint(12, 20)
        
        score = calculate_news_internal(hr, spo2, sys, temp, rr)
        
        rows.append({
            "Bed ID": bed_id,
            "Name": f"{random.choice(first_names)} {random.choice(last_names)}",
            "Age": random.randint(20, 80),
            "Condition": random.choice(conditions),
            "Baseline NEWS": score
        })

    return pd.DataFrame(rows)
