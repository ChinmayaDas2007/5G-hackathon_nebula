def calculate_news(hr, pulse, spo2, sys_bp, temp, rr):
    score = 0

    # --- 1. RESPIRATORY RATE ---
    if rr <= 8: score += 3
    elif 9 <= rr <= 11: score += 1
    elif 12 <= rr <= 20: score += 0
    elif 21 <= rr <= 24: score += 2
    else: score += 3

    # --- 2. OXYGEN SATURATION ---
    if spo2 <= 91: score += 3
    elif 92 <= spo2 <= 93: score += 2
    elif 94 <= spo2 <= 95: score += 1
    else: score += 0 

    # --- 3. TEMPERATURE ---
    if temp <= 35.0: score += 3
    elif 35.1 <= temp <= 36.0: score += 1
    elif 36.1 <= temp <= 38.0: score += 0 
    elif 38.1 <= temp <= 39.0: score += 1
    else: score += 2

    # --- 4. SYSTOLIC BP ---
    if sys_bp <= 90: score += 3
    elif 91 <= sys_bp <= 100: score += 2
    elif 101 <= sys_bp <= 110: score += 1
    else: score += 0 

    # --- 5. HEART RATE (Electrical) ---
    if hr <= 40: score += 3
    elif 41 <= hr <= 50: score += 1
    elif 51 <= hr <= 90: score += 0 
    elif 91 <= hr <= 110: score += 1
    elif 111 <= hr <= 130: score += 2
    else: score += 3

    # --- 6. PULSE (Mechanical) ---
    # Using same logic as HR for scoring
    if pulse <= 40: score += 3
    elif 41 <= pulse <= 50: score += 1
    elif 51 <= pulse <= 90: score += 0 
    elif 91 <= pulse <= 110: score += 1
    elif 111 <= pulse <= 130: score += 2
    else: score += 3

    return score

def get_risk_level(score):
    if score >= 7: return "RED", f"CRITICAL (NEWS: {score})"
    elif score >= 5: return "ORANGE", f"URGENT (NEWS: {score})"
    elif score >= 1: return "YELLOW", f"MONITOR (NEWS: {score})"
    else: return "GREEN", "STABLE"