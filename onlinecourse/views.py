from django.shortcuts import render
from django.http import HttpResponseRedirect
# <HINT> Import any new Models here
from .models import Course, Enrollment, Question, Choice, Submission
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import generic
from django.contrib.auth import login, logout, authenticate
import logging
# Get an instance of a logger
logger = logging.getLogger(__name__)
# Create your views here.


def registration_request(request):
    context = {}
    if request.method == 'GET':
        return render(request, 'onlinecourse/user_registration_bootstrap.html', context)
    elif request.method == 'POST':
        # Check if user exists
        username = request.POST['username']
        password = request.POST['psw']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']
        user_exist = False
        try:
            User.objects.get(username=username)
            user_exist = True
        except:
            logger.error("New user")
        if not user_exist:
            user = User.objects.create_user(username=username, first_name=first_name, last_name=last_name,
                                            password=password)
            login(request, user)
            return redirect("onlinecourse:index")
        else:
            context['message'] = "User already exists."
            return render(request, 'onlinecourse/user_registration_bootstrap.html', context)


def login_request(request):
    context = {}
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['psw']
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')
        else:
            context['message'] = "Invalid username or password."
            return render(request, 'onlinecourse/user_login_bootstrap.html', context)
    else:
        return render(request, 'onlinecourse/user_login_bootstrap.html', context)


def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


def check_if_enrolled(user, course):
    is_enrolled = False
    if user.id is not None:
        # Check if user enrolled
        num_results = Enrollment.objects.filter(user=user, course=course).count()
        if num_results > 0:
            is_enrolled = True
    return is_enrolled


# CourseListView
class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.order_by('-total_enrollment')[:10]
        for course in courses:
            if user.is_authenticated:
                course.is_enrolled = check_if_enrolled(user, course)
        return courses


class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_details_bootstrap.html'


def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    is_enrolled = check_if_enrolled(user, course)
    if not is_enrolled and user.is_authenticated:
        # Create an enrollment
        Enrollment.objects.create(user=user, course=course, mode='honor')
        course.total_enrollment += 1
        course.save()

    return HttpResponseRedirect(reverse(viewname='onlinecourse:course_details', args=(course.id,)))


# <HINT> Create a submit view to create an exam submission record for a course enrollment,
# you may implement it based on following logic:
         # Get user and course object, then get the associated enrollment object created when the user enrolled the course
         # Create a submission object referring to the enrollment
         # Collect the selected choices from exam form
         # Add each selected choice object to the submission object
         # Redirect to show_exam_result with the submission id
#def submit(request, course_id):


# An example method to collect the selected choices from the exam form from the request object
def extract_answers(request):
    submitted_answers = []
    for key in request.POST:
        if key.startswith('choice'):
            for value in request.POST.getlist(key):
                try:
                    submitted_answers.append(int(value))
                except (TypeError, ValueError):
                    continue
    return submitted_answers


from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied


@login_required
@require_POST
def submit(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    enrollment = get_object_or_404(Enrollment, user=request.user, course=course)
    questions = Question.objects.filter(course=course)
    valid_choices = Choice.objects.filter(question__in=questions)
    selected_ids = extract_answers(request)
    selected = list(valid_choices.filter(pk__in=selected_ids).select_related('question'))
    if len(selected) != len(set(selected_ids)):
        raise PermissionDenied("One or more selected answers do not belong to this course.")
    submission = Submission.objects.create(enrollment=enrollment)
    submission.choices.set(selected)
    return redirect('onlinecourse:show_exam_result', course_id=course.id, submission_id=submission.id)


@login_required
def show_exam_result(request, course_id, submission_id):
    course = get_object_or_404(Course, pk=course_id)
    submission = get_object_or_404(
        Submission.objects.select_related('enrollment__user', 'enrollment__course'),
        pk=submission_id, enrollment__course=course, enrollment__user=request.user,
    )
    questions = Question.objects.filter(course=course).prefetch_related('choice_set')
    selected_ids = list(submission.choices.values_list('id', flat=True))
    selected_by_question = {}
    for choice in submission.choices.select_related('question'):
        selected_by_question.setdefault(choice.question_id, []).append(choice)
    results = []
    possible_score = sum(question.grade for question in questions)
    score = 0
    for question in questions:
        selected = selected_by_question.get(question.id, [])
        correct = question.choice_set.filter(is_correct=True).first()
        is_correct = question.is_get_score(selected_ids)
        if is_correct:
            score += question.grade
        results.append({'question': question, 'selected': selected, 'correct': correct,
                        'is_correct': is_correct})
    passed = score >= possible_score * 0.8 if possible_score else False
    percentage = (score / possible_score * 100) if possible_score else 0
    return render(request, 'onlinecourse/exam_result_bootstrap.html', {
        'course': course, 'submission': submission, 'results': results,
        'grade': percentage, 'score': score,
        'total': possible_score, 'possible_score': possible_score,
        'possible': possible_score, 'selected_ids': selected_ids,
        'passed': passed,
    })


# <HINT> Create an exam result view to check if learner passed exam and show their question results and result for each question,
# you may implement it based on the following logic:
        # Get course and submission based on their ids
        # Get the selected choice ids from the submission record
        # For each selected choice, check if it is a correct answer or not
        # Calculate the total score
#def show_exam_result(request, course_id, submission_id):



