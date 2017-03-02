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
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.views import logout
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import SuspiciousOperation, ValidationError
from django.core.urlresolvers import reverse
from django.db import IntegrityError
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.translation import ugettext as _
from django.views.defaults import server_error, bad_request
from django.views.generic import DetailView, TemplateView, CreateView, UpdateView, DeleteView, View
from registration import signals
from registration.backends.default.views import ActivationView as ActivationViewBase
from registration.backends.default.views import RegistrationView
from shibboleth.backends import ShibbolethRemoteUserBackend

from jenkins_auth.forms import MinimalRegistrationForm, ProjectForm
from jenkins_auth.models import Project, JenkinsUser, JenkinsUserProfile
from jenkins_auth.models import RegistrationProfile
from jenkins_auth.settings import LOCAL_ACCOUNTS
from jenkins_auth.utils import delete_project, logically_delete_user, get_service_email_address


HOME_TEMPLATE = 'jenkins_auth/home.html'
PROFILE_CHANGE_FORM_TEMPLATE = 'user/profile_change_form.html'
PROFILE_DELETE_TEMPLATE = 'user/profile_confirm_delete.html'
PROFILE_DELETED_TEMPLATE = 'user/profile_deleted.html'
PROFILE_TEMPLATE = 'user/profile.html'
PROJECT_UPDATE_FORM_TEMPLATE = 'jenkins_auth/project_form_update.html'
REGISTRATION_FORM_SHIB = 'registration/registration_form_shib.html'
TOS_TEMPLATE = 'jenkins_auth/tos.html'
LOGIN_TEMPLATE = 'registration/login.html'

# emails
ACCOUNT_REQUEST_EMAIL = 'jenkins_auth/account_request_email.txt'
PROJECT_REQUEST_EMAIL = 'jenkins_auth/project_request_email.txt'


class Home(LoginRequiredMixin, TemplateView):
    """
    Display the home page.
    This includes all of the projects the user is associated with.

    """
    template_name = HOME_TEMPLATE

    def get_context_data(self, **kwargs):
        context = super(Home, self).get_context_data(**kwargs)
        user = self.request.user
        project_owner_list = Project.objects.filter(owner=user)
        context['project_owner_list'] = project_owner_list
        users_groups = user.groups.all()
        project_admin_list = Project.objects.filter(admins__in=users_groups)
        context['project_admin_list'] = project_admin_list
        project_user_list = Project.objects.filter(users__in=users_groups)
        context['project_user_list'] = project_user_list
        if user.is_staff:
            accounts = RegistrationProfile.objects.filter(
                activated=True).filter(
                user__is_active=False).count()
            if accounts > 0:
                context['approve_accounts'] = True
            projects = Project.objects.filter(is_active=False).count()
            if projects > 0:
                context['approve_projects'] = True
        return context


class TermsOfService(TemplateView):
    """
    Display the terms of service.

    """
    template_name = TOS_TEMPLATE


class Login(View):
    """
    We have to do this to remove the get parameters, as these were causing an issue when logging in with shibboleth.
    Specifically if the 'return' parameter was set shibboleth was not returning to the required page.

    """
    login_url = reverse_lazy('login')

    def get(self, request, *args, **kwargs):
        extra_context = {'local_accounts': LOCAL_ACCOUNTS}
        try:
            request.GET['return']
        except KeyError:
            return auth_views.login(request, extra_context=extra_context)
        return HttpResponseRedirect(self.login_url)

    def post(self, request, *args, **kwargs):
        return auth_views.login(request)


