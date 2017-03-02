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
from django.contrib.sites.shortcuts import get_current_site

from jenkins_auth.models import RegistrationProfile


def logically_delete_user(user):
    """
    Delete a users registration profile, remove the user from all groups, remove
    all permissions and logically delete the user.

    """
    try:
        profile = RegistrationProfile.objects.get(user=user)
        profile.delete()
    except RegistrationProfile.DoesNotExist:
        pass
    user.groups.clear()
    user.user_permissions.clear()
    user.is_staff = False
    user.is_superuser = False
    # logically delete the user
    user.is_active = False
    user.save()


def delete_project(project):
    """
    Delete a project.

    """
    # delete the foreign objects
    project.users.delete()
    project.admins.delete()
    try:
        # the project should have been delete with the cascade
        project.delete()
    except AttributeError:
        pass


def get_service_email_address(request):
    """
    Get the email address to use in the from field.

    """
    current_site = get_current_site(request).domain
    # TODO This is to allow to work in testing
    if current_site.startswith('127.0.0.1'):
        current_site = 'localhost.esc.rl.ac.uk'
    email = 'webmaster@{}'.format(current_site)
    return email
