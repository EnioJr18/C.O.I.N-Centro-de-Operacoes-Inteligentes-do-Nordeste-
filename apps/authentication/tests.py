from django.contrib.auth.models import User
from django.test import TestCase
import json
from rest_framework.test import APIClient
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from .models import UserProfile, UserRole


class AuthenticationTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('operator', 'operator@example.com', 'StrongPassword123')
        self.client = APIClient()
    def test_login_refresh_and_me_do_not_expose_password(self):
        response = self.client.post('/api/v1/auth/login/', {'email': 'operator@example.com', 'password': 'StrongPassword123'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        me = self.client.get('/api/v1/auth/me/')
        self.assertEqual(me.status_code, 200)
        self.assertNotIn('password', me.data)
        self.assertEqual(self.client.post('/api/v1/auth/refresh/', {'refresh': response.data['refresh']}, format='json').status_code, 200)
    def test_invalid_inactive_and_anonymous_requests_are_rejected(self):
        self.assertEqual(self.client.post('/api/v1/auth/login/', {'email': 'operator@example.com', 'password': 'wrong'}, format='json').status_code, 401)
        self.user.is_active = False; self.user.save()
        self.assertEqual(self.client.post('/api/v1/auth/login/', {'email': 'operator@example.com', 'password': 'StrongPassword123'}, format='json').status_code, 401)
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 401)
    def test_operator_is_forbidden_from_administration_and_admin_is_allowed(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/v1/auth/users/').status_code, 403)
        admin = User.objects.create_superuser('admin', 'admin@example.com', 'StrongPassword123')
        self.client.force_authenticate(admin)
        self.assertEqual(self.client.get('/api/v1/auth/users/').status_code, 200)
        response = self.client.post('/api/v1/auth/users/', {'username': 'newop', 'email': 'newop@example.com', 'password': 'StrongPassword123'}, format='json')
        self.assertEqual(response.status_code, 201)
        created = User.objects.get(username='newop')
        self.assertFalse(created.is_superuser)
        self.assertFalse(created.is_staff)
        self.assertEqual(created.profile.role, UserRole.OPERADOR)

    def login(self, user=None, password='StrongPassword123'):
        user = user or self.user
        return self.client.post('/api/v1/auth/login/', {'email': user.email, 'password': password}, format='json')

    def authenticate(self, user=None):
        response = self.login(user)
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        return response.data

    def test_profile_patch_accepts_partial_and_blank_names_for_operator(self):
        self.authenticate()
        response = self.client.patch('/api/v1/auth/me/', {'first_name': '  Ana  '}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['first_name'], 'Ana')
        self.assertEqual(response.data['email'], 'operator@example.com')
        self.assertEqual(response.data['role'], UserRole.OPERADOR)
        self.assertNotIn('password', response.data)
        response = self.client.patch('/api/v1/auth/me/', {'last_name': ''}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['last_name'], '')

    def test_profile_patch_allows_admin_and_active_superuser(self):
        admin = User.objects.create_user('admin-role', 'admin-role@example.com', 'StrongPassword123')
        admin.profile.role = UserRole.ADMIN
        admin.profile.save(update_fields=['role'])
        superuser = User.objects.create_superuser('super', 'super@example.com', 'StrongPassword123')
        for user in (admin, superuser):
            self.client.force_authenticate(user)
            response = self.client.patch('/api/v1/auth/me/', {'first_name': 'Gestor'}, format='json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['role'], UserRole.ADMIN)

    def test_profile_patch_rejects_privileged_unknown_empty_and_cross_user_payloads_atomically(self):
        other = User.objects.create_user('other', 'other@example.com', 'StrongPassword123')
        self.user.first_name = 'Original'
        self.user.save(update_fields=['first_name'])
        self.authenticate()
        forbidden_payloads = [
            {'first_name': 'Alterado', 'email': 'attacker@example.com'},
            {'first_name': 'Alterado', 'role': 'ADMIN'},
            {'first_name': 'Alterado', 'is_active': False},
            {'first_name': 'Alterado', 'is_staff': True},
            {'first_name': 'Alterado', 'is_superuser': True},
            {'first_name': 'Alterado', 'password': 'raw-password'},
            {'first_name': 'Alterado', 'username': 'attacker'},
            {'first_name': 'Alterado', 'unknown': 'value'},
            {'first_name': 'Alterado', 'id': other.id},
            {},
        ]
        for payload in forbidden_payloads:
            response = self.client.patch('/api/v1/auth/me/', payload, format='json')
            self.assertEqual(response.status_code, 400, payload)
            self.user.refresh_from_db()
            self.assertEqual(self.user.first_name, 'Original')
            self.assertEqual(self.user.email, 'operator@example.com')
            self.assertFalse(self.user.is_staff)
            self.assertFalse(self.user.is_superuser)
            self.assertTrue(self.user.is_active)
        other.refresh_from_db()
        self.assertEqual(other.first_name, '')

    def test_profile_writes_reject_anonymous_inactive_and_user_without_profile(self):
        self.assertEqual(self.client.patch('/api/v1/auth/me/', {'first_name': 'Ana'}, format='json').status_code, 401)
        token = str(AccessToken.for_user(self.user))
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(self.client.patch('/api/v1/auth/me/', {'first_name': 'Ana'}, format='json').status_code, 401)
        self.user.is_active = True
        self.user.save(update_fields=['is_active'])
        token = str(AccessToken.for_user(self.user))
        UserProfile.objects.filter(user=self.user).delete()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(self.client.patch('/api/v1/auth/me/', {'first_name': 'Ana'}, format='json').status_code, 403)

    def test_password_change_validates_input_and_uses_django_hashing(self):
        self.authenticate()
        invalid_payloads = [
            ({}, None),
            ({'current_password': 'wrong', 'new_password': 'DifferentPassword123', 'new_password_confirmation': 'DifferentPassword123'}, 'current_password'),
            ({'current_password': 'StrongPassword123', 'new_password': 'DifferentPassword123', 'new_password_confirmation': 'OtherPassword123'}, 'new_password_confirmation'),
            ({'current_password': 'StrongPassword123', 'new_password': 'StrongPassword123', 'new_password_confirmation': 'StrongPassword123'}, 'new_password'),
            ({'current_password': 'StrongPassword123', 'new_password': 'short', 'new_password_confirmation': 'short'}, 'new_password'),
        ]
        for payload, field in invalid_payloads:
            response = self.client.post('/api/v1/auth/me/password/', payload, format='json')
            self.assertEqual(response.status_code, 400)
            if field:
                self.assertIn(field, response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('StrongPassword123'))

    def test_password_change_revokes_old_credentials_and_new_login_works(self):
        tokens = self.authenticate()
        response = self.client.post('/api/v1/auth/me/password/', {
            'current_password': 'StrongPassword123',
            'new_password': 'DifferentPassword123',
            'new_password_confirmation': 'DifferentPassword123',
        }, format='json')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b'')
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 401)
        self.client.credentials()
        refresh = self.client.post('/api/v1/auth/refresh/', {'refresh': tokens['refresh']}, format='json')
        self.assertEqual(refresh.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.data['access']}")
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 401)
        self.client.credentials()
        self.assertEqual(self.login(password='StrongPassword123').status_code, 401)
        new_login = self.login(password='DifferentPassword123')
        self.assertEqual(new_login.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_login.data['access']}")
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 200)

    def test_tokens_without_password_hash_claim_are_invalidated(self):
        legacy_access = AccessToken.for_user(self.user)
        legacy_access.payload.pop(api_settings.REVOKE_TOKEN_CLAIM, None)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {legacy_access}')
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 401)
        legacy_refresh = RefreshToken.for_user(self.user)
        legacy_refresh.payload.pop(api_settings.REVOKE_TOKEN_CLAIM, None)
        self.client.credentials()
        refreshed = self.client.post('/api/v1/auth/refresh/', {'refresh': str(legacy_refresh)}, format='json')
        self.assertEqual(refreshed.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refreshed.data['access']}")
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 401)

    def test_password_change_rejects_anonymous_inactive_and_user_without_profile(self):
        payload = {'current_password': 'StrongPassword123', 'new_password': 'DifferentPassword123', 'new_password_confirmation': 'DifferentPassword123'}
        self.assertEqual(self.client.post('/api/v1/auth/me/password/', payload, format='json').status_code, 401)
        token = str(AccessToken.for_user(self.user))
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(self.client.post('/api/v1/auth/me/password/', payload, format='json').status_code, 401)
        self.user.is_active = True
        self.user.save(update_fields=['is_active'])
        token = str(AccessToken.for_user(self.user))
        self.user.profile.delete()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(self.client.post('/api/v1/auth/me/password/', payload, format='json').status_code, 403)

    def test_openapi_documents_profile_and_password_contracts(self):
        response = self.client.get('/api/schema/?format=json')
        self.assertEqual(response.status_code, 200)
        schema = json.loads(response.content)
        profile = schema['paths']['/api/v1/auth/me/']['patch']
        password = schema['paths']['/api/v1/auth/me/password/']['post']
        self.assertIn('requestBody', profile)
        self.assertEqual(set(('200', '400', '401', '403')) - set(profile['responses']), set())
        self.assertIn('requestBody', password)
        self.assertEqual(set(('204', '400', '401', '403')) - set(password['responses']), set())
