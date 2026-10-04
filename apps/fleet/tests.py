import json
from unittest.mock import patch

from django.contrib.gis.geos import Point
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from dispatch.services import UnitUnavailableError, create_mission, assign_unit_to_mission
from fleet.models.vehicle import FleetUnit, UnitType
from fleet.selectors import get_nearest_available_units


class FleetUnitTestCase(TestCase):
    def create_unit(self, **overrides):
        values = {
            "name": "Alfa 01",
            "license_plate": "ABC-1234",
            "unit_type": UnitType.USB,
            "current_location": Point(-35.0, -9.0, srid=4326),
            "capabilities": {"oxygen": True},
        }
        values.update(overrides)
        return FleetUnit.objects.create(**values)

    def test_creation_uses_expected_defaults_and_helpers(self):
        unit = self.create_unit()

        self.assertEqual(unit.status, FleetUnit.UnitStatus.AVAILABLE)
        self.assertEqual(unit.current_location.srid, 4326)
        self.assertTrue(unit.has_capability("oxygen"))
        self.assertFalse(unit.has_capability("uti"))
        self.assertTrue(unit.is_available())

    def test_license_plate_is_unique(self):
        self.create_unit()

        with self.assertRaises(IntegrityError):
            self.create_unit(name="Alfa 02")


class NearestAvailableUnitsTestCase(TestCase):
    def create_unit(self, suffix, point, **overrides):
        values = {
            "name": f"Unidade {suffix}",
            "license_plate": f"ABC-{suffix:04d}",
            "unit_type": UnitType.USB,
            "current_location": point,
            "capabilities": {"oxygen": True},
        }
        values.update(overrides)
        return FleetUnit.objects.create(**values)

    def test_filters_and_orders_available_units_by_distance(self):
        near = self.create_unit(1, Point(-35.00, -9.00, srid=4326))
        far = self.create_unit(2, Point(-35.10, -9.10, srid=4326))
        self.create_unit(
            3,
            Point(-35.01, -9.01, srid=4326),
            status=FleetUnit.UnitStatus.BUSY,
        )
        self.create_unit(4, None)

        units = list(get_nearest_available_units(-9.0, -35.0, limit=2))

        self.assertEqual([unit.id for unit in units], [near.id, far.id])
        self.assertTrue(all(hasattr(unit, "distance") for unit in units))

    def test_filters_by_type_and_capability_and_returns_empty_when_needed(self):
        usa = self.create_unit(
            1,
            Point(-35.0, -9.0, srid=4326),
            unit_type=UnitType.USA,
            capabilities={"uti": True},
        )
        self.create_unit(2, Point(-35.01, -9.01, srid=4326))

        filtered = list(
            get_nearest_available_units(
                -9.0,
                -35.0,
                required_type=UnitType.USA,
                requirements={"uti": True},
            )
        )

        self.assertEqual([unit.id for unit in filtered], [usa.id])
        self.assertEqual(
            list(get_nearest_available_units(-9.0, -35.0, requirements={"ventilator": True})),
            [],
        )


class DispatchEmergencyViewTestCase(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user('operator', 'operator@example.com', 'StrongPassword123')
        self.client = APIClient()
        self.client.force_authenticate(self.operator)
    def create_unit(self, **overrides):
        values = {
            "name": "Alfa 01",
            "license_plate": "ABC-1234",
            "unit_type": UnitType.USB,
            "current_location": Point(-35.0, -9.0, srid=4326),
            "capabilities": {"oxygen": True},
        }
        values.update(overrides)
        return FleetUnit.objects.create(**values)

    def post(self, payload):
        return self.client.post(
            reverse("fleet:dispatch_emergency"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def valid_payload(self, **overrides):
        payload = {
            "description": "Ocorrência clínica",
            "location": {"latitude": -9.0, "longitude": -35.0},
        }
        payload.update(overrides)
        return payload

    def test_dispatches_valid_request(self):
        unit = self.create_unit()

        response = self.post(self.valid_payload())

        self.assertEqual(response.status_code, 201)
        unit.refresh_from_db()
        self.assertEqual(unit.status, FleetUnit.UnitStatus.BUSY)

    def test_requires_valid_authentication(self):
        self.create_unit()
        anonymous_client = APIClient()
        invalid_token_client = APIClient()
        invalid_token_client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token")

        self.assertEqual(
            anonymous_client.post(
                reverse("fleet:dispatch_emergency"),
                data=json.dumps(self.valid_payload()),
                content_type="application/json",
            ).status_code,
            401,
        )
        self.assertEqual(
            invalid_token_client.post(
                reverse("fleet:dispatch_emergency"),
                data=json.dumps(self.valid_payload()),
                content_type="application/json",
            ).status_code,
            401,
        )

    def test_rejects_user_without_operational_role_and_allows_admin(self):
        self.create_unit()
        unauthorized = User.objects.create_user(
            'no-role', 'no-role@example.com', 'StrongPassword123'
        )
        unauthorized.profile.delete()
        unauthorized.refresh_from_db()
        self.client.force_authenticate(unauthorized)
        self.assertEqual(self.post(self.valid_payload()).status_code, 403)

        admin = User.objects.create_superuser('admin', 'admin@example.com', 'StrongPassword123')
        self.client.force_authenticate(admin)
        self.assertEqual(self.post(self.valid_payload()).status_code, 201)

    def test_rejects_invalid_json_and_payloads(self):
        invalid_json = self.client.post(
            reverse("fleet:dispatch_emergency"), data="{", content_type="application/json"
        )
        self.assertEqual(invalid_json.status_code, 400)

        for payload in (
            {"latitude": -9.0, "longitude": -35.0},
            self.valid_payload(location={"latitude": 91, "longitude": -35.0}),
            self.valid_payload(location={"latitude": -9.0, "longitude": "-35"}),
            self.valid_payload(required_type="INVALID"),
            self.valid_payload(requirements=["oxygen"]),
        ):
            self.assertEqual(self.post(payload).status_code, 400)

    def test_returns_not_found_when_no_unit_is_eligible(self):
        response = self.post(self.valid_payload())

        self.assertEqual(response.status_code, 404)

    def test_does_not_expose_internal_errors(self):
        self.create_unit()

        with (
            patch(
                "dispatch.api_views.dispatch_emergency",
                side_effect=RuntimeError("detalhe interno sensível"),
            ),
            patch("dispatch.api_exceptions.logger.exception"),
        ):
            response = self.post(self.valid_payload())

        self.assertEqual(response.status_code, 500)
        self.assertNotIn("detalhe interno", response.json()["detail"])

    def test_busy_unit_cannot_be_assigned_to_a_pending_mission(self):
        unit = self.create_unit(status=FleetUnit.UnitStatus.BUSY)
        mission = create_mission("Ocorrência", -9.0, -35.0)

        with self.assertRaises(UnitUnavailableError):
            assign_unit_to_mission(mission, unit.id)
