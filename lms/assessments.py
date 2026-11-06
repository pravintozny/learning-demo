"""Assessment management: quizzes, assignments, scoring and attempt limits."""
from datetime import datetime
from typing import Callable, Dict, List, Optional

from .errors import AttemptLimitError, LMSError, NotFoundError, ValidationError
from .models import (Assessment, AssessmentKind, Attempt, EnrollmentStatus, HistoryEvent,
                     Question, ScoringPolicy, Store)


class AssessmentService:
    def __init__(self, store: Store, clock: Callable[[], datetime] = datetime.utcnow):
        self.store, self.clock = store, clock

    def _create(self, course_id, kind, title, weight, max_attempts, policy, **kw) -> Assessment:
        if course_id not in self.store.courses:
            raise NotFoundError(f"course {course_id} not found")
        if not (title or "").strip():
            raise ValidationError("title is required")
        if weight <= 0:
            raise ValidationError("weight must be positive")
        if max_attempts < 1:
            raise ValidationError("max_attempts must be at least 1")
        a = Assessment(self.store.next_id("assessment"), course_id, kind, title.strip(),
                       float(weight), max_attempts=max_attempts, policy=ScoringPolicy(policy), **kw)
        self.store.assessments[a.id] = a
        return a

    def create_quiz(self, course_id: int, title: str, weight: float, max_attempts: int = 3,
                    policy=ScoringPolicy.BEST) -> Assessment:
        return self._create(course_id, AssessmentKind.QUIZ, title, weight, max_attempts, policy)

    def create_assignment(self, course_id: int, title: str, weight: float, max_points: float = 100.0,
                          max_attempts: int = 1, policy=ScoringPolicy.BEST) -> Assessment:
        if max_points <= 0:
            raise ValidationError("max_points must be positive")
        return self._create(course_id, AssessmentKind.ASSIGNMENT, title, weight, max_attempts,
                            policy, max_points=float(max_points))

    def get(self, assessment_id: int) -> Assessment:
        try:
            return self.store.assessments[assessment_id]
        except KeyError:
            raise NotFoundError(f"assessment {assessment_id} not found") from None

    def for_course(self, course_id: int) -> List[Assessment]:
        return [a for a in self.store.assessments.values() if a.course_id == course_id]

    def add_question(self, quiz_id: int, text: str, choices: List[str], correct_index: int,
                     points: float = 1.0) -> Question:
        a = self.get(quiz_id)
        if a.kind != AssessmentKind.QUIZ:
            raise ValidationError("questions can only be added to quizzes")
        if len(choices) < 2:
            raise ValidationError("a question needs at least two choices")
        if not 0 <= correct_index < len(choices):
            raise ValidationError("correct_index out of range")
        if points <= 0:
            raise ValidationError("points must be positive")
        q = Question(self.store.next_id("question"), text, list(choices), correct_index, float(points))
        a.questions.append(q)
        return q

    def attempts(self, enrollment_id: int, assessment_id: int) -> List[Attempt]:
        return sorted((t for t in self.store.attempts.values()
                       if t.enrollment_id == enrollment_id and t.assessment_id == assessment_id),
                      key=lambda t: t.id)

    def _begin(self, enrollment_id: int, assessment_id: int, kind: AssessmentKind):
        e = self.store.enrollments.get(enrollment_id)
        if e is None:
            raise NotFoundError(f"enrollment {enrollment_id} not found")
        a = self.get(assessment_id)
        if a.kind != kind:
            raise ValidationError(f"assessment {a.id} is not a {kind.value}")
        if a.course_id != e.course_id:
            raise ValidationError("assessment does not belong to the enrolled course")
        if e.status == EnrollmentStatus.DROPPED:
            raise LMSError("enrollment was dropped")
        if len(self.attempts(enrollment_id, assessment_id)) >= a.max_attempts:
            raise AttemptLimitError(f"attempt limit of {a.max_attempts} reached")
        return e, a

    def submit_quiz(self, enrollment_id: int, quiz_id: int, answers: Dict[int, int]) -> Attempt:
        e, a = self._begin(enrollment_id, quiz_id, AssessmentKind.QUIZ)
        if not a.questions:
            raise ValidationError("quiz has no questions")
        total = sum(q.points for q in a.questions)
        earned = sum(q.points for q in a.questions if answers.get(q.id) == q.correct_index)
        t = Attempt(self.store.next_id("attempt"), a.id, e.id, self.clock(),
                    answers=dict(answers), score=round(earned / total * 100, 2))
        self.store.attempts[t.id] = t
        self.store.history.append(HistoryEvent(t.submitted_at, e.student_id, e.course_id,
                                               "quiz_submitted", f"{a.title}: {t.score}%"))
        return t

    def submit_assignment(self, enrollment_id: int, assignment_id: int, content: str) -> Attempt:
        e, a = self._begin(enrollment_id, assignment_id, AssessmentKind.ASSIGNMENT)
        if not (content or "").strip():
            raise ValidationError("submission content is required")
        t = Attempt(self.store.next_id("attempt"), a.id, e.id, self.clock(), content=content)
        self.store.attempts[t.id] = t
        self.store.history.append(HistoryEvent(t.submitted_at, e.student_id, e.course_id,
                                               "assignment_submitted", a.title))
        return t

    def grade_assignment(self, attempt_id: int, points: float) -> Attempt:
        t = self.store.attempts.get(attempt_id)
        if t is None:
            raise NotFoundError(f"attempt {attempt_id} not found")
        a = self.get(t.assessment_id)
        if a.kind != AssessmentKind.ASSIGNMENT:
            raise ValidationError("only assignment attempts are graded manually")
        if not 0 <= points <= a.max_points:
            raise ValidationError(f"points must be between 0 and {a.max_points}")
        t.score = round(points / a.max_points * 100, 2)
        e = self.store.enrollments[t.enrollment_id]
        self.store.history.append(HistoryEvent(self.clock(), e.student_id, e.course_id,
                                               "assignment_graded", f"{a.title}: {t.score}%"))
        return t
