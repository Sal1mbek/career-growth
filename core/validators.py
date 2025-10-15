# core/validators.py
from jsonschema import Draft7Validator, ValidationError as JSONSchemaError


def validate_json_payload(schema: dict, value: dict, *, path="payload"):
    """
    Вызывает serializers.ValidationError, если JSON не валиден под schema.
    """
    try:
        Draft7Validator(schema).validate(value or {})
    except JSONSchemaError as e:
        loc = " → ".join([str(p) for p in e.path]) or path
        msg = f"{loc}: {e.message}"
        from rest_framework import serializers
        raise serializers.ValidationError({path: msg})
    return value


def check_payload_version(value: dict, min_version=1, path="payload"):
    from rest_framework import serializers
    ver = (value or {}).get("payload_version", 1)
    if ver < min_version:
        raise serializers.ValidationError({path: f"payload_version={ver} < минимально допустимого {min_version}"})
