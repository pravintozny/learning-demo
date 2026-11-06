"""Progress tracking: lesson completion, course percentage, history, certificates."""
import uuid
from datetime import datetime
from typing import Callable, List

from .courses import CourseService
from .enrollments import EnrollmentService
from .errors import LMSError, ValidationError
from .grading import GradingService
from .models import Certificate, EnrollmentStatus, HistoryEvent, Store


class ProgressService:
    def __init__(self, store: Store, courses: CourseService, enrollments: EnrollmentService,
                 grading: GradingService, clock: Callable[[], datetime] = datetime.utcnow):
        self.store, self.courses, self.enrollments = store, courses, enrollments
        self.grading, self.clock = grading, clock

    def complete_lesson(self, enrollment_id: int, lesson_id: int) -> float:
        e = self.enrollments.get(enrollment_id)
        if e.status == EnrollmentStatus.DROPPED:
            raise LMSError("enrollment was dropped")
        if lesson_id not in self.courses.lesson_ids(e.course_id):
            raise ValidationError("lesson does not belong to the enrolled course")
        done = self.store.completed_lessons.setdefault(enrollment_id, {})
        if lesson_id not in done:
            done[lesson_id] = self.clock()
            self.store.history.append(HistoryEvent(
                done[lesson_id], e.student_id, e.course_id, "lesson_completed",
                self.store.lessons[lesson_id].title))
        return self.completion_percentage(enrollment_id)

    def completion_percentage(self, enrollment_id: int) -> float:
        e = self.enrollments.get(enrollment_id)
        total = len(self.courses.lesson_ids(e.course_id))
        if total == 0:
            return 0.0
        return round(len(self.store.completed_lessons.get(enrollment_id, {})) / total * 100, 2)

    def learning_history(self, student_id: int, course_id: int = None) -> List[HistoryEvent]:
        return sorted((h for h in self.store.history if h.student_id == student_id
                       and (course_id is None or h.course_id == course_id)),
                      key=lambda h: h.at)

    def try_complete(self, enrollment_id: int):
        """Complete the course and issue a certificate if all lessons are done and the
        final grade meets the course pass mark. Returns the certificate or None."""
        e = self.enrollments.get(enrollment_id)
        if e.status == EnrollmentStatus.COMPLETED:
            return self.certificate_for(enrollment_id)
        if e.status != EnrollmentStatus.ACTIVE:
            return None
        if self.completion_percentage(enrollment_id) < 100:
            return None
        grade = self.grading.final_grade(enrollment_id)
        if not grade.passed:
            return None
        self.enrollments.mark_completed(enrollment_id)
        cert = Certificate(self.store.next_id("certificate"), e.id, e.student_id, e.course_id,
                           grade.score, self.clock(), uuid.uuid4().hex[:12].upper())
        self.store.certificates[cert.id] = cert
        self.store.history.append(HistoryEvent(cert.issued_at, e.student_id, e.course_id,
                                               "certificate_issued", cert.code))
        return cert

    def certificate_for(self, enrollment_id: int):
        return next((c for c in self.store.certificates.values()
                     if c.enrollment_id == enrollment_id), None)