class Shibboleth(View):
    """
    This must be protected by shibboleth.
    After successful shibboleth authentication users must be directed here.

    """
    template_name = PROFILE_TEMPLATE
    shib_register_url = reverse_lazy('shib_register')
    success_url = reverse_lazy('home')

    def get(self, request, *args, **kwargs):
        """
        Having logged on with shibboleth, check if user is_authenticated and is_active.

        """
        if request.user.is_authenticated():
            if not request.user.is_active:
                messages.error(
                    request, 'Access denied. Your account has not yet been activated.')
                return bad_request(
                    request, None, template_name=LOGIN_TEMPLATE)
            try:
                shib_uid = request.user.jenkinsuserprofile.shib_uid
            except JenkinsUserProfile.DoesNotExist:
                return server_error(request)
            if request.user.username != shib_uid:
                # it is remotely possible that a user could of already created
                # an account with a username equal to a shibboleth id
                return server_error(request)
            return HttpResponseRedirect(self.success_url)

        return HttpResponseRedirect(self.shib_register_url)


class ShibbolethUserRegistration(
        ShibbolethRemoteUserBackend, RegistrationView):
    """
    This must be protected by shibboleth.
    Create a local account to associate with the shibboleth

    """
    template_name = REGISTRATION_FORM_SHIB
    model = JenkinsUser
    form_class = MinimalRegistrationForm

    def get(self, request, *args, **kwargs):
        """
        Check that the persistent-id has not already been registered, before providing the form.

        """
        try:
            username = self.request.META['persistent-id']
        except KeyError:
            # hack for testing as we cannot set 'persistent-id' due to '-id'
            username = self.request.META['persistent_id']
        try:
            JenkinsUser.objects.get(username=username)
            messages.error(request, 'User already registered')
            return bad_request(
                request, None, template_name=LOGIN_TEMPLATE)
        except JenkinsUser.DoesNotExist:
            pass
        return super(ShibbolethUserRegistration, self).get(
            request, *args, **kwargs)

    def register(self, form):
        """
        Override the method from RegistrationView.
        Create a new user. Based on code from RegistrationView.register and ShibbolethRemoteUserBackend.authenticate.

        """
        site = get_current_site(self.request)
#         username = 'CBIV/Ddgyl825NoF6EM77QAQl0E=42'  # TODO
        try:
            username = self.request.META['persistent-id']
        except KeyError:
            # hack for testing as we cannot set 'persistent-id' due to '-id'
            username = self.request.META['persistent_id']
        # Note that this could be accomplished in one try-except clause, but
        # instead we use get_or_create when creating unknown users since it has
        # built-in safeguards for multiple threads.
        cleaned_data = form.cleaned_data
        new_user_instance, created = JenkinsUser.objects.get_or_create(
            username=username, defaults=cleaned_data)
        if created:
            """
            @note: setting password for user needs on initial creation of user instead of after auth.login() of middleware.
            because get_session_auth_hash() returns the salted_hmac value of salt and password.
            If it remains after the auth.login() it will return a different auth_hash
            than what's stored in session "request.session[HASH_SESSION_KEY]".
            Also we don't need to update the user's password everytime he logs in.
            """
            new_user_instance.set_unusable_password()
            new_user_instance.save()
            new_user_instance = self.configure_user(new_user_instance)
        else:
            raise SuspiciousOperation('User already registered')

        new_user = RegistrationProfile.objects.create_inactive_user(
            new_user=new_user_instance,
            site=site,
            send_email=self.SEND_ACTIVATION_EMAIL,
            request=self.request,
        )

        signals.user_registered.send(sender=self.__class__,
                                     user=new_user,
                                     request=self.request)

        jenkinsUserProfile = JenkinsUserProfile.objects.create(
            user=new_user, shib_uid=username)
        jenkinsUserProfile.save()

        return new_user


class Profile(LoginRequiredMixin, TemplateView):
    """
    Display the user's profile view.

    """
    template_name = PROFILE_TEMPLATE

    def get_context_data(self, **kwargs):
        context = super(Profile, self).get_context_data(**kwargs)
        user = self.request.user
        context['project_count'] = Project.objects.filter(owner=user).count()
        return context


