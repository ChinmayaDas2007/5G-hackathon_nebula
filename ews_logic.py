def calculate_news(hr, spo2, sys_bp, temp):
    score = 0
    
    # --- 1. RESPIRATORY RATE (We assume normal for now if not tracking) ---
    # (If you add RR later, add logic here)

    # --- 2. OXYGEN SATURATION (SpO2) ---
    if spo2 <= 91: score += 3
    elif 92 <= spo2 <= 93: score += 2
    elif 94 <= spo2 <= 95: score += 1
    else: score += 0 # >96 is normal

    # --- 3. TEMPERATURE ---
    if temp <= 35.0: score += 3
    elif 35.1 <= temp <= 36.0: score += 1
    elif 36.1 <= temp <= 38.0: score += 0 # Normal
    elif 38.1 <= temp <= 39.0: score += 1
    elif temp >= 39.1: score += 2

    # --- 4. SYSTOLIC BP ---
    if sys_bp <= 90: score += 3
    elif 91 <= sys_bp <= 100: score += 2
    elif 101 <= sys_bp <= 110: score += 1
    elif 111 <= sys_bp <= 219: score += 0 # Normal
    else: score += 3 # >= 220 (Hypertensive Crisis)

    # --- 5. HEART RATE ---
    if hr <= 40: score += 3
    elif 41 <= hr <= 50: score += 1
    elif 51 <= hr <= 90: score += 0 # Normal
    elif 91 <= hr <= 110: score += 1
    elif 111 <= hr <= 130: score += 2
    else: score += 3 # >= 131

    return score

def get_risk_level(score):
    if score >= 7:
        return "RED", "CRITICAL (NEWS: " + str(score) + ")"
    elif score >= 5:
        return "ORANGE", "URGENT (NEWS: " + str(score) + ")"
    elif score >= 1:
        return "YELLOW", "MONITOR (NEWS: " + str(score) + ")"
    else:
        return "GREEN", "STABLE"