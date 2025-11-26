from django.contrib.auth.models import User
from django.test import SimpleTestCase

from interviews.models import Answer, Candidate, Interview, InterviewResponse, Question, Section


class ModelStrTests(SimpleTestCase):
    """
    CI-safe model string representation tests.
    These tests do NOT hit the database; instances are not saved.
    """

    def setUp(self):
        # Minimal unsaved objects to avoid DB usage
        self.user = User(username="owner")
        self.interview = Interview(
            title="Sample Interview",
            description="Demo",
            created_by=self.user,
        )
        self.candidate = Candidate(full_name="Alice", email="alice@example.com")
        self.response = InterviewResponse(
            interview=self.interview,
            candidate=self.candidate,
        )
        # Attach question via Section (Question.interview FK removed)
        self.section = Section(interview=self.interview, title="Section 1", order=0)
        self.question = Question(
            section=self.section,
            question_text="What is your name?",
            question_type="text",
            is_required=True,
            order=1,
        )

    def test_interview_str(self):
        # [interviews.models.Interview.__str__()](interviews/models.py:18)
        self.assertEqual(str(self.interview), "Sample Interview")

    def test_candidate_str(self):
        # [interviews.models.Candidate.__str__()](interviews/models.py:85)
        self.assertEqual(str(self.candidate), "Alice <alice@example.com>")

    def test_answer_str(self):
        # [interviews.models.Answer.__str__()](interviews/models.py:123)
        ans = Answer(response=self.response, question=self.question, answer_text="Alice")
        s = str(ans)
        self.assertTrue(s.startswith("Alice"))
        self.assertIn("What is your name?", s)
