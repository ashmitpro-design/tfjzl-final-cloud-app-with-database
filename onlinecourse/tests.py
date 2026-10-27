from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from .models import Course, Enrollment, Lesson, Question, Choice


class AssessmentFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='learner', password='test-pass-123')
        self.course = Course.objects.create(name='Test course', image='test.jpg', description='Test', pub_date='2026-01-01')
        self.lesson = Lesson.objects.create(title='Lesson', course=self.course, content='Content')
        self.question = Question.objects.create(lesson=self.lesson, question_text='Question?', grade=2)
        self.correct = Choice.objects.create(question=self.question, choice_text='Right', is_correct=True)
        Choice.objects.create(question=self.question, choice_text='Wrong', is_correct=False)
        Enrollment.objects.create(user=self.user, course=self.course, mode='honor')

    def test_score_method_counts_correct_choices(self):
        from .models import Submission
        submission = Submission.objects.create(enrollment=self.user.enrollment_set.get())
        submission.choices.add(self.correct)
        self.assertEqual(submission.is_get_score(), 2)

    def test_submit_and_result(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('onlinecourse:submit', args=[self.course.id]), {f'choice_{self.question.id}': self.correct.id})
        self.assertEqual(response.status_code, 302)
        result = self.client.get(response.url)
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, 'Congratulations!')
        self.assertContains(result, '2 / 2 points')

    def test_submission_requires_post_and_enrollment(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('onlinecourse:submit', args=[self.course.id])).status_code, 405)
        self.user.enrollment_set.all().delete()
        self.assertEqual(self.client.post(reverse('onlinecourse:submit', args=[self.course.id])).status_code, 404)

    def test_csrf_is_enforced(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(reverse('onlinecourse:submit', args=[self.course.id]), {f'choice_{self.question.id}': self.correct.id})
        self.assertEqual(response.status_code, 403)
