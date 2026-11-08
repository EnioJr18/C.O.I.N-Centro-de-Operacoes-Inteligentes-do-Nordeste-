from django.contrib.gis import admin
from .models.history import MissionHistory
from .models.mission import Mission

@admin.register(Mission)
class MissionAdmin(admin.GISModelAdmin):
    list_display = ('id', 'status', 'assigned_unit', 'created_at')
    list_filter = ('status',)
    search_fields = ('description',)
    readonly_fields = ('status', 'assigned_unit', 'created_at', 'updated_at')

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions


@admin.register(MissionHistory)
class MissionHistoryAdmin(admin.ModelAdmin):
    list_display = ('mission', 'status', 'actor', 'timestamp')
    list_filter = ('status',)
    search_fields = ('=mission__id', 'actor__username', 'notes')
    readonly_fields = ('mission', 'status', 'actor', 'notes', 'timestamp')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        return {}
