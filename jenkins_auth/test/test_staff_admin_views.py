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

import django
django.setup()


from django.test import Client
from django.test import TestCase
from django.contrib.auth import get_user_model
from jenkins_auth.test.helper import get_template_names


User = get_user_model()


class ToggleStaffStatusCase(TestCase):
    c = Client()

    def setUp(self):
        User.objects.create_superuser(
            "admin",
            password="pwd-a",
            email='su@example.org')
        User.objects.create_user("user-1", password="pwd-1")
        User.objects.create_user("staff-1", password="pwd-1", is_staff=True)

    def test_normal_user(self):
        self.c.login(username='user-1', password='pwd-1')
        user = User.objects.get(username='user-1')
        self.assertFalse(user.is_staff)
        url = '/staff/user/{}/togglestaff/'.format(user.id)
        response = self.c.post(url, follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/home.html' in get_template_names(response.templates))

    def test_staff_user(self):
        self.c.login(username='staff-1', password='pwd-1')
        user = User.objects.get(username='user-1')
        self.assertFalse(user.is_staff)
        url = '/staff/user/{}/togglestaff/'.format(user.id)
        response = self.c.post(url, follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/home.html' in get_template_names(response.templates))

    def test_superuser(self):
        self.c.login(username='admin', password='pwd-a')
        user = User.objects.get(username='user-1')
        self.assertFalse(user.is_staff)
        url = '/staff/user/{}/togglestaff/'.format(user.id)

        # toggle on
        response = self.c.post(url, follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/staff/account_form.html' in get_template_names(response.templates))
        user = User.objects.get(username='user-1')
        self.assertTrue(user.is_staff)

        # toggle off
        response = self.c.post(url, follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/staff/account_form.html' in get_template_names(response.templates))
        user = User.objects.get(username='user-1')
        self.assertFalse(user.is_staff)
