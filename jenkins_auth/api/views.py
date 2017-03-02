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

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic import View

from jenkins_auth.api.basic_auth import logged_in_or_basicauth
from jenkins_auth.models import Project
from jenkins_auth.settings import API_USER


User = get_user_model()


class Role(PermissionRequiredMixin, View):
    """
    Provide information about a user. The projects they are in and their role in the projects.

    """

    @method_decorator(logged_in_or_basicauth())
    def dispatch(self, *args, **kwargs):
        return super(Role, self).dispatch(*args, **kwargs)

    def has_permission(self):
        """
        Overrides method from PermissionRequiredMixin.
        Only the API_USER is allowed to call this view
        """
        if self.request.user.username == API_USER:
            return True
        return False

    def get(self, request, username, *args, **kwargs):
        """
        This request returns the roles of the user.
        The user must be active.

        """
        user = get_object_or_404(User, username=username)
        if not user.is_active:
            raise Http404('User not active')
        user_info = _UserInfo(user)
        response = HttpResponse(content_type='application/json')
        # pylint: disable=maybe-no-member
        response.writelines(user_info.get_json())
        return response


class _UserInfo():
    """
    Create an object containing information about a user.
    {'username': 'xxxxxx',
     'roles':    {'admin': ['p1', 'p2']}
                 {'user': ['p6', 'p9']}
    }

    """
    user_info = {}

    def __init__(self, user):
        self._set_username(user)
        self._set_roles(user)

    def get_info(self):
        return self.user_info

    def get_json(self):
        return json.dumps(self.user_info, sort_keys=True)

    def _set_username(self, user):
        self.user_info['username'] = user.username

    def _set_roles(self, user):
        roles = {}
        users_groups = user.groups.all()
        projects = Project.objects.filter(
            admins__in=users_groups).filter(is_active=True)
        project_admin = []
        for project in projects:
            project_admin.append(project.name)
        roles['admin'] = project_admin

        projects = Project.objects.filter(
            users__in=users_groups).filter(is_active=True)
        project_user = []
        for project in projects:
            project_user.append(project.name)
        roles['user'] = project_user

        self.user_info['roles'] = roles
