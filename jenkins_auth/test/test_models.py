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

import datetime

import django
django.setup()

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from django.test import TestCase
from django.utils.timezone import now as datetime_now

from jenkins_auth.models import JenkinsUser, JenkinsUserProfile, RegistrationProfile, Project
from jenkins_auth.utils import logically_delete_user, delete_project


class JenkinsUserTestCase(TestCase):

    def setUp(self):
        ju_1 = JenkinsUser.objects.create(
            username="shib_id",
            is_staff=True,
            email="j.s@test.org")
        JenkinsUserProfile.objects.create(
            user_id=ju_1.id,
            shib_uid="shib_id")
        ju_2 = JenkinsUser.objects.create(
            username="non_shib_user",
            email="j.j@test.org")
        JenkinsUserProfile.objects.create(
            user_id=ju_2.id)

    def test_shib_id_as_username(self):
        """Use example shib id as a username"""
        JenkinsUser.objects.create(username="CBIV/Ddgyl825NoRetYfRNAQl0E=42")

    def test_jenkins_user_shib(self):
        """User is a shibboleth user"""
        ju = JenkinsUser.objects.get(username="shib_id")
        self.assertEqual(ju.jenkinsuserprofile.shib_uid, "shib_id")
        self.assertTrue(ju.jenkinsuserprofile.is_shib_user())

    def test_jenkins_user_not_shib(self):
        """User is not a shibboleth user"""
        ju = JenkinsUser.objects.get(username="non_shib_user")
        self.assertEqual(ju.jenkinsuserprofile.shib_uid, "")
        self.assertFalse(ju.jenkinsuserprofile.is_shib_user())

    def test_jenkins_user_delete(self):
        """Check the associated user profile gets deleted"""
        ju = JenkinsUser.objects.get(username="shib_id")
        ju.delete()
        self.assertRaises(
            JenkinsUserProfile.DoesNotExist,
            JenkinsUserProfile.objects.get,
            shib_uid="shib_id")

    def test_staff_emails(self):
        """Check we only get the staff email addresses"""
        self.assertEqual(
            JenkinsUser.objects.get_staff_emails(),
            {'j.s@test.org'})


class ProjectTestCase(TestCase):

    def setUp(self):
        ju = JenkinsUser.objects.create(username="user_1")
        admins = Group.objects.create(name="p A admins")
        users = Group.objects.create(name="p A users")
        Project.objects.create(
            name="project A",
            description="test project A",
            owner=ju,
            admins=admins,
            users=users)

    def test_jenkins_user_delete(self):
        """Project owner cannot be deleted"""
        ju = JenkinsUser.objects.get(username="user_1")
        self.assertRaises(django.db.models.deletion.ProtectedError, ju.delete)

    def test_project_url(self):
        project = Project.objects.get(name="project A")
        self.assertEqual(project.get_absolute_url(), "/project/1/")


class RegistrationProfileTestCase(TestCase):
    activation_key = "8c2582f4aaf8ab5804880901b2d2dbe7b9d97f72"

    def setUp(self):
        site = Site.objects.first()
        ju_1 = JenkinsUser.objects.create(
            username="user_1")
        RegistrationProfile.objects.create_inactive_user(
            new_user=ju_1,
            site=site,
            send_email=False,
            profile_info={'activation_key': self.activation_key}
        )

        expiration_date = datetime.timedelta(
            days=(settings.ACCOUNT_ACTIVATION_DAYS))
        date_joined = datetime_now() - expiration_date
        ju_2 = JenkinsUser.objects.create(
            username="expired_reg",
            date_joined=date_joined)
        RegistrationProfile.objects.create(user=ju_2)

    def test_activate_user(self):
        """Check profile is activated but user is not"""
        activated_user = (RegistrationProfile.objects
                          .activate_user(self.activation_key))
        self.assertTrue(activated_user.registrationprofile.activated)
        self.assertFalse(activated_user.is_active)

    def test_delete_expired_users(self):
        """Check only expired user registrations are removed"""
        self.assertEqual(JenkinsUser.objects.count(), 2)
        RegistrationProfile.objects.delete_expired_users()
        self.assertEqual(JenkinsUser.objects.count(), 1)


class UtilsTestCase(TestCase):

    def setUp(self):
        ju_1 = JenkinsUser.objects.create(
            username="shib_id",
            is_staff=True,
            is_superuser=True)
        JenkinsUserProfile.objects.create(
            user_id=ju_1.id,
            shib_uid="shib_id")
        RegistrationProfile.objects.create(user=ju_1,
                                           activated=True)
        admins = Group.objects.create(name="p A admins")
        users = Group.objects.create(name="p A users")
        ju_1.groups.add(admins)
        ju_1.groups.add(users)

        Project.objects.create(
            name="project A",
            description="test project A",
            owner=ju_1,
            admins=admins,
            users=users)

    def test_logically_delete_user(self):
        """Clean out anything associated with the user"""
        ju = JenkinsUser.objects.get(username="shib_id")
        self.assertTrue(ju.is_active)
        self.assertTrue(ju.is_staff)
        self.assertTrue(ju.is_superuser)
        self.assertTrue(ju.registrationprofile.activated)
        RegistrationProfile.objects.get(user=ju)
        self.assertEqual(ju.groups.count(), 2)

        logically_delete_user(ju)

        self.assertFalse(ju.is_active)
        self.assertFalse(ju.is_staff)
        self.assertFalse(ju.is_superuser)
        self.assertRaises(
            RegistrationProfile.DoesNotExist,
            RegistrationProfile.objects.get,
            user=ju)
        self.assertEqual(ju.groups.count(), 0)
#         self.assertIsNone(ju.user_permissions)

    def test_delete_project(self):
        """Delete the project and associated Groups"""
        self.assertEqual(Project.objects.count(), 1)
        self.assertEqual(Group.objects.count(), 2)

        delete_project(Project.objects.get(name="project A"))

        self.assertEqual(Project.objects.count(), 0)
        self.assertEqual(Group.objects.count(), 0)
