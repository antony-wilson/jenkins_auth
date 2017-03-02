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
from django.contrib.auth.models import Group, User
from django.core.mail import send_mail
from django.db import models
from django.urls import reverse
from registration.models import RegistrationManager as RegistrationManagerBase
from registration.models import RegistrationProfile as RegistrationProfileBase
from registration.models import SHA1_RE
from registration.users import UserModel


# from jenkins_auth.utils import validate_shibboleth_username
# User = UserModel()
class JenkinsUserManager(models.Manager):

    def email_staff(self, subject, message, _from):
        send_mail(
            subject,
            message,
            _from,
            self.get_staff_emails(),
            fail_silently=False,
        )

    def get_staff_emails(self):
        """
        Get a list of staff email addresses.

        """
        staff = JenkinsUser.objects.filter(is_staff=True)
        email = set()
        for person in staff:
            email.add(person.email)
        return email


class JenkinsUser(User):
    """
    A User model with a custom username validator.

    """
    objects = JenkinsUserManager()

    def __init__(self, *args, **kwargs):
        super(JenkinsUser, self).__init__(*args, **kwargs)
        self._meta.get_field('username').validators = [
            validate_shibboleth_username]

    class Meta:
        proxy = True


class JenkinsUserProfile(models.Model):
    """
    Additional information about a user.

    """
    user = models.OneToOneField(JenkinsUser, on_delete=models.CASCADE)
    shib_uid = models.CharField('Shibboleth UID', max_length=100, unique=True)

    def is_shib_user(self):
        # The shiboleth module requires that the username is set to the
        # Shibboleth ID. To ensure that this is a real Shibbolth ID, we compare
        # it to the value stored in shib_uid
        return self.shib_uid == self.user.username


class Project(models.Model):
    name = models.CharField('Project name', max_length=200, unique=True,
                            help_text='A human readable name for the project that must be unique.')
    description = models.TextField(
        max_length=300, blank=True, help_text='A description of the project, up to 300 characters long.')
    # a project should not be left without an owner and we do not want to
    # automatically delete the project
    owner = models.ForeignKey(
        JenkinsUser, related_name='project_owner', on_delete=models.PROTECT)
    admins = models.ForeignKey(
        Group, related_name='project_admin', on_delete=models.CASCADE)
    users = models.ForeignKey(
        Group, related_name='project_user', on_delete=models.CASCADE)
    is_active = models.BooleanField(
        'Active', default=False, help_text='Designates whether this project should be treated as active.')
    created_on = models.DateTimeField(auto_now_add=True)

    def get_absolute_url(self):
        return reverse('project-detail', kwargs={'pk': self.pk})

    class Meta:
        permissions = (
            ('read_project', 'Can read project'),
        )


class RegistrationManager(RegistrationManagerBase):
    """
    Override the class from the registration module.

    """

    def activate_user(self, activation_key):
        """
        Validate an activation key and activate the corresponding
        ``User`` if valid.

        This overrides the method in the base class. The user does NOT get
        activated when the profile is activated.

        If the key is valid and has not expired, return the ``User``
        after activating.

        If the key is not valid or has expired, return ``False``.

        If the key is valid but the ``User`` is already active,
        return ``User``.

        If the key is valid but the ``User`` is inactive, return ``False``.

        To prevent reactivation of an account which has been
        deactivated by site administrators, ``RegistrationProfile.activated``
        is set to ``True`` after successful activation.

        """
        # Make sure the key we're trying conforms to the pattern of a
        # SHA1 hash; if it doesn't, no point trying to look it up in
        # the database.
        if SHA1_RE.search(activation_key):
            try:
                profile = self.get(activation_key=activation_key)
            except self.model.DoesNotExist:
                # This is an actual activation failure as the activation
                # key does not exist. It is *not* the scenario where an
                # already activated User reuses an activation key.
                return False

            if profile.activated:
                # The User has already activated and is trying to activate
                # again. If the User is active, return the User. Else,
                # return False as the User has been deactivated by a site
                # administrator.
                if profile.user.is_active:
                    return profile.user
                else:
                    return False

            if not profile.activation_key_expired():
                profile.activated = True
                profile.save()
                return profile.user
        return False

    def delete_expired_users(self):
        """
        Remove expired instances of ``RegistrationProfile`` and their
        associated ``User``s.

        This overrides the method in the base class. Rather than checking
            ``if not user.is_active:``
        this method uses
            ``if not profile.activated:``

        Accounts to be deleted are identified by searching for
        instances of ``RegistrationProfile`` with expired activation
        keys, and then checking to see if their profile has the field
        ``activated`` set to ``False``; any ``RegistrationProfile`` which
        is both inactive and has an expired activation key will be deleted.

        It is recommended that this method be executed regularly as
        part of your routine site maintenance; this application
        provides a custom management command which will call this
        method, accessible as ``manage.py cleanupregistration``.

        Regularly clearing out accounts which have never been
        activated serves two useful purposes:

        1. It alleviates the occasional need to reset a
           ``RegistrationProfile`` and/or re-send an activation email
           when a user does not receive or does not act upon the
           initial activation email; since the account will be
           deleted, the user will be able to simply re-register and
           receive a new activation key.

        2. It prevents the possibility of a malicious user registering
           one or more accounts and never activating them (thus
           denying the use of those usernames to anyone else); since
           those accounts will be deleted, the usernames will become
           available for use again.

        If you have a troublesome ``User`` and wish to disable their
        account while keeping it in the database, simply delete the
        associated ``RegistrationProfile``; an inactive ``User`` which
        does not have an associated ``RegistrationProfile`` will not
        be deleted.

        """
        for profile in self.all():
            try:
                if profile.activation_key_expired():
                    user = profile.user
                    if not profile.activated:
                        user.delete()
                        profile.delete()
            except UserModel().DoesNotExist:
                profile.delete()


class RegistrationProfile(RegistrationProfileBase):
    """
    Override RegistrationProfile in order to use our manager

    """
    objects = RegistrationManager()

    class Meta:
        proxy = True


def validate_shibboleth_username(value):
    """
    Custom username validator.
    Allow shibboleth uids as valid usernames.

    """
    # TODO add some validation based on shibboleth uid
    pass
