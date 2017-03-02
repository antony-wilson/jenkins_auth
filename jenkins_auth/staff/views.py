'''
BSD Licence
Copyright (c) 2017, Science & Technology Facilities Council (STFC)
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

    * Redistributions of source code must retain the above copyright notice,
        this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright notice,
        this list of conditions and the following disclaimer in the
        documentation and/or other materials provided with the distribution.
    * Neither the name of the Science & Technology Facilities Council (STFC)
        nor the names of its contributors may be used to endorse or promote
        products derived from this software without specific prior written
        permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

'''
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin,\
    PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponseRedirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import DeleteView, ListView, UpdateView, View, DetailView
from django.views.generic.edit import FormMixin

from jenkins_auth.models import Project
from jenkins_auth.models import RegistrationProfile
from jenkins_auth.settings import ACCOUNT_EXPIRATION_DAYS, API_USER, ADMIN_USER
from jenkins_auth.staff.forms import EmailMessageForm
from jenkins_auth.utils import delete_project, logically_delete_user, get_service_email_address


User = get_user_model()

ACCOUNT_TABS = [
    ['staff_user_approval', 'Accounts waiting for staff approval',
     'Waiting Approval'],
    ['staff_user_active',
     'All active user accounts, ordered by "Last Name"',
     'Active'],
    ['staff_user_stale', 'User accounts that have not been accessed for at least {} days, ordered by "Last Logged In"'.format(
        ACCOUNT_EXPIRATION_DAYS), 'Stale'],
    ['staff_user_deleted',
     'User accounts that have been deleted, ordered by "Last Name"', 'Deleted'],
    ['staff_user_staff',
     'Users that have "staff" status, ordered by "Last Name"',
     'Staff'],
    ['staff_user_registration',
     'User accounts that have not completed registration, ordered by "Date Joined"', 'Registration Incomplete '],
]

USER_LIST_ACTIVE_TEMPLATE = 'jenkins_auth/staff/account_list_active.html'
USER_LIST_STALE_TEMPLATE = 'jenkins_auth/staff/account_list_stale.html'
USER_LIST_DELETED_TEMPLATE = 'jenkins_auth/staff/account_list_deleted.html'
USER_LIST_REGISTRATION_TEMPLATE = 'jenkins_auth/staff/account_list_registration.html'
USER_LIST_APPROVAL_TEMPLATE = 'jenkins_auth/staff/account_list_approval.html'
USER_LIST_STAFF_TEMPLATE = 'jenkins_auth/staff/account_list_staff.html'
USER_TEMPLATE = 'jenkins_auth/staff/account_form.html'
USER_REJECT_TEMPLATE = 'jenkins_auth/staff/account_confirm_reject.html'
USER_DELETE_TEMPLATE = 'user/profile_confirm_delete.html'

PROJECT_LIST_ACTIVE_TEMPLATE = 'jenkins_auth/staff/project_list_active.html'
PROJECT_LIST_APPROVAL_TEMPLATE = 'jenkins_auth/staff/project_list_approval.html'
PROJECT_TEMPLATE = 'jenkins_auth/staff/project_form.html'
PROJECT_REJECT_TEMPLATE = 'jenkins_auth/staff/project_confirm_reject.html'
PROJECT_DELETE_TEMPLATE = 'jenkins_auth/project_confirm_delete.html'

# emails
ACTIVATION_COMPLETE_EMAIL = 'registration/activation_complete_email.txt'
PROJECT_APPROVED_EMAIL = 'jenkins_auth/staff/project_approved_email.txt'


class Staff(LoginRequiredMixin, PermissionRequiredMixin):

    def has_permission(self):
        """
        Overrides method from PermissionRequiredMixin.
        """
        return self.request.user.is_staff


