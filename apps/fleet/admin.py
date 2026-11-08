from django.contrib.gis import admin
from .models.vehicle import FleetUnit

@admin.register(FleetUnit)
class FleetUnitAdmin(admin.GISModelAdmin):
    list_display = ('name', 'status')  
    list_filter = ('status',)          
    search_fields = ('name',)
    readonly_fields = ('status', 'created_at', 'updated_at')

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions
