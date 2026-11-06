import unittest
from datetime import datetime, timedelta

from lms import (LMS, AttemptLimitError, EnrollmentError, NotFoundError,
                 PrerequisiteError, ValidationError)
from lms.grading import letter_grade


class Clock:
    def __init__(self):
        self.t = datetime(2026, 1, 1)

    def __call__(self):
        self.t += timedelta(minutes=1)
        return self.t


class Base(unittest.TestCase):
    def setUp(self):
        self.lms = LMS(clock=Clock())
        self.cat = self.lms.courses.add_category("Programming")

    def course(self, title="Python 101", lessons=2, capacity=None, prereqs=(), publish=True, **kw):
        c = self.lms.courses.create_course(title, self.cat.id, capacity=capacity,
                                           prerequisite_ids=prereqs, **kw)
        m = self.lms.courses.add_module(c.id, "M1")
        for i in range(lessons):
            self.lms.courses.add_lesson(m.id, f"L{i}")
        if publish:
            self.lms.courses.publish(c.id)
        return c

    def student(self, n=1):
        return self.lms.students.register(f"S{n}", f"s{n}@x.com")


class TestStudentsInstructors(Base):
    def test_register_and_duplicate_email(self):
        s = self.student()
        self.assertEqual(s.email, "s1@x.com")
        with self.assertRaises(ValidationError):
            self.lms.students.register("Other", "S1@X.com")
        with self.assertRaises(ValidationError):
            self.lms.students.register("", "a@b.c")
        with self.assertRaises(ValidationError):
            self.lms.students.register("A", "nope")

    def test_profile_update(self):
        s = self.student()
        self.student(2)
        self.lms.students.update_profile(s.id, name="New", bio="hi")
        self.assertEqual(self.lms.students.get(s.id).name, "New")
        with self.assertRaises(ValidationError):
            self.lms.students.update_profile(s.id, email="s2@x.com")
        with self.assertRaises(NotFoundError):
            self.lms.students.get(99)

    def test_enrollment_history_ordered(self):
        s = self.student()
        a, b = self.course("A"), self.course("B")
        self.lms.enrollments.enroll(s.id, b.id)
        self.lms.enrollments.enroll(s.id, a.id)
        hist = self.lms.students.enrollment_history(s.id)
        self.assertEqual([e.course_id for e in hist], [b.id, a.id])

    def test_instructor_skills_and_assignment(self):
        i = self.lms.instructors.create("Ann", "ann@x.com", skills=["Python", "python", "SQL"])
        self.assertEqual(i.skills, ["python", "sql"])
        self.assertEqual(self.lms.instructors.find_by_skill("SQL"), [i])
        j = self.lms.instructors.create("Bob", "bob@x.com")
        c = self.course()
        self.lms.instructors.assign_course(i.id, c.id)
        self.lms.instructors.assign_course(j.id, c.id)  # reassign
        self.assertEqual(self.lms.instructors.courses_of(i.id), [])
        self.assertEqual(self.lms.instructors.courses_of(j.id), [c])
        self.lms.instructors.remove_skill(i.id, "sql")
        self.assertEqual(i.skills, ["python"])
        with self.assertRaises(ValidationError):
            self.lms.instructors.create("Ann2", "ann@x.com")


class TestCourses(Base):
    def test_validation(self):
        cs = self.lms.courses
        with self.assertRaises(ValidationError):
            cs.create_course("X", self.cat.id, price=-1)
        with self.assertRaises(ValidationError):
            cs.create_course("X", self.cat.id, capacity=0)
        with self.assertRaises(NotFoundError):
            cs.create_course("X", 999)
        with self.assertRaises(ValidationError):
            cs.add_category("programming")

    def test_publish_requires_lessons(self):
        c = self.course(lessons=0, publish=False)
        with self.assertRaises(ValidationError):
            self.lms.courses.publish(c.id)

    def test_prerequisite_cycles_rejected(self):
        a = self.course("A")
        b = self.course("B", prereqs=[a.id])
        c = self.course("C", prereqs=[b.id])
        with self.assertRaises(ValidationError):
            self.lms.courses.set_prerequisites(a.id, [c.id])
        with self.assertRaises(ValidationError):
            self.lms.courses.set_prerequisites(a.id, [a.id])
        with self.assertRaises(NotFoundError):
            self.lms.courses.create_course("D", self.cat.id, prerequisite_ids=[999])

    def test_catalog_filters(self):
        self.course("Alpha", price=10)
        self.course("Beta", price=50)
        self.course("Hidden", publish=False)
        cs = self.lms.courses
        self.assertEqual([c.title for c in cs.catalog()], ["Alpha", "Beta"])
        self.assertEqual([c.title for c in cs.catalog(max_price=20)], ["Alpha"])
        self.assertEqual([c.title for c in cs.catalog(search="bet")], ["Beta"])
        self.assertEqual(len(cs.catalog(published_only=False)), 3)


class TestEnrollment(Base):
    def test_duplicate_blocked_but_reenroll_after_drop(self):
        s, c = self.student(), self.course()
        e = self.lms.enrollments.enroll(s.id, c.id)
        with self.assertRaises(EnrollmentError):
            self.lms.enrollments.enroll(s.id, c.id)
        self.lms.enrollments.drop(e.id)
        self.assertEqual(self.lms.enrollments.enroll(s.id, c.id).status.value, "active")

    def test_capacity(self):
        c = self.course(capacity=1)
        s1, s2 = self.student(1), self.student(2)
        e = self.lms.enrollments.enroll(s1.id, c.id)
        with self.assertRaises(EnrollmentError):
            self.lms.enrollments.enroll(s2.id, c.id)
        self.lms.enrollments.drop(e.id)  # frees the seat
        self.assertEqual(self.lms.enrollments.seats_left(c.id), 1)
        self.lms.enrollments.enroll(s2.id, c.id)

    def test_unpublished_blocked(self):
        c = self.course(publish=False)
        with self.assertRaises(EnrollmentError):
            self.lms.enrollments.enroll(self.student().id, c.id)

    def test_prerequisite_validation(self):
        base = self.course("Base")
        adv = self.course("Adv", prereqs=[base.id])
        s = self.student()
        with self.assertRaises(PrerequisiteError):
            self.lms.enrollments.enroll(s.id, adv.id)
        e = self.lms.enrollments.enroll(s.id, base.id)
        with self.assertRaises(PrerequisiteError):  # active is not enough
            self.lms.enrollments.enroll(s.id, adv.id)
        self.lms.enrollments.mark_completed(e.id)
        self.lms.enrollments.enroll(s.id, adv.id)

    def test_drop_rules(self):
        s, c = self.student(), self.course()
        e = self.lms.enrollments.enroll(s.id, c.id)
        self.lms.enrollments.mark_completed(e.id)
        with self.assertRaises(EnrollmentError):
            self.lms.enrollments.drop(e.id)
        with self.assertRaises(NotFoundError):
            self.lms.enrollments.enroll(99, c.id)


class TestAssessments(Base):
    def setUp(self):
        super().setUp()
        self.c = self.course()
        self.s = self.student()
        self.e = self.lms.enrollments.enroll(self.s.id, self.c.id)
        self.quiz = self.lms.assessments.create_quiz(self.c.id, "Q1", 40, max_attempts=2)
        self.q1 = self.lms.assessments.add_question(self.quiz.id, "1+1?", ["1", "2"], 1, points=1)
        self.q2 = self.lms.assessments.add_question(self.quiz.id, "2+2?", ["3", "4"], 1, points=3)

    def test_quiz_scoring_weighted_by_points(self):
        t = self.lms.assessments.submit_quiz(self.e.id, self.quiz.id, {self.q1.id: 1, self.q2.id: 0})
        self.assertEqual(t.score, 25.0)

    def test_attempt_limit(self):
        for _ in range(2):
            self.lms.assessments.submit_quiz(self.e.id, self.quiz.id, {})
        with self.assertRaises(AttemptLimitError):
            self.lms.assessments.submit_quiz(self.e.id, self.quiz.id, {})

    def test_question_validation(self):
        a = self.lms.assessments
        with self.assertRaises(ValidationError):
            a.add_question(self.quiz.id, "q", ["only"], 0)
        with self.assertRaises(ValidationError):
            a.add_question(self.quiz.id, "q", ["a", "b"], 5)
        asg = a.create_assignment(self.c.id, "A", 10)
        with self.assertRaises(ValidationError):
            a.add_question(asg.id, "q", ["a", "b"], 0)

    def test_assignment_flow(self):
        a = self.lms.assessments
        asg = a.create_assignment(self.c.id, "HW", 60, max_points=50)
        t = a.submit_assignment(self.e.id, asg.id, "my work")
        self.assertIsNone(t.score)
        a.grade_assignment(t.id, 40)
        self.assertEqual(t.score, 80.0)
        with self.assertRaises(ValidationError):
            a.grade_assignment(t.id, 51)
        with self.assertRaises(AttemptLimitError):
            a.submit_assignment(self.e.id, asg.id, "again")

    def test_wrong_course_or_kind(self):
        other = self.course("Other")
        oq = self.lms.assessments.create_quiz(other.id, "OQ", 10)
        with self.assertRaises(ValidationError):
            self.lms.assessments.submit_quiz(self.e.id, oq.id, {})
        with self.assertRaises(ValidationError):
            self.lms.assessments.submit_assignment(self.e.id, self.quiz.id, "x")

    def test_dropped_cannot_submit(self):
        self.lms.enrollments.drop(self.e.id)
        with self.assertRaises(Exception):
            self.lms.assessments.submit_quiz(self.e.id, self.quiz.id, {})


class TestGrading(Base):
    def setUp(self):
        super().setUp()
        self.c = self.course()
        self.e = self.lms.enrollments.enroll(self.student().id, self.c.id)
        self.A = self.lms.assessments

    def perfect_quiz(self, weight, attempts=3, policy="best"):
        q = self.A.create_quiz(self.c.id, "Q", weight, attempts, policy)
        qu = self.A.add_question(q.id, "?", ["a", "b"], 0)
        return q, qu

    def test_weighted_final_grade(self):
        q, qu = self.perfect_quiz(30)
        asg = self.A.create_assignment(self.c.id, "HW", 70)
        self.A.submit_quiz(self.e.id, q.id, {qu.id: 0})  # 100
        t = self.A.submit_assignment(self.e.id, asg.id, "x")
        self.A.grade_assignment(t.id, 50)  # 50
        g = self.lms.grading.final_grade(self.e.id)
        self.assertEqual(g.score, 65.0)  # .3*100 + .7*50
        self.assertEqual(g.letter, "D")
        self.assertTrue(g.passed and g.complete)

    def test_missing_counts_as_zero(self):
        q, qu = self.perfect_quiz(50)
        self.A.create_assignment(self.c.id, "HW", 50)
        self.A.submit_quiz(self.e.id, q.id, {qu.id: 0})
        g = self.lms.grading.final_grade(self.e.id)
        self.assertEqual(g.score, 50.0)
        self.assertFalse(g.complete)
        self.assertFalse(g.passed)

    def test_policies(self):
        scores = {}
        for pol in ("best", "latest", "average"):
            q = self.A.create_quiz(self.c.id, pol, 1, 2, pol)
            qu = self.A.add_question(q.id, "?", ["a", "b"], 0)
            self.A.submit_quiz(self.e.id, q.id, {qu.id: 0})  # 100
            self.A.submit_quiz(self.e.id, q.id, {qu.id: 1})  # 0
            scores[pol] = self.lms.grading.assessment_score(self.e.id, q)
        self.assertEqual(scores, {"best": 100.0, "latest": 0.0, "average": 50.0})

    def test_ungraded_assignment_ignored_and_no_assessments(self):
        self.assertFalse(self.lms.grading.final_grade(self.e.id).passed)
        asg = self.A.create_assignment(self.c.id, "HW", 1)
        self.A.submit_assignment(self.e.id, asg.id, "x")
        self.assertIsNone(self.lms.grading.assignment_scores(self.e.id)[asg.id])
        self.assertEqual(self.lms.grading.quiz_scores(self.e.id), {})

    def test_letters(self):
        self.assertEqual([letter_grade(x) for x in (95, 85, 75, 65, 10)], list("ABCDF"))


