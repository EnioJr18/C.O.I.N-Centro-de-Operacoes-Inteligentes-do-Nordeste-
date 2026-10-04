from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from .models import UserRole


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
        response = self.client.post('/api/v1/auth/users/', {'username': 'newop', 'email': 'newop@example.com', 'password': 'StrongPassword123', 'is_superuser': True, 'is_staff': True, 'role': 'ADMIN'}, format='json')
        self.assertEqual(response.status_code, 201)
        created = User.objects.get(username='newop')
        self.assertFalse(created.is_superuser)
        self.assertFalse(created.is_staff)
        self.assertEqual(created.profile.role, UserRole.OPERADOR)
