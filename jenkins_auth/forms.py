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
from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.forms import ModelForm
from django.urls import reverse_lazy
from django.utils.translation import ugettext_lazy as _
from registration.forms import RegistrationForm as RegistrationFormBase
from registration.users import UserModel, UsernameField

from jenkins_auth.models import JenkinsUser, Project
from jenkins_auth.settings import API_USER, ADMIN_USER


User = UserModel()


class RegistrationFormTermsOfService(RegistrationFormBase):
    """
    Subclass of ``RegistrationForm`` which adds first_name and last_name.

    """
    first_name = forms.CharField(label=_("First name"))
    last_name = forms.CharField(label=_("Last name"))

    class Meta:
        model = User
        fields = (UsernameField(), "first_name", "last_name", "email")


class MinimalRegistrationForm(ModelForm):
    """
    A form for gathering user details, which does not require a password field.
    The JenkinsUser model is used instead of the standard User model in order
    to allow us to use the shibboleth uid as the username.
    """

    first_name = forms.CharField(label=_("First name"))
    last_name = forms.CharField(label=_("Last name"))
    email = forms.EmailField(label=_("E-mail"))

    class Meta:
        model = JenkinsUser
        fields = ('first_name', 'last_name', 'email')


class UserMultipleModelChoiceField(forms.ModelMultipleChoiceField):

    def label_from_instance(self, obj):
        return "{full_name} (id:{id})".format(
            full_name=obj.get_full_name(), id=obj.id)


class ProjectForm(forms.ModelForm):
    admin_users = UserMultipleModelChoiceField(
        queryset=(JenkinsUser.objects.
                  filter(is_active=True).
                  exclude(username=API_USER).
                  exclude(username=ADMIN_USER)),
        required=False,
        label=_("Admins"),
        widget=FilteredSelectMultiple(
            verbose_name=('Admins'),
            is_stacked=False,
        )
    )
    user_users = UserMultipleModelChoiceField(
        queryset=(JenkinsUser.objects.
                  filter(is_active=True).
                  exclude(username=API_USER).
                  exclude(username=ADMIN_USER)),
        required=False,
        label=_("Users"),
        widget=FilteredSelectMultiple(
            verbose_name=('Users'),
            is_stacked=False
        )
    )

    class Meta:
        model = Project
        fields = ('description', )

    class Media:
        css = {
            'all': ('jenkins_auth/css/jenkins_auth_selector.css',),
        }
        js = (reverse_lazy('javascript-catalog'),)

    def __init__(self, *args, **kwargs):
        super(ProjectForm, self).__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.fields[
                'admin_users'].initial = self.instance.admins.user_set.all()
            self.fields[
                'user_users'].initial = self.instance.users.user_set.all()

    def save(self, commit=True):
        project = super(ProjectForm, self).save(commit=commit)

        if commit:
            project.admins.user_set = self.cleaned_data['admin_users']
            project.users.user_set = self.cleaned_data['user_users']
        else:
            old_save_m2m = self.save_m2m

            def new_save_m2m():
                old_save_m2m()
                project.admins.user_set = self.cleaned_data['admin_users']
                project.users.user_set = self.cleaned_data['user_users']
            self.save_m2m = new_save_m2m
        return project
