"""Student management."""
from datetime import datetime
from typing import Callable, List

from .errors import NotFoundError, ValidationError
from .models import Enrollment, Student, Store


def _check_email(email: str) -> str:
    email = (email or "").strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValidationError(f"invalid email: {email!r}")
    return email


class StudentService:
    def __init__(self, store: Store, clock: Callable[[], datetime] = datetime.utcnow):
        self.store, self.clock = store, clock

    def register(self, name: str, email: str, bio: str = "") -> Student:
        if not (name or "").strip():
            raise ValidationError("name is required")
        email = _check_email(email)
        if any(s.email == email for s in self.store.students.values()):
            raise ValidationError(f"email already registered: {email}")
        s = Student(self.store.next_id("student"), name.strip(), email, bio, self.clock())
        self.store.students[s.id] = s
        return s

    def get(self, student_id: int) -> Student:
        try:
            return self.store.students[student_id]
        except KeyError:
            raise NotFoundError(f"student {student_id} not found") from None

    def update_profile(self, student_id: int, name: str = None, email: str = None, bio: str = None) -> Student:
        s = self.get(student_id)
        if email is not None:
            email = _check_email(email)
            if any(o.email == email and o.id != s.id for o in self.store.students.values()):
                raise ValidationError(f"email already registered: {email}")
            s.email = email
        if name is not None:
            if not name.strip():
                raise ValidationError("name is required")
            s.name = name.strip()
        if bio is not None:
            s.bio = bio
        return s

    def enrollment_history(self, student_id: int) -> List[Enrollment]:
        self.get(student_id)
        return sorted(
            (e for e in self.store.enrollments.values() if e.student_id == student_id),
            key=lambda e: (e.enrolled_at, e.id),
        )
