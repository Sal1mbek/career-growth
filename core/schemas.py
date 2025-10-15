from rest_framework import serializers


class PayloadTemplatesResponseSerializer(serializers.Serializer):
    version = serializers.IntegerField()
    schema = serializers.JSONField()
    templates = serializers.JSONField()
