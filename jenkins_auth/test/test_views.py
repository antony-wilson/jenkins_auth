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
from jenkins_auth.models import JenkinsUserProfile
from django.contrib.auth import get_user_model
from jenkins_auth.test.helper import get_template_names


User = get_user_model()


class HomeTestCase(TestCase):
    c = Client()

    def test_home_unauthenticated(self):
        response = self.c.get('/', follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'registration/login.html' in get_template_names(response.templates))

    def test_home_authenticated(self):
        User.objects.create_user("user-1", password="pwd-1", last_name="1")
        self.c.login(username='user-1', password='pwd-1')
        response = self.c.get('/')
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/home.html' in get_template_names(response.templates))


class TOSTestCase(TestCase):
    c = Client()

    def test_tos_unauthenticated(self):
        response = self.c.get('/tos/')
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/tos.html' in get_template_names(response.templates))


class LoginTestCase(TestCase):
    c = Client()

    def test_login_get(self):
        response = self.c.get('/accounts/login/')
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'registration/login.html' in get_template_names(response.templates))

    def test_login_post_unknown_user(self):
        response = self.c.post(
            '/accounts/login/', {'username': 'user-X', 'password': 'pwd-1'}, follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'registration/login.html' in get_template_names(response.templates))

    def test_login_post_bad_password(self):
        User.objects.create_user("user-1", password="pwd-1", last_name="1")
        response = self.c.post(
            '/accounts/login/', {'username': 'user-1', 'password': 'pwd-X'}, follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'registration/login.html' in get_template_names(response.templates))

    def test_login_post_ok(self):
        User.objects.create_user("user-1", password="pwd-1", last_name="1")
        response = self.c.post(
            '/accounts/login/', {'username': 'user-1', 'password': 'pwd-1'}, follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/home.html' in get_template_names(response.templates))


class JenkinsUserTestCase(TestCase):
    c = Client()
    MESSAGE_1 = 'Account user-1 has been deleted.'
    MESSAGE_2 = 'Please check your email to complete the registration process.'
    ALERT_1 = '<div class="alert alert-danger">Account cannot be deleted as you are the owner of a project</div>'
    ALERT_2 = '<div class="alert alert-danger">Account cannot be deleted as you are the owner of 2 projects</div>'

    def setUp(self):
        User.objects.create_user("user-1", password="pwd-1", last_name="1")
        User.objects.create_user("user-2", password="pwd-2", last_name="2")

    def test_delete_user(self):
        self.c.login(username='user-1', password='pwd-1')
        # delete user-1
        response = self.c.get('/accounts/profile/delete/')
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'user/profile_confirm_delete.html' in get_template_names(response.templates))
        response = self.c.post('/accounts/profile/delete/')
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'user/profile_deleted.html' in get_template_names(response.templates))
        self.assertTrue(self.MESSAGE_1 in str(response.content))

    def test_delete_user_with_project(self):
        self.c.login(username='user-1', password='pwd-1')
        # create project
        self.c.post(
            '/project/add/', {'name': 'proj 1', 'description': 'my first project'})
        response = self.c.get('/accounts/profile/delete/')
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'user/profile_confirm_delete.html' in get_template_names(response.templates))
        # cannot delete user
        response = self.c.post('/accounts/profile/delete/', follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'user/profile.html' in get_template_names(response.templates))
        self.assertTrue(self.ALERT_1 in str(response.content))

    def test_delete_user_with_projects(self):
        self.c.login(username='user-1', password='pwd-1')
        # create project
        self.c.post(
            '/project/add/', {'name': 'proj 1', 'description': 'my first project'})
        # create another project
        self.c.post(
            '/project/add/', {'name': 'proj 2', 'description': 'my second project'})
        response = self.c.get('/accounts/profile/delete/')
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'user/profile_confirm_delete.html' in get_template_names(response.templates))
        response = self.c.post('/accounts/profile/delete/', follow=True)
        self.assertEquals(response.status_code, 200)
        # cannot delete user
        self.assertTrue(
            'user/profile.html' in get_template_names(response.templates))
        self.assertTrue(self.ALERT_2 in str(response.content))

    def test_shib_register_get(self):
        persistent_id = 'shib-id'
        response = self.c.get(
            '/accounts/shib/register/',
            persistent_id=persistent_id)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'registration/registration_form_shib.html' in get_template_names(response.templates))

    def test_shib_register_get_after_post(self):
        persistent_id = 'shib-id'
        self.c.post('/accounts/shib/register/',
                    {'first_name': 'shi',
                     'last_name': 'bboleth',
                     'email': 'shib@example.org'},
                    persistent_id=persistent_id)

        response = self.c.get(
            '/accounts/shib/register/',
            persistent_id=persistent_id)
        self.assertEquals(response.status_code, 400)
        self.assertTrue(
            'registration/login.html' in get_template_names(response.templates))

    def test_shib_register_post(self):
        persistent_id = 'shib-id'
        response = self.c.post('/accounts/shib/register/',
                               {'first_name': 'shi',
                                'last_name': 'bboleth',
                                'email': 'shib@example.org'},
                               persistent_id=persistent_id,
                               follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'registration/registration_complete.html' in get_template_names(response.templates))
        self.assertTrue(self.MESSAGE_2 in str(response.content))

        shib_user = User.objects.get(username=persistent_id)
        self.assertFalse(shib_user.is_active)
        self.assertFalse(shib_user.has_usable_password())
        self.assertFalse(shib_user.registrationprofile.activated)
        self.assertEqual(shib_user.jenkinsuserprofile.shib_uid, persistent_id)

    def test_shib_register_post_after_post(self):
        persistent_id = 'shib-id'
        self.c.post('/accounts/shib/register/',
                    {'first_name': 'shi',
                     'last_name': 'bboleth',
                     'email': 'shib@example.org'},
                    persistent_id=persistent_id)

        # post the form for 'shib-id' again
        response = self.c.post('/accounts/shib/register/',
                               {'first_name': 'shi',
                                'last_name': 'bboleth',
                                'email': 'shib@example.org'},
                               persistent_id=persistent_id,
                               follow=True)
        self.assertEquals(response.status_code, 400)
        self.assertTrue(
            '400.html' in get_template_names(
                response.templates))

    def test_shib_unauthenticated(self):
        persistent_id = 'shib-id'
        response = self.c.get('/accounts/shib/',
                              persistent_id=persistent_id, follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'registration/registration_form_shib.html' in get_template_names(response.templates))

    def test_shib_authenticated_good(self):
        shib_user = User.objects.create_user("shib-user", password="shib-pwd")
        JenkinsUserProfile.objects.create(
            user_id=shib_user.id,
            shib_uid="shib-user")
        self.c.login(username='shib-user', password='shib-pwd')
        persistent_id = 'shib-user'
        response = self.c.get('/accounts/shib/',
                              persistent_id=persistent_id, follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/home.html' in get_template_names(response.templates))

    def test_shib_authenticated_empty_profile(self):
        shib_user = User.objects.create_user(
            "shib-empty-profile",
            password="shib-pwd")
        JenkinsUserProfile.objects.create(user_id=shib_user.id)
        self.c.login(username='shib-empty-profile', password='shib-pwd')
        persistent_id = 'shib-empty-profile'
        response = self.c.get('/accounts/shib/',
                              persistent_id=persistent_id, follow=True)
        self.assertEquals(response.status_code, 500)
        self.assertTrue('500.html' in get_template_names(response.templates))

    def test_shib_authenticated_no_profile(self):
        User.objects.create_user("shib-no-profile", password="shib-pwd")
        self.c.login(username='shib-no-profile', password='shib-pwd')
        persistent_id = 'shib-no-profile'
        response = self.c.get('/accounts/shib/',
                              persistent_id=persistent_id, follow=True)
        self.assertEquals(response.status_code, 500)
        self.assertTrue('500.html' in get_template_names(response.templates))

    def test_shib_authenticated_shib_inactive(self):
        shib_user = User.objects.create_user(
            username="shib-inactive",
            password="shib-pwd")
        self.c.login(username='shib-inactive', password="shib-pwd")
        shib_user.is_active = False
        shib_user.save()
        persistent_id = 'shib-inactive'
        response = self.c.get('/accounts/shib/',
                              persistent_id=persistent_id, follow=True)
        self.assertEquals(response.status_code, 400)
        self.assertTrue(
            'registration/login.html' in get_template_names(response.templates))


class ProjectTestCase(TestCase):
    c = Client()
    MESSAGE_1 = '<div class="alert alert-success">Project was created successfully</div>'
    MESSAGE_2 = '<div class="alert alert-success">Project was successfully deleted</div>'
    MESSAGE_3 = '<div class="alert alert-success">Project was updated successfully</div>'
    ALERT_1 = 'Project with this Project name already exists.'
    ALERT_2 = 'Ensure this value has at most 300 characters (it has 301)'

    def setUp(self):
        User.objects.create_user("user-1", password="pwd-1", last_name="1")
        User.objects.create_user("user-2", password="pwd-2", last_name="2")
        User.objects.create_user("user-3", password="pwd-3", last_name="3")
        User.objects.create_user("user-4", password="pwd-4", last_name="4")
        self.c.login(username='user-1', password='pwd-1')

    def test_create_project(self):
        # new project
        response = self.c.post('/project/add/',
                               {'name': 'proj 1',
                                'description': 'my first project'},
                               follow=True)
        # returns project description page
        self.assertEquals(response.status_code, 200)
        self.assertTrue(self.MESSAGE_1 in str(response.content))
        self.assertTrue(
            'jenkins_auth/project_detail.html' in get_template_names(response.templates))
        self.assertEquals(response.context['project'].name, 'proj 1')
        self.assertEquals(
            response.context['project'].description,
            'my first project')
        self.assertEquals(response.context['project'].owner.username, 'user-1')

    def test_create_project_duplicate_name(self):
        # create project
        self.c.post('/project/add/',
                    {'name': 'proj 1',
                     'description': 'my first project'})
        response = self.c.post(
            '/project/add/', {'name': 'proj 1', 'description': 'my first project'})
        self.assertEquals(response.status_code, 200)
        self.assertTrue(self.ALERT_1 in str(response.content))
        self.assertTrue(
            'jenkins_auth/project_form.html' in get_template_names(response.templates))

    def test_create_project_description_too_long(self):
        response = self.c.post(
            '/project/add/',
            {
                'name': 'proj 1',
                'description': '1234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901'},
            follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(self.ALERT_2 in str(response.content))
        self.assertTrue(
            'jenkins_auth/project_form.html' in get_template_names(response.templates))

    def test_get_project(self):
        # create project
        self.c.post(
            '/project/add/', {'name': 'proj 1', 'description': 'my first project'})
        # retrieve details
        response = self.c.get('/project/1/')
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/project_detail.html' in get_template_names(response.templates))
        self.assertEquals(response.context['project'].name, 'proj 1')
        self.assertEquals(
            response.context['project'].description,
            'my first project')
        self.assertEquals(response.context['project'].owner.username, 'user-1')

    def test_get_project_unauthorised(self):
        # create project
        self.c.post(
            '/project/add/', {'name': 'proj 1', 'description': 'my first project'})
        # check unauthorised user access
        self.c.login(username='user-2', password='pwd-2')
        response = self.c.get('/project/1/', follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/home.html' in get_template_names(response.templates))

    def test_update_project_admins_users(self):
        # create project
        self.c.post(
            '/project/add/', {'name': 'proj 1', 'description': 'my first project'})
        # add admin and user privileges
        self.c.post('/project/1/update/',
                    {'admin_users': User.objects.get(username='user-2').id,
                     'user_users': User.objects.get(username='user-3').id})
        response = self.c.get('/project/1/')
        self.assertEquals(
            response.context['project'].admins.user_set.first().username,
            'user-2')
        self.assertEquals(
            response.context['project'].users.user_set.first().username,
            'user-3')

    def test_get_project_admin_access(self):
        # create project
        self.c.post(
            '/project/add/', {'name': 'proj 1', 'description': 'my first project'})
        # add admin and user privileges
        self.c.post('/project/1/update/',
                    {'admin_users': User.objects.get(username='user-2').id,
                     'user_users': User.objects.get(username='user-3').id})
        # check user-2 (admin user) can view the project
        self.c.login(username='user-2', password='pwd-2')
        response = self.c.get('/project/1/')
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/project_detail.html' in get_template_names(response.templates))

    def test_get_project_user_access(self):
        # create project
        self.c.post(
            '/project/add/', {'name': 'proj 1', 'description': 'my first project'})
        # add admin and user privileges
        self.c.post('/project/1/update/',
                    {'admin_users': User.objects.get(username='user-2').id,
                     'user_users': User.objects.get(username='user-3').id})
        # check user-3 (plain user) can view the project
        self.c.login(username='user-3', password='pwd-3')
        response = self.c.get('/project/1/')
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/project_detail.html' in get_template_names(response.templates))

    def test_get_project_unauthorised_access(self):
        # create project
        self.c.post(
            '/project/add/', {'name': 'proj 1', 'description': 'my first project'})
        # add admin and user privileges
        self.c.post('/project/1/update/',
                    {'admin_users': User.objects.get(username='user-2').id,
                     'user_users': User.objects.get(username='user-3').id})
        # check unauthorised user access
        self.c.login(username='user-4', password='pwd-4')
        response = self.c.get('/project/1/', follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/home.html' in get_template_names(response.templates))

    def test_update_project_unauthorised_access(self):
        # create project
        self.c.post(
            '/project/add/', {'name': 'proj 1', 'description': 'my first project'})

        # check unauthorised user access
        self.c.login(username='user-2', password='pwd-2')
        response = self.c.get('/project/1/update/', follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/home.html' in get_template_names(response.templates))

    def test_update_project(self):
        # create project
        self.c.post(
            '/project/add/', {'name': 'proj 1', 'description': 'my first project'})

        # update
        # add user-2 as admin, and user-3 as user
        self.c.login(username='user-1', password='pwd-1')
        response = self.c.post('/project/1/update/',
                               {'admin_users': User.objects.get(username='user-2').id,
                                'user_users': User.objects.get(username='user-3').id},
                               follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/project_detail.html' in get_template_names(response.templates))
        self.assertTrue(self.MESSAGE_3 in str(response.content))

        # check user-2 can now update the project
        self.c.login(username='user-2', password='pwd-2')
        response = self.c.get('/project/1/update/')
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/project_form_update.html' in get_template_names(response.templates))

        # check user-3 still cannot update the project
        self.c.login(username='user-3', password='pwd-3')
        response = self.c.get('/project/1/update/', follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/home.html' in get_template_names(response.templates))

    def test_delete_project_by_admin(self):
        # create project
        self.c.post(
            '/project/add/', {'name': 'proj 1', 'description': 'my first project'})
        # add user-2 as admin, and user-3 as user
        self.c.post('/project/1/update/',
                    {'admin_users': User.objects.get(username='user-2').id,
                     'user_users': User.objects.get(username='user-3').id})

        # check user-2 (admin user) cannot delete the project
        self.c.login(username='user-2', password='pwd-2')
        response = self.c.get('/project/1/delete/', follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/home.html' in get_template_names(response.templates))

    def test_delete_project_by_user(self):
        # create project
        self.c.post(
            '/project/add/', {'name': 'proj 1', 'description': 'my first project'})
        # add user-2 as admin, and user-3 as user
        self.c.post('/project/1/update/',
                    {'admin_users': User.objects.get(username='user-2').id,
                     'user_users': User.objects.get(username='user-3').id})

        # check user-3 (plain user) cannot delete the project
        self.c.login(username='user-3', password='pwd-3')
        response = self.c.get('/project/1/delete/', follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/home.html' in get_template_names(response.templates))

    def test_delete_project_by_other_user(self):
        # create project
        self.c.post(
            '/project/add/', {'name': 'proj 1', 'description': 'my first project'})
        # add user-2 as admin, and user-3 as user
        self.c.post('/project/1/update/',
                    {'admin_users': User.objects.get(username='user-2').id,
                     'user_users': User.objects.get(username='user-3').id})
        # check user-4 cannot delete the project
        self.c.login(username='user-4', password='pwd-4')
        response = self.c.get('/project/1/delete/', follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/home.html' in get_template_names(response.templates))

    def test_delete_project_by_owner(self):
        # create project
        self.c.post(
            '/project/add/', {'name': 'proj 1', 'description': 'my first project'})
        # add user-2 as admin, and user-3 as user
        self.c.post('/project/1/update/',
                    {'admin_users': User.objects.get(username='user-2').id,
                     'user_users': User.objects.get(username='user-3').id})
        # check owner can delete
        self.c.login(username='user-1', password='pwd-1')
        response = self.c.get('/project/1/delete/')
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/project_confirm_delete.html' in get_template_names(response.templates))
        response = self.c.post('/project/1/delete/', follow=True)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            'jenkins_auth/home.html' in get_template_names(response.templates))
        self.assertTrue(self.MESSAGE_2 in str(response.content))