class UserList(Staff, ListView):
    """
    The active users.

    """
    model = User
    template_name = USER_LIST_ACTIVE_TEMPLATE

    def get_queryset(self):
        """
        user is_active = True
        """
        return (User.objects.filter(is_active=True).
                exclude(username=API_USER).
                exclude(username=ADMIN_USER).
                order_by('last_name'))

    def get_context_data(self, **kwargs):
        context = super(UserList, self).get_context_data(**kwargs)
        context['tabs'] = ACCOUNT_TABS
        context['show_projects'] = True
        return context


class UserListStale(UserList):
    """
    The active users that have not logged in for ACCOUNT_EXPIRATION_DAYS days.

    """
    template_name = USER_LIST_STALE_TEMPLATE

    def get_queryset(self):
        """
        user is_active = True
        user last_login > ACCOUNT_EXPIRATION_DAYS
        """
        old_date = timezone.now() - \
            timezone.timedelta(days=ACCOUNT_EXPIRATION_DAYS)
        return (User.objects.filter(is_active=True).
                filter(last_login__lte=old_date).
                exclude(username=API_USER).
                exclude(username=ADMIN_USER).
                order_by('last_login'))


class UserListDeleted(UserList):
    """
    The users that have been logically deleted.

    """
    template_name = USER_LIST_DELETED_TEMPLATE

    def get_queryset(self):
        """
        user is_active = False
        user registration profile = null
        """
        return User.objects.filter(is_active=False).filter(
            registrationprofile__isnull=True).order_by('last_name')

    def get_context_data(self, **kwargs):
        context = super(UserListDeleted, self).get_context_data(**kwargs)
        context['show_projects'] = False
        return context


class UserListRegistration(UserList):
    """
    The users that are have not completed registration, i.e. not confirmed their email.

    """
    template_name = USER_LIST_REGISTRATION_TEMPLATE

    def get_queryset(self):
        """
        registration profile activated = False

        """
        profiles = RegistrationProfile.objects.filter(
            activated=False).order_by('user__date_joined')
        users = []
        for reg_prof in profiles:
            users.append(reg_prof.user)
        return users

    def get_context_data(self, **kwargs):
        """
        Determine whether or not to show the delete button.

        """
        context = super(UserListRegistration, self).get_context_data(**kwargs)
        expired_registration = False
        profiles = RegistrationProfile.objects.filter(activated=False)
        for profile in profiles:
            if profile.activation_key_expired():
                expired_registration = True
        context['show_delete'] = expired_registration
        return context


class UserListApproval(UserList):
    """
    The users that have verified their email but are awaiting staff approval.

    """
    template_name = USER_LIST_APPROVAL_TEMPLATE

    def get_queryset(self):
        """
        user registration profile activated = True
        user is_active = False
        """
        profiles = RegistrationProfile.objects.filter(
            activated=True).filter(user__is_active=False).order_by('user__last_login')
        users = []
        for reg_prof in profiles:
            users.append(reg_prof.user)
        return users

    def get_context_data(self, **kwargs):
        context = super(UserListApproval, self).get_context_data(**kwargs)
        context['show_projects'] = False
        context['waiting_approval'] = True
        return context


class UserListStaff(UserList):
    """
    The users that are staff.
    """
    template_name = USER_LIST_STAFF_TEMPLATE

    def get_queryset(self):
        """
        user is_active = True
        user is_staff = True
        """
        return (User.objects.filter(is_active=True).
                filter(is_staff=True).
                exclude(username=API_USER).
                exclude(username=ADMIN_USER).
                order_by('last_name'))


class UserDetail(Staff, DetailView):
    """
    Display details about a user.

    """
    model = User
    template_name = USER_TEMPLATE

    def get_context_data(self, **kwargs):
        context = super(UserDetail, self).get_context_data(**kwargs)
        user = self.get_object()
        users_groups = user.groups.all()
        project_admin_list = Project.objects.filter(admins__in=users_groups)
        context['project_admin_list'] = project_admin_list
        project_user_list = Project.objects.filter(users__in=users_groups)
        context['project_user_list'] = project_user_list

        if user.is_active:
            context['status'] = 'active'
        else:
            try:
                if user.registrationprofile.activated:
                    context['status'] = 'approval'
                else:
                    context['status'] = 'register'
            except ObjectDoesNotExist:
                context['status'] = 'deleted'

        context['is_staff_admin'] = self.request.user.is_superuser
        return context


