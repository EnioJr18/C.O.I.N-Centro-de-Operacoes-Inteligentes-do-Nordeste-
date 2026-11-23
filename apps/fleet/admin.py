from django.contrib.gis import admin
from .models.history import FleetUnitHistory
from .models.vehicle import FleetUnit

@admin.register(FleetUnit)
class FleetUnitAdmin(admin.GISModelAdmin):
    list_display = ('name', 'license_plate', 'unit_type', 'status')
    list_filter = ('status', 'unit_type')
    search_fields = ('name', 'license_plate')
    readonly_fields = (
        'name', 'license_plate', 'unit_type', 'current_location', 'status',
        'capabilities', 'created_at', 'updated_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions


@admin.register(FleetUnitHistory)
class FleetUnitHistoryAdmin(admin.ModelAdmin):
    list_display = ('unit', 'action', 'actor', 'created_at')
    list_filter = ('action',)
    search_fields = ('unit__name', 'unit__license_plate', 'actor__username', 'request_id')
    readonly_fields = (
        'unit', 'actor', 'action', 'previous_status', 'new_status',
        'changed_fields', 'request_id', 'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        return {}
