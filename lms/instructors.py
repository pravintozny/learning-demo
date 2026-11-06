"""Instructor management."""
from typing import Iterable, List

from .errors import NotFoundError, ValidationError
from .models import Course, Instructor, Store


class InstructorService:
    def __init__(self, store: Store):
        self.store = store

    def create(self, name: str, email: str, bio: str = "", skills: Iterable[str] = ()) -> Instructor:
        if not (name or "").strip():
            raise ValidationError("name is required")
        email = (email or "").strip().lower()
        if "@" not in email:
            raise ValidationError(f"invalid email: {email!r}")
        if any(i.email == email for i in self.store.instructors.values()):
            raise ValidationError(f"email already registered: {email}")
        inst = Instructor(self.store.next_id("instructor"), name.strip(), email, bio)
        self.store.instructors[inst.id] = inst
        for s in skills:
            self.add_skill(inst.id, s)
        return inst

    def get(self, instructor_id: int) -> Instructor:
        try:
            return self.store.instructors[instructor_id]
        except KeyError:
            raise NotFoundError(f"instructor {instructor_id} not found") from None

    def update_profile(self, instructor_id: int, name: str = None, bio: str = None) -> Instructor:
        i = self.get(instructor_id)
        if name is not None:
            if not name.strip():
                raise ValidationError("name is required")
            i.name = name.strip()
        if bio is not None:
            i.bio = bio
        return i

    def add_skill(self, instructor_id: int, skill: str) -> Instructor:
        i = self.get(instructor_id)
        skill = (skill or "").strip().lower()
        if not skill:
            raise ValidationError("skill is required")
        if skill not in i.skills:
            i.skills.append(skill)
        return i

    def remove_skill(self, instructor_id: int, skill: str) -> Instructor:
        i = self.get(instructor_id)
        skill = skill.strip().lower()
        if skill in i.skills:
            i.skills.remove(skill)
        return i

    def find_by_skill(self, skill: str) -> List[Instructor]:
        skill = skill.strip().lower()
        return [i for i in self.store.instructors.values() if skill in i.skills]

    def assign_course(self, instructor_id: int, course_id: int) -> Course:
        i = self.get(instructor_id)
        try:
            c = self.store.courses[course_id]
        except KeyError:
            raise NotFoundError(f"course {course_id} not found") from None
        if c.instructor_id is not None and c.instructor_id != i.id:
            self.store.instructors[c.instructor_id].course_ids.remove(c.id)
        c.instructor_id = i.id
        if c.id not in i.course_ids:
            i.course_ids.append(c.id)
        return c

    def courses_of(self, instructor_id: int) -> List[Course]:
        i = self.get(instructor_id)
        return [self.store.courses[c] for c in i.course_ids]
