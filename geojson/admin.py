from django.contrib import admin
from django.utils.html import mark_safe
from .models import KabupatenGeoJSON, KecamatanGeoJSON
import json

class GeoJSONMapPreviewMixin:
    readonly_fields = ('peta_preview',)
    
    @admin.display(description="Preview Peta Wilayah")
    def peta_preview(self, obj):
        if not obj or not obj.geojson_data:
            return mark_safe("<i>Data koordinat peta belum diunggah.</i>")
            
        data = obj.geojson_data
        if isinstance(data, str):
            data_json = data
        else:
            data_json = json.dumps(data)
            
        map_id = f"leaflet_map_{obj.pk}"
        html = f"""
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        
        <div id="{map_id}" style="width: 100%; height: 450px; border-radius: 8px; border: 1px solid #ccc; z-index: 1;"></div>
        
        <script>
            document.addEventListener("DOMContentLoaded", function() {{
                var map = L.map('{map_id}', {{ zoomControl: false }}).setView([-6.9175, 107.6191], 8);
                L.control.zoom({{ position: 'topright' }}).addTo(map);
                
                L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    maxZoom: 19
                }}).addTo(map);
                
                var rawData = {data_json};
                
                var layer = L.geoJSON(rawData, {{
                    style: function(feature) {{
                        return {{ color: "#555555", weight: 0.8, opacity: 1.0, fillOpacity: 0.35, fillColor: "#808080" }};
                    }}
                }}).addTo(map);
                
                try {{
                    map.fitBounds(layer.getBounds(), {{ padding: [20, 20] }});
                }} catch(e) {{}}
            }});
        </script>
        """
        return mark_safe(html)

from django.db import models

class HasGeoJSONFilter(admin.SimpleListFilter):
    title = 'Status GeoJSON'
    parameter_name = 'has_geojson'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Sudah Ada'),
            ('no', 'Belum Ada'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(geojson_data__isnull=True).exclude(geojson_data__exact='')
        if self.value() == 'no':
            return queryset.filter(models.Q(geojson_data__isnull=True) | models.Q(geojson_data__exact=''))
        return queryset

@admin.register(KabupatenGeoJSON)
class KabupatenGeoJSONAdmin(GeoJSONMapPreviewMixin, admin.ModelAdmin):
    list_display = ('kabupaten', 'has_geojson_data')
    search_fields = ('kabupaten__nama_kokab',)
    list_filter = (HasGeoJSONFilter,)
    autocomplete_fields = ('kabupaten',)
    fields = ('kabupaten', 'peta_preview', 'geojson_data')
    ordering = ('kabupaten__nama_kokab',)
    list_per_page = 27

    @admin.display(description="GeoJSON Dimasukkan", boolean=True)
    def has_geojson_data(self, obj):
        return bool(obj.geojson_data)
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_add_permission(self, request):
        return False

@admin.register(KecamatanGeoJSON)
class KecamatanGeoJSONAdmin(GeoJSONMapPreviewMixin, admin.ModelAdmin):
    list_display = ('kecamatan', 'get_kabupaten', 'has_geojson_data')
    search_fields = ('kecamatan__nama_kecamatan', 'kecamatan__kab_kota__nama_kokab')
    list_filter = ('kecamatan__kab_kota', HasGeoJSONFilter)
    autocomplete_fields = ('kecamatan',)
    fields = ('kecamatan', 'peta_preview', 'geojson_data')
    ordering = ('kecamatan__kab_kota__nama_kokab', 'kecamatan__nama_kecamatan')
    list_per_page = 45
    list_max_show_all = 1000

    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_add_permission(self, request):
        return False

    @admin.display(description="Kabupaten/Kota", ordering="kecamatan__kab_kota__nama_kokab")
    def get_kabupaten(self, obj):
        return obj.kecamatan.kab_kota.nama_kokab if obj.kecamatan else "-"

    @admin.display(description="GeoJSON Dimasukkan", boolean=True)
    def has_geojson_data(self, obj):
        return bool(obj.geojson_data)