class ProfileUpdate(LoginRequiredMixin, TemplateView):
    """
    Edit the user's profile.
    We cannot use the Update Template as we do not have the user id as a slug in the url.

    """
    model = JenkinsUser
    success_message = "Profile was updated successfully"
    success_url = reverse_lazy('profile')
    template_name = PROFILE_CHANGE_FORM_TEMPLATE

    def get(self, request, *args, **kwargs):
        """
        Overrides method from TemplateView.

        """
        user = request.user
        data = {}
        data['first_name'] = user.first_name
        data['last_name'] = user.last_name
        data['email'] = user.email
        form = MinimalRegistrationForm(data)
        context = super(ProfileUpdate, self).get_context_data(**kwargs)
        context['form'] = form
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        """
        Overrides method from TemplateView.

        """
        form = MinimalRegistrationForm(request.POST, instance=request.user)
        if form.is_valid:
            form.save()
            messages.success(self.request, self.success_message)
            return HttpResponseRedirect(self.success_url)

        context = super(ProfileUpdate, self).get_context_data(**kwargs)
        context['form'] = form
        return render(request, self.template_name, context)


class ProfileDelete(LoginRequiredMixin, TemplateView):
    """
    Logically delete a user.
    The user is marker as in-active, removed from all groups and all permissions are removed.
    A confirmation dialog box is shown before deleting the profile.

    """
    model = JenkinsUser
    template_name = PROFILE_DELETE_TEMPLATE
    success_message = "Profile was deleted successfully"

    def post(self, request, *args, **kwargs):
        """
        Overrides method from TemplateView.

        """
        user = self.request.user
        project_count = Project.objects.filter(owner=user).count()
        if project_count > 0:
            if project_count > 1:
                messages.error(request, 'Account cannot be deleted as you are the owner of {} projects'.format(
                    project_count))
            else:
                messages.error(
                    request,
                    'Account cannot be deleted as you are the owner of a project')
            return HttpResponseRedirect(reverse('profile'))

        logically_delete_user(user)
        context = {'username': self.request.user.username}
        return logout(
            request, template_name=PROFILE_DELETED_TEMPLATE, extra_context=context)


