from django.contrib.gis import admin
from .models.vehicle import FleetUnit

@admin.register(FleetUnit)
class FleetUnitAdmin(admin.GISModelAdmin):
    list_display = ('name', 'status')  
    list_filter = ('status',)          
    search_fields = ('name',)