from dispatch.api_views import DispatchEmergencyAPIView


class LegacyDispatchEmergencyAPIView(DispatchEmergencyAPIView):
    """Temporary compatibility alias; excluded from the official OpenAPI schema."""

    schema = None
