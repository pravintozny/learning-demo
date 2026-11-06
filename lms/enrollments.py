"""Enrollment management with capacity, duplicate and prerequisite constraints."""
from datetime import datetime
from typing import Callable, List, Optional

from .errors import EnrollmentError, NotFoundError, PrerequisiteError
from .models import Enrollment, EnrollmentStatus, HistoryEvent, Store

HOLDS_SEAT = (EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED)


class EnrollmentService:
    def __init__(self, store: Store, clock: Callable[[], datetime] = datetime.utcnow):
        self.store, self.clock = store, clock

    def get(self, enrollment_id: int) -> Enrollment:
        try:
            return self.store.enrollments[enrollment_id]
        except KeyError:
            raise NotFoundError(f"enrollment {enrollment_id} not found") from None

    def seats_taken(self, course_id: int) -> int:
        return sum(1 for e in self.store.enrollments.values()
                   if e.course_id == course_id and e.status in HOLDS_SEAT)

    def seats_left(self, course_id: int) -> Optional[int]:
        cap = self.store.courses[course_id].capacity
        return None if cap is None else max(cap - self.seats_taken(course_id), 0)

    def has_completed(self, student_id: int, course_id: int) -> bool:
        return any(e.student_id == student_id and e.course_id == course_id
                   and e.status == EnrollmentStatus.COMPLETED
                   for e in self.store.enrollments.values())

    def missing_prerequisites(self, student_id: int, course_id: int) -> List[int]:
        c = self.store.courses[course_id]
        return [p for p in c.prerequisite_ids if not self.has_completed(student_id, p)]

    def enroll(self, student_id: int, course_id: int) -> Enrollment:
        if student_id not in self.store.students:
            raise NotFoundError(f"student {student_id} not found")
        if course_id not in self.store.courses:
            raise NotFoundError(f"course {course_id} not found")
        course = self.store.courses[course_id]
        if not course.published:
            raise EnrollmentError("course is not open for enrollment")
        for e in self.store.enrollments.values():
            if e.student_id == student_id and e.course_id == course_id and e.status in HOLDS_SEAT:
                raise EnrollmentError("student is already enrolled in this course")
        missing = self.missing_prerequisites(student_id, course_id)
        if missing:
            raise PrerequisiteError(f"missing completed prerequisites: {missing}")
        if course.capacity is not None and self.seats_taken(course_id) >= course.capacity:
            raise EnrollmentError("course is at full capacity")
        e = Enrollment(self.store.next_id("enrollment"), student_id, course_id,
                       EnrollmentStatus.ACTIVE, self.clock())
        self.store.enrollments[e.id] = e
        self.store.history.append(HistoryEvent(e.enrolled_at, student_id, course_id, "enrolled"))
        return e

    def drop(self, enrollment_id: int) -> Enrollment:
        e = self.get(enrollment_id)
        if e.status != EnrollmentStatus.ACTIVE:
            raise EnrollmentError(f"cannot drop an enrollment that is {e.status.value}")
        e.status, e.dropped_at = EnrollmentStatus.DROPPED, self.clock()
        self.store.history.append(HistoryEvent(e.dropped_at, e.student_id, e.course_id, "dropped"))
        return e

    def mark_completed(self, enrollment_id: int) -> Enrollment:
        e = self.get(enrollment_id)
        if e.status != EnrollmentStatus.ACTIVE:
            raise EnrollmentError(f"cannot complete an enrollment that is {e.status.value}")
        e.status, e.completed_at = EnrollmentStatus.COMPLETED, self.clock()
        self.store.history.append(HistoryEvent(e.completed_at, e.student_id, e.course_id, "completed"))
        return e
