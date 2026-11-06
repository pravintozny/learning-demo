"""Plain data models. All state lives in :class:`Store`."""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class EnrollmentStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DROPPED = "dropped"


class AssessmentKind(str, Enum):
    QUIZ = "quiz"
    ASSIGNMENT = "assignment"


class ScoringPolicy(str, Enum):
    BEST = "best"
    LATEST = "latest"
    AVERAGE = "average"


@dataclass
class Student:
    id: int
    name: str
    email: str
    bio: str = ""
    registered_at: Optional[datetime] = None


@dataclass
class Instructor:
    id: int
    name: str
    email: str
    bio: str = ""
    skills: List[str] = field(default_factory=list)
    course_ids: List[int] = field(default_factory=list)


@dataclass
class Category:
    id: int
    name: str


@dataclass
class Lesson:
    id: int
    module_id: int
    title: str


@dataclass
class Module:
    id: int
    course_id: int
    title: str
    lesson_ids: List[int] = field(default_factory=list)


@dataclass
class Course:
    id: int
    title: str
    category_id: int
    price: float = 0.0
    capacity: Optional[int] = None  # None means unlimited
    pass_mark: float = 60.0
    published: bool = False
    instructor_id: Optional[int] = None
    prerequisite_ids: List[int] = field(default_factory=list)
    module_ids: List[int] = field(default_factory=list)


@dataclass
class Enrollment:
    id: int
    student_id: int
    course_id: int
    status: EnrollmentStatus
    enrolled_at: datetime
    completed_at: Optional[datetime] = None
    dropped_at: Optional[datetime] = None


@dataclass
class Question:
    id: int
    text: str
    choices: List[str]
    correct_index: int
    points: float = 1.0


@dataclass
class Assessment:
    id: int
    course_id: int
    kind: AssessmentKind
    title: str
    weight: float  # relative weight in the final grade
    max_points: float = 100.0  # used for assignments
    max_attempts: int = 1
    policy: ScoringPolicy = ScoringPolicy.BEST
    questions: List[Question] = field(default_factory=list)


@dataclass
class Attempt:
    id: int
    assessment_id: int
    enrollment_id: int
    submitted_at: datetime
    answers: Dict[int, int] = field(default_factory=dict)
    content: str = ""
    score: Optional[float] = None  # percentage 0-100; None = awaiting grading


@dataclass
class Certificate:
    id: int
    enrollment_id: int
    student_id: int
    course_id: int
    final_grade: float
    issued_at: datetime
    code: str


@dataclass
class HistoryEvent:
    at: datetime
    student_id: int
    course_id: int
    kind: str
    detail: str = ""


class Store:
    """In-memory storage shared by every service."""

    def __init__(self) -> None:
        self.students: Dict[int, Student] = {}
        self.instructors: Dict[int, Instructor] = {}
        self.categories: Dict[int, Category] = {}
        self.courses: Dict[int, Course] = {}
        self.modules: Dict[int, Module] = {}
        self.lessons: Dict[int, Lesson] = {}
        self.enrollments: Dict[int, Enrollment] = {}
        self.assessments: Dict[int, Assessment] = {}
        self.attempts: Dict[int, Attempt] = {}
        self.certificates: Dict[int, Certificate] = {}
        self.completed_lessons: Dict[int, Dict[int, datetime]] = {}  # enrollment -> lesson -> time
        self.history: List[HistoryEvent] = []
        self._counters: Dict[str, itertools.count] = {}

    def next_id(self, kind: str) -> int:
        return next(self._counters.setdefault(kind, itertools.count(1)))
