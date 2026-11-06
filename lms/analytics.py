"""Analytics over students, courses and instructors."""
from typing import Dict, Optional

from .enrollments import EnrollmentService
from .errors import NotFoundError
from .grading import GradingService
from .models import EnrollmentStatus, Store
from .progress import ProgressService


def _avg(values) -> Optional[float]:
    values = list(values)
    return round(sum(values) / len(values), 2) if values else None


class AnalyticsService:
    def __init__(self, store: Store, enrollments: EnrollmentService,
                 grading: GradingService, progress: ProgressService):
        self.store, self.enrollments = store, enrollments
        self.grading, self.progress = grading, progress

    def student_performance(self, student_id: int) -> Dict:
        if student_id not in self.store.students:
            raise NotFoundError(f"student {student_id} not found")
        es = [e for e in self.store.enrollments.values() if e.student_id == student_id]
        live = [e for e in es if e.status != EnrollmentStatus.DROPPED]
        return {
            "enrolled": len(es),
            "completed": sum(e.status == EnrollmentStatus.COMPLETED for e in es),
            "dropped": sum(e.status == EnrollmentStatus.DROPPED for e in es),
            "average_progress": _avg(self.progress.completion_percentage(e.id) for e in live),
            "average_grade": _avg(self.grading.final_grade(e.id).score for e in live),
            "certificates": sum(c.student_id == student_id for c in self.store.certificates.values()),
        }

    def course_completion_rate(self, course_id: int) -> float:
        """Completed / (all non-dropped enrollments), as a percentage."""
        if course_id not in self.store.courses:
            raise NotFoundError(f"course {course_id} not found")
        es = [e for e in self.store.enrollments.values()
              if e.course_id == course_id and e.status != EnrollmentStatus.DROPPED]
        if not es:
            return 0.0
        return round(sum(e.status == EnrollmentStatus.COMPLETED for e in es) / len(es) * 100, 2)

    def enrollment_statistics(self, course_id: int) -> Dict:
        if course_id not in self.store.courses:
            raise NotFoundError(f"course {course_id} not found")
        c = self.store.courses[course_id]
        es = [e for e in self.store.enrollments.values() if e.course_id == course_id]
        by = {s.value: sum(e.status == s for e in es) for s in EnrollmentStatus}
        taken = self.enrollments.seats_taken(course_id)
        return {
            "total": len(es), **by, "capacity": c.capacity, "seats_taken": taken,
            "seats_left": self.enrollments.seats_left(course_id),
            "utilization": None if c.capacity is None else round(taken / c.capacity * 100, 2),
            "revenue": round(taken * c.price, 2),
        }

    def instructor_performance(self, instructor_id: int) -> Dict:
        inst = self.store.instructors.get(instructor_id)
        if inst is None:
            raise NotFoundError(f"instructor {instructor_id} not found")
        ids = set(inst.course_ids)
        es = [e for e in self.store.enrollments.values()
              if e.course_id in ids and e.status != EnrollmentStatus.DROPPED]
        return {
            "courses": len(ids),
            "students": len({e.student_id for e in es}),
            "completion_rate": round(sum(e.status == EnrollmentStatus.COMPLETED for e in es)
                                     / len(es) * 100, 2) if es else 0.0,
            "average_grade": _avg(self.grading.final_grade(e.id).score for e in es),
        }
