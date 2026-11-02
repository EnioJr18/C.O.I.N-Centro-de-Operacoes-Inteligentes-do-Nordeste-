from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.contrib import admin
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.auth.models import User
from django.db import close_old_connections
from django.urls import reverse
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from rest_framework.test import APIClient

from .models import UserAdministrationAction, UserAdministrationEvent, UserProfile, UserRole
from .services import (
    UserAdministrationConflictError,
    UserAdministrationForbiddenError,
    change_user_role,
    set_user_active,
    update_managed_user,
)


PASSWORD = 'StrongPassword123'


class UserAdministrationAPITestCase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', 'admin@example.com', PASSWORD)
        self.admin.profile.role = UserRole.ADMIN
        self.admin.profile.save(update_fields=['role'])
        self.operator = User.objects.create_user('operator', 'operator@example.com', PASSWORD)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_list_is_paginated_searchable_filterable_ordered_and_has_no_n_plus_one(self):
        User.objects.create_user('ana', 'ana@example.com', PASSWORD, first_name='Ana', last_name='Silva')
        inactive = User.objects.create_user('inactive', 'inactive@example.com', PASSWORD, is_active=False)
        second_admin = User.objects.create_user('manager', 'manager@example.com', PASSWORD)
        second_admin.profile.role = UserRole.ADMIN
        second_admin.profile.save(update_fields=['role'])
        superuser = User.objects.create_superuser('root', 'root@example.com', PASSWORD)
        no_profile = User.objects.create_user('legacy', 'legacy@example.com', PASSWORD)
        no_profile.profile.delete()

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get('/api/v1/auth/users/')
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 3)
        self.assertIn('count', response.data)
        by_name = {item['username']: item for item in response.data['results']}
        self.assertEqual(by_name['root']['role'], UserRole.ADMIN)
        self.assertTrue(by_name['root']['is_superuser'])
        self.assertIsNone(by_name['legacy']['role'])
        self.assertIn('date_joined', by_name['ana'])

        self.assertEqual(self.client.get('/api/v1/auth/users/?search=SILVA').data['count'], 1)
        self.assertEqual(self.client.get('/api/v1/auth/users/?role=ADMIN').data['count'], 3)
        self.assertEqual(self.client.get('/api/v1/auth/users/?is_active=false').data['results'][0]['id'], inactive.id)
        ordered = self.client.get('/api/v1/auth/users/?ordering=username').data['results']
        self.assertEqual([item['username'] for item in ordered], sorted(item['username'] for item in ordered))
        for query in ('role=INVALID', 'is_active=maybe', 'ordering=email', 'page=0', 'unknown=value'):
            self.assertEqual(self.client.get(f'/api/v1/auth/users/?{query}').status_code, 400)

    def test_role_filters_match_serialized_roles_status_and_missing_profiles(self):
        active_admin = User.objects.create_user('active-admin', 'active-admin@example.com', PASSWORD)
        active_admin.profile.role = UserRole.ADMIN
        active_admin.profile.save(update_fields=['role'])
        inactive_admin = User.objects.create_user(
            'inactive-admin', 'inactive-admin@example.com', PASSWORD, is_active=False,
        )
        inactive_admin.profile.role = UserRole.ADMIN
        inactive_admin.profile.save(update_fields=['role'])
        active_root = User.objects.create_superuser('active-root', 'active-root@example.com', PASSWORD)
        inactive_root = User.objects.create_superuser('inactive-root', 'inactive-root@example.com', PASSWORD)
        inactive_root.is_active = False
        inactive_root.save(update_fields=['is_active'])
        missing_profile = User.objects.create_user('legacy', 'legacy@example.com', PASSWORD)
        missing_profile.profile.delete()

        operators = self.client.get('/api/v1/auth/users/?role=OPERADOR').data['results']
        self.assertNotIn(active_root.id, {item['id'] for item in operators})
        self.assertTrue(all(item['role'] == UserRole.OPERADOR for item in operators))

        active_admins = self.client.get('/api/v1/auth/users/?role=ADMIN&is_active=true').data['results']
        self.assertEqual(
            {item['id'] for item in active_admins},
            {self.admin.id, active_admin.id, active_root.id},
        )
        self.assertTrue(all(item['role'] == UserRole.ADMIN and item['is_active'] for item in active_admins))

        inactive_admins = self.client.get('/api/v1/auth/users/?role=ADMIN&is_active=false').data['results']
        self.assertEqual({item['id'] for item in inactive_admins}, {inactive_admin.id, inactive_root.id})
        self.assertTrue(all(item['role'] == UserRole.ADMIN and not item['is_active'] for item in inactive_admins))

        for role in (UserRole.ADMIN, UserRole.OPERADOR):
            results = self.client.get(f'/api/v1/auth/users/?role={role}').data['results']
            self.assertNotIn(missing_profile.id, {item['id'] for item in results})
        unfiltered = self.client.get('/api/v1/auth/users/?search=legacy').data['results']
        self.assertEqual(unfiltered[0]['role'], None)

    def test_list_permissions_and_pagination(self):
        for index in range(23):
            User.objects.create_user(f'user{index}', f'user{index}@example.com', PASSWORD)
        response = self.client.get('/api/v1/auth/users/')
        self.assertEqual(len(response.data['results']), 20, response.data)
        self.assertIsNotNone(response.data['next'])
        self.client.force_authenticate(self.operator)
        self.assertEqual(self.client.get('/api/v1/auth/users/').status_code, 403)
        self.client.force_authenticate()
        self.assertEqual(self.client.get('/api/v1/auth/users/').status_code, 401)
        superuser = User.objects.create_superuser('root', 'root@example.com', PASSWORD)
        self.client.force_authenticate(superuser)
        self.assertEqual(self.client.get('/api/v1/auth/users/').status_code, 200)

    def test_create_normalizes_email_rejects_duplicates_and_audits(self):
        payload = {
            'username': 'newop', 'email': '  NEWOP@Example.COM  ',
            'first_name': 'Novo', 'last_name': 'Operador', 'password': PASSWORD,
        }
        response = self.client.post('/api/v1/auth/users/', payload, format='json', HTTP_X_REQUEST_ID='client-controlled')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['email'], 'newop@example.com')
        self.assertFalse(response.data['is_superuser'])
        self.assertNotIn('password', response.data)
        created = User.objects.get(username='newop')
        self.assertTrue(created.is_active)
        self.assertEqual(created.profile.role, UserRole.OPERADOR)
        event = UserAdministrationEvent.objects.get(action=UserAdministrationAction.USER_CREATED)
        self.assertEqual((event.actor, event.target), (self.admin, created))
        self.assertEqual(event.request_id, response['X-Request-ID'])
        self.assertNotEqual(event.request_id, 'client-controlled')

        inactive = User.objects.create_user('old', '  Duplicate@Example.COM ', PASSWORD, is_active=False)
        self.assertFalse(inactive.is_active)
        duplicate = {**payload, 'username': 'duplicate', 'email': 'duplicate@example.com'}
        self.assertEqual(self.client.post('/api/v1/auth/users/', duplicate, format='json').status_code, 400)

    def test_create_rejects_invalid_and_privileged_payloads_atomically(self):
        base = {'username': 'newop', 'email': 'newop@example.com', 'password': PASSWORD}
        invalid = [
            {**base, 'email': ''},
            {**base, 'email': 'not-an-email'},
            {**base, 'password': 'short'},
            {**base, 'role': 'ADMIN'},
            {**base, 'is_superuser': True},
            {**base, 'is_staff': True},
            {**base, 'is_active': False},
            {**base, 'unknown': True},
        ]
        for payload in invalid:
            response = self.client.post('/api/v1/auth/users/', payload, format='json')
            self.assertEqual(response.status_code, 400, payload)
        self.assertFalse(User.objects.filter(username='newop').exists())
        self.assertFalse(UserAdministrationEvent.objects.exists())

    def test_detail_update_and_protected_targets(self):
        detail = self.client.get(f'/api/v1/auth/users/{self.operator.id}/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(self.client.get('/api/v1/auth/users/999999/').status_code, 404)
        response = self.client.patch(
            f'/api/v1/auth/users/{self.operator.id}/',
            {'first_name': '  Ana  '}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['first_name'], 'Ana')
        event = UserAdministrationEvent.objects.get(action=UserAdministrationAction.PROFILE_UPDATED)
        self.assertEqual(event.changed_fields, ['first_name'])
        self.assertEqual(event.request_id, response['X-Request-ID'])

        for payload in ({}, {'email': 'new@example.com'}, {'last_name': 'X', 'role': 'ADMIN'}):
            self.assertEqual(
                self.client.patch(f'/api/v1/auth/users/{self.operator.id}/', payload, format='json').status_code,
                400,
            )
        self.assertEqual(
            self.client.patch(f'/api/v1/auth/users/{self.admin.id}/', {'first_name': 'Self'}, format='json').status_code,
            403,
        )
        superuser = User.objects.create_superuser('root', 'root@example.com', PASSWORD)
        self.assertEqual(self.client.get(f'/api/v1/auth/users/{superuser.id}/').status_code, 200)
        self.assertEqual(
            self.client.patch(f'/api/v1/auth/users/{superuser.id}/', {'first_name': 'X'}, format='json').status_code,
            403,
        )

    def test_role_changes_are_idempotent_audited_and_protected(self):
        url = f'/api/v1/auth/users/{self.operator.id}/role/'
        promoted = self.client.patch(url, {'role': 'ADMIN'}, format='json')
        self.assertEqual(promoted.status_code, 200)
        self.assertEqual(promoted.data['role'], UserRole.ADMIN)
        self.assertEqual(UserAdministrationEvent.objects.filter(action=UserAdministrationAction.ROLE_CHANGED).count(), 1)
        self.assertEqual(self.client.patch(url, {'role': 'ADMIN'}, format='json').status_code, 200)
        self.assertEqual(UserAdministrationEvent.objects.filter(action=UserAdministrationAction.ROLE_CHANGED).count(), 1)
        self.assertEqual(self.client.patch(url, {'role': 'OPERADOR'}, format='json').status_code, 200)
        self.assertEqual(
            self.client.patch(f'/api/v1/auth/users/{self.admin.id}/role/', {'role': 'OPERADOR'}, format='json').status_code,
            403,
        )
        superuser = User.objects.create_superuser('root', 'root@example.com', PASSWORD)
        self.assertEqual(
            self.client.patch(f'/api/v1/auth/users/{superuser.id}/role/', {'role': 'OPERADOR'}, format='json').status_code,
            403,
        )
        missing = User.objects.create_user('missing', 'missing@example.com', PASSWORD)
        missing.profile.delete()
        self.assertEqual(
            self.client.patch(f'/api/v1/auth/users/{missing.id}/role/', {'role': 'ADMIN'}, format='json').status_code,
            400,
        )

    def test_activation_deactivation_idempotency_audit_and_protections(self):
        deactivate = f'/api/v1/auth/users/{self.operator.id}/deactivate/'
        activate = f'/api/v1/auth/users/{self.operator.id}/activate/'
        response = self.client.post(deactivate)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['is_active'])
        self.assertEqual(self.client.post(deactivate).status_code, 200)
        self.assertEqual(UserAdministrationEvent.objects.filter(action=UserAdministrationAction.USER_DEACTIVATED).count(), 1)
        self.assertEqual(self.client.post(activate).status_code, 200)
        self.assertEqual(self.client.post(activate).status_code, 200)
        self.assertEqual(UserAdministrationEvent.objects.filter(action=UserAdministrationAction.USER_ACTIVATED).count(), 1)
        self.assertEqual(self.client.post(f'/api/v1/auth/users/{self.admin.id}/deactivate/').status_code, 403)
        superuser = User.objects.create_superuser('root', 'root@example.com', PASSWORD)
        self.assertEqual(self.client.post(f'/api/v1/auth/users/{superuser.id}/deactivate/').status_code, 403)

    def test_last_active_admin_is_preserved_and_superuser_counts(self):
        other_admin = User.objects.create_user('otheradmin', 'otheradmin@example.com', PASSWORD)
        other_admin.profile.role = UserRole.ADMIN
        other_admin.profile.save(update_fields=['role'])
        self.assertEqual(self.client.post(f'/api/v1/auth/users/{other_admin.id}/deactivate/').status_code, 200)
        other_admin.is_active = True
        other_admin.save(update_fields=['is_active'])
        self.assertEqual(self.client.patch(
            f'/api/v1/auth/users/{other_admin.id}/role/', {'role': 'OPERADOR'}, format='json',
        ).status_code, 200)

        # An active superuser counts as an administrator of security.
        root = User.objects.create_superuser('root', 'root@example.com', PASSWORD)
        self.client.force_authenticate(root)
        self.assertEqual(self.client.post(f'/api/v1/auth/users/{self.admin.id}/deactivate/').status_code, 200)

    def test_openapi_documents_all_administration_paths(self):
        self.client.force_authenticate()
        schema = self.client.get('/api/schema/?format=json').json()
        for path in (
            '/api/v1/auth/users/', '/api/v1/auth/users/{user_id}/',
            '/api/v1/auth/users/{user_id}/role/',
            '/api/v1/auth/users/{user_id}/activate/',
            '/api/v1/auth/users/{user_id}/deactivate/',
        ):
            self.assertIn(path, schema['paths'])

    def test_audit_failure_rolls_back_the_user_change(self):
        with patch('authentication.services._event', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                update_managed_user(
                    actor=self.admin,
                    target_id=self.operator.id,
                    values={'first_name': 'Não deve persistir'},
                    request_id='00000000-0000-0000-0000-000000000003',
                )
        self.operator.refresh_from_db()
        self.assertEqual(self.operator.first_name, '')
        self.assertFalse(UserAdministrationEvent.objects.exists())

    def test_audit_failure_rolls_back_role_and_state_changes(self):
        with patch('authentication.services._event', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                change_user_role(
                    actor=self.admin,
                    target_id=self.operator.id,
                    new_role=UserRole.ADMIN,
                    request_id='00000000-0000-0000-0000-000000000004',
                )
        self.operator.profile.refresh_from_db()
        self.assertEqual(self.operator.profile.role, UserRole.OPERADOR)

        with patch('authentication.services._event', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                set_user_active(
                    actor=self.admin,
                    target_id=self.operator.id,
                    is_active=False,
                    request_id='00000000-0000-0000-0000-000000000005',
                )
        self.operator.refresh_from_db()
        self.assertTrue(self.operator.is_active)
        self.assertFalse(UserAdministrationEvent.objects.exists())


class UserAdministrationAdminTestCase(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser('root', 'root@example.com', PASSWORD)
        self.target = User.objects.create_user('operator', 'operator@example.com', PASSWORD)
        self.assertTrue(self.client.login(username='root', password=PASSWORD))

    def test_user_admin_list_and_detail_remain_visible_with_read_only_profile(self):
        self.assertEqual(self.client.get(reverse('admin:auth_user_changelist')).status_code, 200)
        detail = self.client.get(reverse('admin:auth_user_change', args=(self.target.id,)))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, self.target.username)
        self.assertContains(detail, self.target.profile.get_role_display())
        self.assertNotContains(detail, 'name="_save"')
        self.assertNotContains(detail, 'name="_addanother"')

    def test_user_admin_blocks_creation_and_preserves_createsuperuser_support(self):
        initial_count = User.objects.count()
        response = self.client.post(reverse('admin:auth_user_add'), {
            'username': 'created-in-admin',
            'password1': PASSWORD,
            'password2': PASSWORD,
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(User.objects.count(), initial_count)
        self.assertTrue(callable(User._default_manager.create_superuser))

    def test_user_admin_blocks_direct_user_and_profile_mutations(self):
        original_role = self.target.profile.role
        response = self.client.post(reverse('admin:auth_user_change', args=(self.target.id,)), {
            'username': 'changed',
            'email': 'changed@example.com',
            'is_active': '',
            'is_staff': 'on',
            'is_superuser': 'on',
            'profile-0-id': self.target.profile.id,
            'profile-0-user': self.target.id,
            'profile-0-role': UserRole.ADMIN,
            'profile-TOTAL_FORMS': '1',
            'profile-INITIAL_FORMS': '1',
            'profile-MIN_NUM_FORMS': '0',
            'profile-MAX_NUM_FORMS': '1',
        })
        self.assertEqual(response.status_code, 403)
        self.target.refresh_from_db()
        self.target.profile.refresh_from_db()
        self.assertEqual(self.target.username, 'operator')
        self.assertEqual(self.target.email, 'operator@example.com')
        self.assertTrue(self.target.is_active)
        self.assertFalse(self.target.is_staff)
        self.assertFalse(self.target.is_superuser)
        self.assertEqual(self.target.profile.role, original_role)

    def test_user_admin_blocks_individual_and_bulk_deletion(self):
        delete_url = reverse('admin:auth_user_delete', args=(self.target.id,))
        self.assertEqual(self.client.post(delete_url, {'post': 'yes'}).status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.target.pk).exists())

        response = self.client.post(reverse('admin:auth_user_changelist'), {
            'action': 'delete_selected',
            ACTION_CHECKBOX_NAME: [self.target.pk],
            'index': '0',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.target.pk).exists())
        self.assertEqual(admin.site._registry[User].get_actions(response.wsgi_request), {})

    def test_other_admin_modules_and_operational_rest_api_remain_available(self):
        self.assertEqual(self.client.get(reverse('admin:fleet_fleetunit_changelist')).status_code, 200)
        api_client = APIClient()
        api_client.force_authenticate(self.root)
        response = api_client.get('/api/v1/auth/users/')
        self.assertEqual(response.status_code, 200)


class LastAdministratorConcurrencyTestCase(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.first = User.objects.create_user('first', 'first@example.com', PASSWORD)
        self.second = User.objects.create_user('second', 'second@example.com', PASSWORD)
        UserProfile.objects.filter(user__in=(self.first, self.second)).update(role=UserRole.ADMIN)

    @staticmethod
    def _demote(actor_id, target_id, request_id):
        close_old_connections()
        try:
            actor = User.objects.get(pk=actor_id)
            change_user_role(
                actor=actor,
                target_id=target_id,
                new_role=UserRole.OPERADOR,
                request_id=request_id,
            )
            return 'changed'
        except UserAdministrationConflictError:
            return 'conflict'
        except UserAdministrationForbiddenError:
            return 'forbidden'
        finally:
            close_old_connections()

    @staticmethod
    def _deactivate(actor_id, target_id, request_id):
        close_old_connections()
        try:
            actor = User.objects.get(pk=actor_id)
            set_user_active(
                actor=actor,
                target_id=target_id,
                is_active=False,
                request_id=request_id,
            )
            return 'changed'
        except UserAdministrationConflictError:
            return 'conflict'
        except UserAdministrationForbiddenError:
            return 'forbidden'
        finally:
            close_old_connections()

    @staticmethod
    def _activate(actor_id, target_id, request_id):
        close_old_connections()
        try:
            actor = User.objects.get(pk=actor_id)
            set_user_active(
                actor=actor,
                target_id=target_id,
                is_active=True,
                request_id=request_id,
            )
            return 'active'
        finally:
            close_old_connections()

    def test_concurrent_demotion_never_removes_both_active_administrators(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(
                lambda args: self._demote(*args),
                (
                    (self.first.id, self.second.id, '00000000-0000-0000-0000-000000000001'),
                    (self.second.id, self.first.id, '00000000-0000-0000-0000-000000000002'),
                ),
            ))
        self.assertCountEqual(outcomes, ['changed', 'conflict'])
        active_admins = User.objects.filter(is_active=True, profile__role=UserRole.ADMIN).count()
        self.assertEqual(active_admins, 1)
        self.assertEqual(UserAdministrationEvent.objects.filter(action=UserAdministrationAction.ROLE_CHANGED).count(), 1)

    def test_concurrent_deactivation_and_demotion_preserve_an_active_administrator(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(
                lambda operation: operation(),
                (
                    lambda: self._demote(
                        self.first.id, self.second.id, '00000000-0000-0000-0000-000000000006',
                    ),
                    lambda: self._deactivate(
                        self.second.id, self.first.id, '00000000-0000-0000-0000-000000000007',
                    ),
                ),
            ))
        self.assertCountEqual(outcomes, ['changed', 'conflict'])
        self.assertEqual(
            User.objects.filter(is_active=True, profile__role=UserRole.ADMIN).count(),
            1,
        )
        self.assertEqual(UserAdministrationEvent.objects.count(), 1)

    def test_concurrent_activation_of_inactive_admin_is_idempotent_and_audited_once(self):
        root = User.objects.create_superuser('root', 'root@example.com', PASSWORD)
        self.second.is_active = False
        self.second.save(update_fields=['is_active'])
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(
                lambda request_id: self._activate(root.id, self.second.id, request_id),
                (
                    '00000000-0000-0000-0000-000000000008',
                    '00000000-0000-0000-0000-000000000009',
                ),
            ))
        self.assertEqual(outcomes, ['active', 'active'])
        self.second.refresh_from_db()
        self.assertTrue(self.second.is_active)
        self.assertEqual(
            UserAdministrationEvent.objects.filter(action=UserAdministrationAction.USER_ACTIVATED).count(),
            1,
        )
