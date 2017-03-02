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
from jenkins_auth.settings import API_USER

User = get_user_model()


class APICase(TestCase):
    c = Client()

    def setUp(self):
        User.objects.create_user(API_USER, password="pwd-1")

    def est_not_jenkins_user(self):
        print("test_normal_user")
        User.objects.create_user("user-1", password="pwd-1")
        self.c.login(username='user-1', password='pwd-1')
        response = self.c.get('/user/user-1', follow=True)
        print(get_template_names(response.templates))
        print("xxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/home.html' in get_template_names(response.templates))

    def test_in_active_user(self):
        self.c.login(username=API_USER, password='pwd-1')
        User.objects.create_user("user-2", password="pwd-2", is_active=False)
        response = self.c.get('/user/user-2')
        self.assertEquals(response.status_code, 404)
        self.assertTrue('404.html' in get_template_names(response.templates))

    def test_unknown_user(self):
        self.c.login(username=API_USER, password='pwd-1')
        response = self.c.get('/user/unknown')
        self.assertEquals(response.status_code, 404)
        self.assertTrue('404.html' in get_template_names(response.templates))

    def test_ok(self):
        User.objects.create_user("user-1", password="pwd-1")
        self.c.login(username=API_USER, password='pwd-1')
        response = self.c.get('/user/user-1')
        self.assertEquals(response.status_code, 200)
        self.assertJSONEqual(
            response.content.decode(),
            '{"roles": {"admin": [], "user": []}, "username": "user-1"}')

    def test_ok_2(self):
        User.objects.create_user("user-1", password="pwd-1")
        User.objects.create_user("user-2", password="pwd-2")
        User.objects.create_user("user-3", password="pwd-3")
        self.c.login(username='user-1', password='pwd-1')

        # create project
        self.c.post(
            '/project/add/', {'name': 'proj 1', 'description': 'my first project'})
        # add admin and user privileges
        self.c.post('/project/1/update/',
                    {'admin_users': [User.objects.get(username='user-1').id,
                                     User.objects.get(username='user-2').id],
                     'user_users': User.objects.get(username='user-3').id})

        # create another project
        self.c.post(
            '/project/add/', {'name': 'proj 2', 'description': 'my second project'})
        # add admin and user privileges
        self.c.post('/project/2/update/',
                    {'admin_users': User.objects.get(username='user-1').id,
                     'user_users': User.objects.get(username='user-3').id})

        # create another project
        self.c.post(
            '/project/add/', {'name': 'proj 3', 'description': 'my third project'})
        # add admin and user privileges
        self.c.post('/project/3/update/',
                    {'admin_users': User.objects.get(username='user-1').id,
                     'user_users': User.objects.get(username='user-2').id})

        # create another project
        self.c.post(
            '/project/add/', {'name': 'proj 4', 'description': 'my forth project'})

        self.c.login(username=API_USER, password='pwd-1')
        response = self.c.get('/user/user-1')
        self.assertEquals(response.status_code, 200)
        self.assertJSONEqual(
            response.content.decode(),
            '{"roles": {"admin": ["proj 1", "proj 2", "proj 3", "proj 4"], "user": []}, "username": "user-1"}')

        response = self.c.get('/user/user-2')
        self.assertEquals(response.status_code, 200)
        self.assertJSONEqual(
            response.content.decode(),
            '{"roles": {"admin": ["proj 1"], "user": ["proj 3"]}, "username": "user-2"}')

        response = self.c.get('/user/user-3')
        self.assertEquals(response.status_code, 200)
        self.assertJSONEqual(
            response.content.decode(),
            '{"roles": {"admin": [], "user": ["proj 1", "proj 2"]}, "username": "user-3"}')
