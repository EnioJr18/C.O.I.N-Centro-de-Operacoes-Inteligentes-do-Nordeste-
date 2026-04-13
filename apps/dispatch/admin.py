from django.contrib.gis import admin
from .models.mission import Mission

@admin.register(Mission)
class MissionAdmin(admin.GISModelAdmin):
    list_display = ('id', 'status', 'assigned_unit', 'created_at')
    list_filter = ('status',)
    search_fields = ('description',)