class ProjectView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    View a project.
    The user must be logged in and have permission to view the project.

    """
    model = Project

    def has_permission(self):
        """
        Overrides method from PermissionRequiredMixin.

        """
        # Just in case the owner removes his admin privileges
        if self.get_object().owner == self.request.user:
            return True

        # get the user group for this project
        user_group = self.get_object().users

        # check user group for this instance has read permission
        try:
            user_group.permissions.get(codename='read_project')
        except Permission.DoesNotExist:
            return self.has_admin_permission()

        # check user is a member of the user group
        try:
            self.request.user.groups.get(id=user_group.id)
        except Group.DoesNotExist:
            return self.has_admin_permission()

        return True

    def has_admin_permission(self):
        # get the admin group for this project
        admin_group = self.get_object().admins

        # check admin group for this instance has read permission
        try:
            admin_group.permissions.get(codename='read_project')
        except Permission.DoesNotExist:
            return False

        # check user is a member of the admin group
        try:
            self.request.user.groups.get(id=admin_group.id)
        except Group.DoesNotExist:
            return False

        return True


class ProjectCreate(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    """
    Create a project.
    Anyone can create a project

    """
    model = Project
    fields = ['name', 'description', ]
    success_message = "Project was created successfully"

    def form_valid(self, form):
        """
        Overrides method from CreateView.

        """
        form.instance.owner = self.request.user
        # admin group
        try:
            admin_group = Group.objects.create(
                name='{} | admins'.format(form.instance.name))
        except IntegrityError:
            print(
                "ERROR Group '{} | admins' exists without a corresponding project".format(
                    form.instance.name))
            form.add_error(
                "name",
                ValidationError(
                    _('Project with this Project name already exists.'),
                    code='IntegrityError'))
            return super(ProjectCreate, self).form_invalid(form)

        update_project = Permission.objects.get(codename='change_project')
        admin_group.permissions.add(update_project)
        read_project = Permission.objects.get(codename='delete_project')
        admin_group.permissions.add(read_project)
        read_project = Permission.objects.get(codename='read_project')
        admin_group.permissions.add(read_project)
        form.instance.admins = admin_group
        # add owner as admin
        self.request.user.groups.add(admin_group)

        # user group
        try:
            user_group = Group.objects.create(
                name='{} | users'.format(form.instance.name))
        except IntegrityError:
            print(
                "ERROR Group '{} | users' exists without a corresponding project".format(
                    form.instance.name))
            form.add_error(
                "name",
                ValidationError(
                    _('Project with this Project name already exists.'),
                    code='IntegrityError'))
            return super(ProjectCreate, self).form_invalid(form)
        user_group.permissions.add(read_project)
        form.instance.users = user_group

        form.instance.is_active = True

        admin_group.save()
        user_group.save()
        form.instance.save()

        # email
#         context = super(ProjectCreate, self).get_context_data()
#         context.update({
#             'project': form.instance,
#             'site': get_current_site(self.request),
#         })
#         subject = 'Project requires approval'
#         message = render_to_string(PROJECT_REQUEST_EMAIL, context)
#         JenkinsUser.objects.email_staff(
#             subject,
#             message,
#             get_service_email_address(
#                 self.request))

        return super(ProjectCreate, self).form_valid(form)


class ProjectUpdate(
        LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    """
    Update a project.
    Only members of the projects admin group can update the project.

    """
    model = Project
    template_name = PROJECT_UPDATE_FORM_TEMPLATE
    success_message = "Project was updated successfully"
    form_class = ProjectForm

    def has_permission(self):
        """
        Overrides method from PermissionRequiredMixin.

        """
        # Just in case the owner removes his admin privileges
        if self.get_object().owner == self.request.user:
            return True

        # get the admin group for this project
        admin_group = self.get_object().admins

        # check admin group for this instance has update permission
        try:
            admin_group.permissions.get(codename='change_project')
        except Permission.DoesNotExist:
            return False

        # check user is a member of the admin group
        try:
            self.request.user.groups.get(id=admin_group.id)
        except Group.DoesNotExist:
            return False

        return True


class ProjectDelete(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """
    Delete a project.
    Only the project owner can delete the project.

    """
    model = Project
    success_url = reverse_lazy('home')
    success_message = "Project was successfully deleted"

    def has_permission(self):
        """
        Overrides method from PermissionRequiredMixin.

        """
        if self.get_object().owner == self.request.user:
            return True
        return False

    def delete(self, request, *args, **kwargs):
        """
        Overrides method from DeleteView.

        """
        project = self.get_object()
        delete_project(project)
        # There is no SuccessMessageMixin on the DeleteView, so set the message
        # here
        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.success_url)


class ActivationView(ActivationViewBase):
    """
    Re-implements registration.backends.default.views in order to use our version of RegistrationProfile.

    """

    def activate(self, *args, **kwargs):
        """
        Re-implements registration.backends.default.views in order to use our version of RegistrationProfile.

        """
        activation_key = kwargs.get('activation_key', '')
        activated_user = (RegistrationProfile.objects
                          .activate_user(activation_key))
        if activated_user:

            if not activated_user.is_active:
                # send mail to staff
                context = super(
                    ActivationView,
                    self).get_context_data(
                    **kwargs)
                context.update({
                    'activated_user': activated_user.get_full_name(),
                    'activated_username': activated_user.username,
                    'activated_id': activated_user.id,
                    'site': get_current_site(self.request),
                })
                subject = 'User account requires approval'
                message = render_to_string(ACCOUNT_REQUEST_EMAIL, context)
                JenkinsUser.objects.email_staff(
                    subject,
                    message,
                    get_service_email_address(
                        self.request))

            signals.user_activated.send(sender=self.__class__,
                                        user=activated_user,
                                        request=self.request)
        return activated_user
