"""Grading: per-assessment scores under a scoring policy, weighted final grades."""
from dataclasses import dataclass
from typing import Dict, Optional

from .assessments import AssessmentService
from .errors import NotFoundError
from .models import Assessment, AssessmentKind, ScoringPolicy, Store


def letter_grade(score: float) -> str:
    for cutoff, letter in ((90, "A"), (80, "B"), (70, "C"), (60, "D")):
        if score >= cutoff:
            return letter
    return "F"


@dataclass
class FinalGrade:
    score: float  # 0-100
    letter: str
    passed: bool
    breakdown: Dict[int, Optional[float]]  # assessment id -> score (None = missing)
    complete: bool  # every assessment has a graded score


class GradingService:
    def __init__(self, store: Store, assessments: AssessmentService):
        self.store, self.assessments = store, assessments

    def assessment_score(self, enrollment_id: int, assessment: Assessment) -> Optional[float]:
        """Score (0-100) under the assessment's policy; ungraded attempts are ignored."""
        graded = [t.score for t in self.assessments.attempts(enrollment_id, assessment.id)
                  if t.score is not None]
        if not graded:
            return None
        if assessment.policy == ScoringPolicy.BEST:
            return max(graded)
        if assessment.policy == ScoringPolicy.LATEST:
            return graded[-1]
        return round(sum(graded) / len(graded), 2)

    def assignment_scores(self, enrollment_id: int) -> Dict[int, Optional[float]]:
        return self._scores(enrollment_id, AssessmentKind.ASSIGNMENT)

    def quiz_scores(self, enrollment_id: int) -> Dict[int, Optional[float]]:
        return self._scores(enrollment_id, AssessmentKind.QUIZ)

    def _scores(self, enrollment_id, kind):
        e = self.store.enrollments.get(enrollment_id)
        if e is None:
            raise NotFoundError(f"enrollment {enrollment_id} not found")
        return {a.id: self.assessment_score(enrollment_id, a)
                for a in self.assessments.for_course(e.course_id) if a.kind == kind}

    def final_grade(self, enrollment_id: int) -> FinalGrade:
        """Weighted average over all course assessments; missing ones count as zero."""
        e = self.store.enrollments.get(enrollment_id)
        if e is None:
            raise NotFoundError(f"enrollment {enrollment_id} not found")
        items = self.assessments.for_course(e.course_id)
        breakdown = {a.id: self.assessment_score(enrollment_id, a) for a in items}
        total_w = sum(a.weight for a in items)
        if total_w == 0:
            score = 0.0
        else:
            score = sum((breakdown[a.id] or 0.0) * a.weight for a in items) / total_w
        score = round(score, 2)
        pass_mark = self.store.courses[e.course_id].pass_mark
        return FinalGrade(score, letter_grade(score), bool(items) and score >= pass_mark,
                          breakdown, all(v is not None for v in breakdown.values()))
