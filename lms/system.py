"""Facade wiring every service around one shared store."""
from datetime import datetime
from typing import Callable

from .analytics import AnalyticsService
from .assessments import AssessmentService
from .courses import CourseService
from .enrollments import EnrollmentService
from .grading import GradingService
from .instructors import InstructorService
from .models import Store
from .progress import ProgressService
from .students import StudentService


class LMS:
    def __init__(self, clock: Callable[[], datetime] = datetime.utcnow):
        self.store = Store()
        self.students = StudentService(self.store, clock)
        self.instructors = InstructorService(self.store)
        self.courses = CourseService(self.store)
        self.enrollments = EnrollmentService(self.store, clock)
        self.assessments = AssessmentService(self.store, clock)
        self.grading = GradingService(self.store, self.assessments)
        self.progress = ProgressService(self.store, self.courses, self.enrollments, self.grading, clock)
        self.analytics = AnalyticsService(self.store, self.enrollments, self.grading, self.progress)