class UserApprove(Staff, UpdateView):
    """
    Approve a user.
    By submitting the form the user is set to active.

    """
    model = User
    fields = ['is_active']
    template_name = USER_TEMPLATE
    success_url = reverse_lazy('staff_user_approval')

    def form_valid(self, form):
        form.instance.is_active = True
        form.instance.save()
        # email user
        user = self.get_object()
        context = super(UserApprove, self).get_context_data()
        context.update({
            'user': user,
            'site': get_current_site(self.request),
        })
        message = render_to_string(ACTIVATION_COMPLETE_EMAIL, context)
        subject = 'Account creation on {site_name} approved'.format(
            site_name=get_current_site(self.request).name)
        user.email_user(
            subject,
            message,
            get_service_email_address(
                self.request))

        return super(UserApprove, self).form_valid(form)


class UserDelete(Staff, DeleteView):
    """
    Logically delete a user.

    """
    model = User
    success_url = reverse_lazy('staff_user_deleted')
    success_message = "User was successfully deleted"
    template_name = USER_DELETE_TEMPLATE

    def delete(self, request, *args, **kwargs):
        """
        Only delete the user if they do not own any projects.
        Remove the user from any groups.
        Delete the registration profile.
        Logically delete the user.
        """
        user = self.get_object()

        # We cannot delete a user if they still own projects
        project_count = Project.objects.filter(owner=user).count()
        if project_count > 0:
            messages.error(request, 'Account cannot be deleted as they own {} projects'.format(
                project_count))
            # This is the best we can do for a redirect. Anyway the user should
            # not be able to navigate here.
            return HttpResponseRedirect(reverse_lazy("staff_user_active"))

        logically_delete_user(user)

        # There is no SuccessMessageMixin on the DeleteView, so set the message
        # here
        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.success_url)


class UserReject(Staff, FormMixin, DeleteView):
    """
    Reject a user.
    A form is displayed for the staff user to provide a reason for the rejection along with a button to confirm rejection.
    The user is physically deleted and an email sent to the user.

    """
    form_class = EmailMessageForm
    model = User
    success_url = reverse_lazy('staff_user_approval')
    success_message = "User account application was rejected"
    template_name = USER_REJECT_TEMPLATE

    def get_context_data(self, **kwargs):
        context = super(UserReject, self).get_context_data(**kwargs)
        user = self.get_object()
        message = "Dear {user}, \nUnfortunately your request for the creation of an account for {username} has been declined.\n\nSincerely,\n{signed}".format(
            user=user.get_full_name(), username=user.username, signed=get_current_site(self.request).name)
        data = {'message': message}
        context['form'] = EmailMessageForm(data)
        return context

    def delete(self, request, *args, **kwargs):
        """
        Overrides method from UserDelete.

        """
        user = self.get_object()
        # check user is waiting approval ?

        form = self.get_form()
        if not form.is_valid():
            return form.form_invalid()

        # email user
        staff_message = form.cleaned_data['message']
        subject = 'Account creation on {site_name} rejected'.format(
            site_name=get_current_site(self.request).name)
        user.email_user(
            subject,
            staff_message,
            get_service_email_address(
                self.request))

        logically_delete_user(user)
        user.delete()

        # There is no SuccessMessageMixin on the DeleteView, so set the message
        # here
        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.success_url)


class UserDeleteExpiredRegistrations(Staff, View):
    """
    Delete expired user registrations from the database.

    """
    success_url = reverse_lazy('staff_user_registration')
    success_message = "Expired user registrations deleted"

    def post(self, request, *args, **kwargs):
        RegistrationProfile.objects.delete_expired_users()
        messages.success(request, self.success_message)
        return HttpResponseRedirect(self.success_url)


