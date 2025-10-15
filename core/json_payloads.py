# core/json_payloads.py

# ----- Notification -----
NOTIFICATION_TEMPLATES = {
    "ASSESSMENT": {
        "title": "Аттестация назначена",
        "link": "/assessments/{assessment_id}/",
        "data": {
            "assessment_id": 0,
            "officer": "",
            "status": "PLANNED",
            "due_date": "YYYY-MM-DD"
        }
    },
    "TRAINING": {
        "title": "Назначено обучение",
        "link": "/trainings/{course_id}/",
        "data": {"course_id": 0, "title": "", "start_at": "YYYY-MM-DD"}
    },
    "CAREER": {
        "title": "Обновлена карьерная траектория",
        "link": "/career/trajectories/{trajectory_id}/",
        "data": {"trajectory_id": 0, "status": "ACTIVE", "target_position": ""}
    },
    "VACANCY": {
        "title": "Новая вакансия",
        "link": "/vacancies/{vacancy_id}/",
        "data": {"vacancy_id": 0, "position": "", "department": ""}
    },
    "SYSTEM": {
        "title": "Системное сообщение",
        "message": "Плановые работы...",
        "severity": "info"  # info|warning|critical
    },
}

NOTIFICATION_TEMPLATES["ASSESSMENT"]["payload_version"] = 1

NOTIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "link": {"type": "string"},
        "message": {"type": "string"},
        "severity": {"type": "string", "enum": ["info", "warning", "critical"]},
        "data": {"type": "object"},
        "payload_version": {"type": "number"}
    },
    "additionalProperties": True
}

# ----- Feedback360 -----
FEEDBACK360_TEMPLATE = {
    "competencies": [
        # {"competency_id": 0, "score": 3}
    ],
    "comments": ""
}

FEEDBACK360_TEMPLATE["payload_version"] = 1

FEEDBACK360_SCHEMA = {
    "type": "object",
    "properties": {
        "competencies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "competency_id": {"type": "number"},
                    "score": {"type": "number", "minimum": 1, "maximum": 5}
                },
                "required": ["competency_id", "score"]
            }
        },
        "comments": {"type": "string"},
        "payload_version": {"type": "number"}
    },
    "required": ["competencies"],
    "additionalProperties": False
}

# ----- Recommendation -----
RECOMMENDATION_TEMPLATES = {
    "TRAINING": {
        "training_id": 0,
        "training_title": "",
        "reason": "",
        "link": "/trainings/{training_id}/"
    },
    "COMPETENCY_GAP": {
        "competency": "",
        "target_score": 4.0,
        "current_score": 0.0,
        "actions": ["Курс ...", "Наставничество ..."]
    },
    "POSITION": {
        "target_position": "",
        "required_competencies": [],
        "gap_analysis": {}  # {"Коммуникация": -0.5}
    }
}

RECOMMENDATION_TEMPLATES["TRAINING"]["payload_version"] = 1

RECOMMENDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "training_id": {"type": "number"},
        "training_title": {"type": "string"},
        "reason": {"type": "string"},
        "link": {"type": "string"},
        "competency": {"type": "string"},
        "target_score": {"type": "number"},
        "current_score": {"type": "number"},
        "actions": {"type": "array", "items": {"type": "string"}},
        "target_position": {"type": "string"},
        "required_competencies": {"type": "array", "items": {"type": "string"}},
        "gap_analysis": {"type": "object"},
        "payload_version": {"type": "number"}
    },
    "additionalProperties": True
}
