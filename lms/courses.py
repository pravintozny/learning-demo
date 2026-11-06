"""Course management: catalog, categories, modules, lessons, prerequisites, pricing."""
from typing import List, Optional

from .errors import NotFoundError, ValidationError
from .models import Category, Course, Lesson, Module, Store


class CourseService:
    def __init__(self, store: Store):
        self.store = store

    # -- categories
    def add_category(self, name: str) -> Category:
        name = (name or "").strip()
        if not name:
            raise ValidationError("category name is required")
        if any(c.name.lower() == name.lower() for c in self.store.categories.values()):
            raise ValidationError(f"category exists: {name}")
        c = Category(self.store.next_id("category"), name)
        self.store.categories[c.id] = c
        return c

    # -- courses
    def create_course(self, title: str, category_id: int, price: float = 0.0,
                      capacity: Optional[int] = None, pass_mark: float = 60.0,
                      prerequisite_ids=()) -> Course:
        if not (title or "").strip():
            raise ValidationError("title is required")
        if category_id not in self.store.categories:
            raise NotFoundError(f"category {category_id} not found")
        if price < 0:
            raise ValidationError("price cannot be negative")
        if capacity is not None and capacity < 1:
            raise ValidationError("capacity must be at least 1")
        if not 0 <= pass_mark <= 100:
            raise ValidationError("pass_mark must be between 0 and 100")
        c = Course(self.store.next_id("course"), title.strip(), category_id, float(price), capacity, float(pass_mark))
        self.store.courses[c.id] = c
        try:
            self.set_prerequisites(c.id, prerequisite_ids)
        except Exception:
            del self.store.courses[c.id]
            raise
        return c

    def get(self, course_id: int) -> Course:
        try:
            return self.store.courses[course_id]
        except KeyError:
            raise NotFoundError(f"course {course_id} not found") from None

    def set_price(self, course_id: int, price: float) -> Course:
        if price < 0:
            raise ValidationError("price cannot be negative")
        c = self.get(course_id)
        c.price = float(price)
        return c

    def set_capacity(self, course_id: int, capacity: Optional[int]) -> Course:
        if capacity is not None and capacity < 1:
            raise ValidationError("capacity must be at least 1")
        c = self.get(course_id)
        c.capacity = capacity
        return c

    def set_prerequisites(self, course_id: int, prerequisite_ids) -> Course:
        c = self.get(course_id)
        ids = list(dict.fromkeys(prerequisite_ids))
        for p in ids:
            self.get(p)
            if p == course_id:
                raise ValidationError("a course cannot be its own prerequisite")
            if self._reaches(p, course_id):
                raise ValidationError("circular prerequisite chain")
        c.prerequisite_ids = ids
        return c

    def _reaches(self, start: int, target: int) -> bool:
        """True if `target` is reachable from `start` via prerequisite links."""
        seen, stack = set(), [start]
        while stack:
            cur = stack.pop()
            if cur == target:
                return True
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(self.store.courses[cur].prerequisite_ids)
        return False

    def publish(self, course_id: int) -> Course:
        c = self.get(course_id)
        if not self.lesson_ids(course_id):
            raise ValidationError("cannot publish a course without lessons")
        c.published = True
        return c

    def unpublish(self, course_id: int) -> Course:
        c = self.get(course_id)
        c.published = False
        return c

    # -- modules & lessons
    def add_module(self, course_id: int, title: str) -> Module:
        c = self.get(course_id)
        if not (title or "").strip():
            raise ValidationError("module title is required")
        m = Module(self.store.next_id("module"), course_id, title.strip())
        self.store.modules[m.id] = m
        c.module_ids.append(m.id)
        return m

    def add_lesson(self, module_id: int, title: str) -> Lesson:
        try:
            m = self.store.modules[module_id]
        except KeyError:
            raise NotFoundError(f"module {module_id} not found") from None
        if not (title or "").strip():
            raise ValidationError("lesson title is required")
        l = Lesson(self.store.next_id("lesson"), module_id, title.strip())
        self.store.lessons[l.id] = l
        m.lesson_ids.append(l.id)
        return l

    def lesson_ids(self, course_id: int) -> List[int]:
        c = self.get(course_id)
        return [l for m in c.module_ids for l in self.store.modules[m].lesson_ids]

    # -- catalog
    def catalog(self, category_id: Optional[int] = None, max_price: Optional[float] = None,
                search: str = "", published_only: bool = True) -> List[Course]:
        out = []
        for c in self.store.courses.values():
            if published_only and not c.published:
                continue
            if category_id is not None and c.category_id != category_id:
                continue
            if max_price is not None and c.price > max_price:
                continue
            if search and search.lower() not in c.title.lower():
                continue
            out.append(c)
        return sorted(out, key=lambda c: c.title.lower())
