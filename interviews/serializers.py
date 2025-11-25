from typing import Any, Dict, List
from rest_framework import serializers
from .models import Interview, Question


class AnswerItemSerializer(serializers.Serializer):
    """Single QA item sent from UI/API."""
    question = serializers.IntegerField()
    text = serializers.CharField(allow_blank=True, required=False, default="")
    option_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )


class SubmitResponseSerializer(serializers.Serializer):
    """
    Validates a complete interview submission.
    Also supports realtime (voice) transcript capture.
    """
    candidate_name = serializers.CharField()
    candidate_email = serializers.EmailField()
    answers = AnswerItemSerializer(many=True)
    transcript = serializers.CharField(allow_blank=True, required=False, default="")
    source = serializers.ChoiceField(choices=("form", "realtime", "api"), default="api")

    def validate_answers(self, value: List[Dict[str, Any]]):
        interview: Interview | None = self.context.get("interview")
        if not interview:
            raise serializers.ValidationError("Interview context missing")
        valid_qids = set(
            Question.objects.filter(interview=interview).values_list("id", flat=True)
        )
        for item in value:
            qid = item.get("question")
            if qid not in valid_qids:
                raise serializers.ValidationError(
                    f"Question {qid} is not part of interview {interview.pk}"
                )
            # Sanitize strings
            txt = item.get("text")
            if txt is not None and not isinstance(txt, str):
                raise serializers.ValidationError("Answer.text must be a string")
            # Ensure option_ids is a list of ints if present
            if "option_ids" in item:
                try:
                    _ = [int(x) for x in (item.get("option_ids") or [])]
                except Exception:
                    raise serializers.ValidationError("option_ids must be a list of integers")
        return value