class TestProgress(Base):
    def setUp(self):
        super().setUp()
        self.c = self.course(lessons=4)
        self.s = self.student()
        self.e = self.lms.enrollments.enroll(self.s.id, self.c.id)
        self.lessons = self.lms.courses.lesson_ids(self.c.id)
        self.P = self.lms.progress

    def test_percentage_idempotent(self):
        self.assertEqual(self.P.complete_lesson(self.e.id, self.lessons[0]), 25.0)
        self.assertEqual(self.P.complete_lesson(self.e.id, self.lessons[0]), 25.0)
        self.assertEqual(self.P.complete_lesson(self.e.id, self.lessons[1]), 50.0)

    def test_foreign_lesson_rejected(self):
        other = self.course("O")
        with self.assertRaises(ValidationError):
            self.P.complete_lesson(self.e.id, self.lms.courses.lesson_ids(other.id)[0])

    def test_certificate_requires_progress_and_passing_grade(self):
        q = self.lms.assessments.create_quiz(self.c.id, "Q", 1, 2)
        qu = self.lms.assessments.add_question(q.id, "?", ["a", "b"], 0)
        self.assertIsNone(self.P.try_complete(self.e.id))  # no progress
        for l in self.lessons:
            self.P.complete_lesson(self.e.id, l)
        self.assertIsNone(self.P.try_complete(self.e.id))  # failing grade
        self.lms.assessments.submit_quiz(self.e.id, q.id, {qu.id: 1})
        self.assertIsNone(self.P.try_complete(self.e.id))
        self.lms.assessments.submit_quiz(self.e.id, q.id, {qu.id: 0})
        cert = self.P.try_complete(self.e.id)
        self.assertEqual(cert.final_grade, 100.0)
        self.assertEqual(self.lms.enrollments.get(self.e.id).status.value, "completed")
        self.assertIs(self.P.try_complete(self.e.id), cert)  # idempotent
        self.assertIs(self.P.certificate_for(self.e.id), cert)

    def test_completion_unlocks_dependent_course(self):
        adv = self.course("Adv", prereqs=[self.c.id])
        q = self.lms.assessments.create_quiz(self.c.id, "Q", 1)
        qu = self.lms.assessments.add_question(q.id, "?", ["a", "b"], 0)
        self.lms.assessments.submit_quiz(self.e.id, q.id, {qu.id: 0})
        for l in self.lessons:
            self.P.complete_lesson(self.e.id, l)
        self.P.try_complete(self.e.id)
        self.lms.enrollments.enroll(self.s.id, adv.id)

    def test_learning_history(self):
        self.P.complete_lesson(self.e.id, self.lessons[0])
        kinds = [h.kind for h in self.P.learning_history(self.s.id)]
        self.assertEqual(kinds, ["enrolled", "lesson_completed"])
        self.assertEqual(self.P.learning_history(self.s.id, course_id=999), [])


class TestAnalytics(Base):
    def test_all_metrics(self):
        c = self.course(lessons=1, capacity=4, price=25)
        inst = self.lms.instructors.create("Ann", "a@x.com")
        self.lms.instructors.assign_course(inst.id, c.id)
        q = self.lms.assessments.create_quiz(c.id, "Q", 1)
        qu = self.lms.assessments.add_question(q.id, "?", ["a", "b"], 0)
        s1, s2, s3 = self.student(1), self.student(2), self.student(3)
        e1 = self.lms.enrollments.enroll(s1.id, c.id)
        self.lms.enrollments.enroll(s2.id, c.id)
        e3 = self.lms.enrollments.enroll(s3.id, c.id)
        self.lms.enrollments.drop(e3.id)
        self.lms.assessments.submit_quiz(e1.id, q.id, {qu.id: 0})
        self.lms.progress.complete_lesson(e1.id, self.lms.courses.lesson_ids(c.id)[0])
        self.lms.progress.try_complete(e1.id)
        a = self.lms.analytics
        self.assertEqual(a.course_completion_rate(c.id), 50.0)
        st = a.enrollment_statistics(c.id)
        self.assertEqual((st["total"], st["active"], st["completed"], st["dropped"]), (3, 1, 1, 1))
        self.assertEqual((st["seats_left"], st["utilization"], st["revenue"]), (2, 50.0, 50.0))
        sp = a.student_performance(s1.id)
        self.assertEqual((sp["completed"], sp["average_grade"], sp["certificates"]), (1, 100.0, 1))
        ip = a.instructor_performance(inst.id)
        self.assertEqual((ip["courses"], ip["students"], ip["completion_rate"], ip["average_grade"]),
                         (1, 2, 50.0, 50.0))

    def test_empty_and_missing(self):
        c = self.course()
        self.assertEqual(self.lms.analytics.course_completion_rate(c.id), 0.0)
        with self.assertRaises(NotFoundError):
            self.lms.analytics.student_performance(1)
        with self.assertRaises(NotFoundError):
            self.lms.analytics.instructor_performance(1)


if __name__ == "__main__":
    unittest.main()
