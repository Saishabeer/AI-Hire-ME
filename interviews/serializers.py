from typing import Any, Dict, List

from rest_framework import serializers

from .models import Question


class AnswerItemSerializer(serializers.Serializer):
    """Single QA item sent from UI/API."""

    question = serializers.IntegerField()
    text = serializers.CharField(allow_blank=True, required=False, default="")
    option_values = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
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
        """
        Validate each answer item and ensure multiple-choice options are valid.
        """
        interview = self.context.get("interview")
        if not interview:
            raise serializers.ValidationError("Interview context missing")

        valid_qids = set(
            Question.objects.filter(section__interview=interview).values_list("id", flat=True)
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

            # Ensure option_values is a list of strings if present and valid for the question
            if "option_values" in item:
                vals = item.get("option_values") or []
                if not isinstance(vals, list) or any(not isinstance(x, str) for x in vals):
                    raise serializers.ValidationError("option_values must be a list of strings")

                # For multiple choice, enforce membership in configured options
                try:
                    q = Question.objects.get(pk=qid, section__interview=interview)
                except Question.DoesNotExist:
                    q = None
                if q and q.question_type == "multiple_choice":
                    allowed = set(q.options or [])
                    invalid = [v for v in vals if v not in allowed]
                    if invalid:
                        raise serializers.ValidationError(
                            f"Invalid options for question {qid}: {invalid}"
                        )

        return value
