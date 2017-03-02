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

jenkins_auth URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
'''
from django.conf.urls import include, url
from django.contrib import admin
from django.views.generic.base import TemplateView
from django.views.i18n import JavaScriptCatalog

from jenkins_auth.api.views import Role
from jenkins_auth.settings import DEBUG
from jenkins_auth.staff.views import ProjectDelete as StaffProjectDelete
from jenkins_auth.staff.views import UserList, UserListStale, UserListRegistration, \
    UserListDeleted, UserListStaff, ProjectList, ProjectListApproval, \
    ProjectDetail, UserDetail, UserListApproval, UserDelete, UserReject, ProjectReject, \
    UserDeleteExpiredRegistrations, UserApprove, ProjectApprove
from jenkins_auth.staff_admin.views import ToggleStaffStatus
from jenkins_auth.views import Home, Profile, ProfileUpdate, ProfileDelete, ProjectCreate, \
    ProjectUpdate, ProjectDelete, ProjectView, TermsOfService, Shibboleth, \
    ShibbolethUserRegistration, Login, ActivationView


urlpatterns = [

    # Login
    url(r'^accounts/login/$', Login.as_view(),
        name='login'),
    # Profile
    url(r'^accounts/profile/$', Profile.as_view(),
        name='profile'),
    # Profile change
    url(r'^accounts/profile/change/$', ProfileUpdate.as_view(),
        name='profile_change'),
    # Profile change
    url(r'^accounts/profile/delete/$', ProfileDelete.as_view(),
        name='profile_delete'),
    url(r'^accounts/activate/complete/$',
        TemplateView.as_view(
            template_name='registration/activation_complete.html'),
        name='registration_activation_complete'),
    url(r'^accounts/activate/(?P<activation_key>\w+)/$',
        ActivationView.as_view(),
        name='registration_activate'),


    ##################################################################
    # These URLs MUST be protected by shibboleth
    url(r'^accounts/shib/$', Shibboleth.as_view(), name="shib"),
    url(r'^accounts/shib/register/$',
        ShibbolethUserRegistration.as_view(), name="shib_register"),
    ##################################################################

    # pass on the rest of the accounts urls
    url(r'^accounts/', include('registration.backends.default.urls')),

    # admin views
    url(r'^staff/user/(?P<pk>[0-9]+)/togglestaff/$',
        ToggleStaffStatus.as_view(), name='admin_toggle_staff'),
    url(r'^admin/', include(admin.site.urls)),

    # needed for the FilteredSelectMultiple
    url(r'^jsi18n/$', JavaScriptCatalog.as_view(), name='javascript-catalog'),

    # User project pages
    url(r'^project/add/$', ProjectCreate.as_view(), name='project-add'),
    url(r'^project/(?P<pk>[0-9]+)/$',
        ProjectView.as_view(), name='project-detail'),
    url(r'^project/(?P<pk>[0-9]+)/update/$',
        ProjectUpdate.as_view(), name='project-update'),
    url(r'^project/(?P<pk>[0-9]+)/delete/$',
        ProjectDelete.as_view(), name='project-delete'),


    # Staff access to user accounts
    url(r'^staff/user/$', UserList.as_view(), name='staff_user_active'),
    url(r'^staff/user/approval/$', UserListApproval.as_view(),
        name='staff_user_approval'),
    url(r'^staff/user/stale/$', UserListStale.as_view(),
        name='staff_user_stale'),
    url(r'^staff/user/deleted/$', UserListDeleted.as_view(),
        name='staff_user_deleted'),
    url(r'^staff/user/registration/$', UserListRegistration.as_view(),
        name='staff_user_registration'),
    url(r'^staff/user/staff/$', UserListStaff.as_view(),
        name='staff_user_staff'),
    url(r'^staff/user/(?P<pk>[0-9]+)/$',
        UserDetail.as_view(), name='staff_user_detail'),
    url(r'^staff/user/(?P<pk>[0-9]+)/delete/$',
        UserDelete.as_view(), name='staff_user_delete'),
    url(r'^staff/user/(?P<pk>[0-9]+)/approve/$',
        UserApprove.as_view(), name='staff_user_approve'),
    url(r'^staff/user/(?P<pk>[0-9]+)/reject/$',
        UserReject.as_view(), name='staff_user_reject'),
    url(r'^staff/user/registration/delete$',
        UserDeleteExpiredRegistrations.as_view(),
        name='staff_user_registration_delete'),


    # Staff access to projects
    url(r'^staff/project/$', ProjectList.as_view(), name='staff_project'),
    url(r'^staff/project/approval/$', ProjectListApproval.as_view(),
        name='staff_project_approval'),
    url(r'^staff/project/(?P<pk>[0-9]+)/$',
        ProjectDetail.as_view(), name='staff_project_detail'),
    url(r'^staff/project/(?P<pk>[0-9]+)/approve/$',
        ProjectApprove.as_view(), name='staff_project_approve'),
    url(r'^staff/project/(?P<pk>[0-9]+)/delete/$',
        StaffProjectDelete.as_view(), name='staff_project_delete'),
    url(r'^staff/project/(?P<pk>[0-9]+)/reject/$',
        ProjectReject.as_view(), name='staff_project_reject'),

    # Terms of service
    url(r'^tos/$', TermsOfService.as_view(), name='tos'),

    # API calls
    url(r'^user/(?P<username>\S+)',
        Role.as_view(), name='api_roles'),

]

if DEBUG:
    urlpatterns += (
        url(r'^shib/', include('shibboleth.urls', namespace='shibboleth')),
    )

urlpatterns += (
    # Place holders
    url(r'../jenkins', Home.as_view(), name='jenkins'),

    # Anything else
    url(r'', Home.as_view(), name='home'),

)