class ProjectList(Staff, ListView):
    model = Project
    template_name = PROJECT_LIST_ACTIVE_TEMPLATE

    def get_queryset(self):
        """
        Return the projects that are active.
        """
        return Project.objects.filter(is_active=True).order_by('name')


class ProjectListApproval(ProjectList):
    template_name = PROJECT_LIST_APPROVAL_TEMPLATE

    def get_queryset(self):
        """
        Return the new projects that are waiting for staff approval.
        """
        return Project.objects.filter(is_active=False).order_by('created_on')


class ProjectDetail(Staff, SuccessMessageMixin, DetailView):
    """
    Approve a project.
    By submitting the form the project is set to active.

    """
    model = Project
    template_name = PROJECT_TEMPLATE

    def get_context_data(self, **kwargs):
        context = super(ProjectDetail, self).get_context_data(**kwargs)
        context['is_staff_interface'] = True
        return context


class ProjectApprove(Staff, SuccessMessageMixin, UpdateView):
    """
    Approve a project.
    By submitting the form the project is set to active.

    """
    model = Project
    fields = ['is_active']
    success_url = reverse_lazy('staff_project_approval')
    success_message = "Project application was successfully approved"

    def form_valid(self, form):
        form.instance.is_active = True
        form.instance.save()

        # email project owner
        project = self.get_object()
        context = super(ProjectApprove, self).get_context_data()
        context.update({
            'project': project,
            'site': get_current_site(self.request),
        })
        message = render_to_string(PROJECT_APPROVED_EMAIL, context)
        subject = 'Project application for "{project}" approved'.format(
            project=project.name)
        project.owner.email_user(
            subject,
            message,
            get_service_email_address(
                self.request))

        return super(ProjectApprove, self).form_valid(form)


class ProjectReject(Staff, FormMixin, DeleteView):
    """
    Reject a project.
    A form is displayed for the user to provide a reason for the rejection along with a button to confirm rejection.
    The project is physically deleted and an email sent to the project owner.

    """
    form_class = EmailMessageForm
    model = Project
    success_url = reverse_lazy('staff_project_approval')
    success_message = "Project application was successfully rejected"
    template_name = PROJECT_REJECT_TEMPLATE

    def get_context_data(self, **kwargs):
        context = super(ProjectReject, self).get_context_data(**kwargs)
        project = self.get_object()
        message = "Dear {user}, \nUnfortunately your request for the creation of the project {project} has been declined.\n\nSincerely,\n{signed}".format(
            user=project.owner.get_full_name(), project=project.name, signed=get_current_site(self.request).name)
        data = {'message': message}
        context['form'] = EmailMessageForm(data)
        return context

    def delete(self, request, *args, **kwargs):
        """
        Overrides method from DeleteView.

        """
        form = self.get_form()
        if not form.is_valid():
            return form.form_invalid()

        # email project owner
        staff_message = form.cleaned_data['message']
        project = self.get_object()
        subject = 'Project application for "{project}" rejected'.format(
            project=project.name)
        project.owner.email_user(
            subject,
            staff_message,
            get_service_email_address(
                self.request))

        delete_project(self.get_object())

        # There is no SuccessMessageMixin on the DeleteView, so set the message
        # here
        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.success_url)


class ProjectDelete(Staff, DeleteView):
    """
    Delete a project.
    The project is physically deleted.

    """
    model = Project
    success_url = reverse_lazy('staff_project')
    success_message = "Project was successfully deleted"
    template_name = PROJECT_DELETE_TEMPLATE

    def delete(self, request, *args, **kwargs):
        """
        Overrides method from DeleteView.

        """
        delete_project(self.get_object())

        # There is no SuccessMessageMixin on the DeleteView, so set the message
        # here
        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.success_url)
