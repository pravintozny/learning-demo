# learning-demo: Learning Management System

A dependency-free, in-memory Learning Management System in Python 3.8+.

## Modules (`lms/`)

| Area | Module | Highlights |
|---|---|---|
| Students | `students.py` | registration (unique email), profiles, enrollment history |
| Instructors | `instructors.py` | profiles, skills, course assignment |
| Courses | `courses.py` | categories, modules, lessons, prerequisites (cycle-checked), pricing, catalog search |
| Enrollment | `enrollments.py` | status + dates, capacity, duplicate and prerequisite checks |
| Assessments | `assessments.py` | quizzes, assignments, questions, attempt limits, scoring policy |
| Progress | `progress.py` | lesson completion, completion %, learning history, certificates |
| Grading | `grading.py` | quiz/assignment scores, weighted final grade, letter grade |
| Analytics | `analytics.py` | student, course, instructor, enrollment statistics |

`lms.LMS` wires all services around one shared store.

## Quick start

```python
from lms import LMS

lms = LMS()
cat = lms.courses.add_category("Programming")
course = lms.courses.create_course("Python 101", cat.id, price=49, capacity=30)
module = lms.courses.add_module(course.id, "Basics")
lesson = lms.courses.add_lesson(module.id, "Hello world")
lms.courses.publish(course.id)

student = lms.students.register("Ada", "ada@example.com")
enrollment = lms.enrollments.enroll(student.id, course.id)

quiz = lms.assessments.create_quiz(course.id, "Quiz 1", weight=100)
q = lms.assessments.add_question(quiz.id, "2+2?", ["3", "4"], correct_index=1)
lms.assessments.submit_quiz(enrollment.id, quiz.id, {q.id: 1})
lms.progress.complete_lesson(enrollment.id, lesson.id)
certificate = lms.progress.try_complete(enrollment.id)
```

## Business rules

- **Enrollment** fails if the course is unpublished, the student already holds an active or
  completed enrollment (re-enrolling after a drop is allowed), the capacity is reached
  (active and completed enrollments hold a seat), or any prerequisite course has not been
  *completed* by the student.
- **Prerequisites** cannot be circular or self-referential.
- **Quiz score** = points earned / total points x 100. **Assignment score** = awarded / max points x 100,
  set by an instructor via `grade_assignment`; ungraded attempts are ignored.
- **Attempt limits** are per enrollment and assessment. Each assessment uses a policy
  (`best`, `latest` or `average`) to pick its score from attempts.
- **Final grade** = sum(score x weight) / sum(weights); missing assessments count as 0.
  Letters: A>=90, B>=80, C>=70, D>=60, else F. Pass requires score >= the course `pass_mark`
  (default 60) and at least one assessment.
- **Completion & certificate**: `try_complete` marks an enrollment completed and issues a
  certificate only when all lessons are done and the final grade passes.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for design notes.

## Tests

```
python3 -m unittest discover -s tests -v
```
