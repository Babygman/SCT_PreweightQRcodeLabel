USER_STATES = {
    "BRIDGE_UNAVAILABLE": {
        "th": "ไม่สามารถเชื่อมต่อ Scale Bridge ได้",
        "en": "Scale Bridge unavailable",
    },
    "DISCONNECTED": {"th": "เครื่องชั่งไม่ได้เชื่อมต่อ", "en": "Scale disconnected"},
    "MULTIPLE_SCALES": {"th": "พบเครื่องชั่งหลายเครื่อง", "en": "Multiple scales detected"},
    "READING_MISSING": {"th": "ไม่มีค่าน้ำหนัก", "en": "Reading unavailable"},
    "READING_UNSTABLE": {"th": "ค่าน้ำหนักไม่นิ่ง", "en": "Reading unstable"},
    "READING_STALE": {"th": "ค่าน้ำหนักล้าสมัย", "en": "Reading stale"},
    "OVERLOAD": {"th": "น้ำหนักเกินพิกัด", "en": "Overload"},
    "TARE_MISSING": {"th": "ยังไม่ได้บันทึกน้ำหนักภาชนะ", "en": "Tare missing"},
    "READY": {"th": "พร้อมบันทึก", "en": "Ready to save"},
}


def bilingual_state(code):
    labels = USER_STATES.get(code, {"th": "ไม่ทราบสถานะ", "en": "Unknown state"})
    return {"code": code, "label_th": labels["th"], "label_en": labels["en"]}
