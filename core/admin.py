from django.contrib import admin
from django import forms
from django.utils.html import format_html
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget
from import_export.formats.base_formats import XLSX
from .models import *

class KecamatanResource(resources.ModelResource):
    kab_kota = fields.Field(attribute='kab_kota', column_name='kab_kota', widget=ForeignKeyWidget(KabupatenKota, 'nama_kokab'))
    class Meta:
        model = Kecamatan
        import_id_fields = ('kode_kecamatan',)
        fields = ('kode_kecamatan', 'nama_kecamatan', 'kab_kota')

class TpsPemiluInline(admin.StackedInline):
    model = TpsDptPemilu
    extra = 0

class TpsPilkadaInline(admin.StackedInline):
    model = TpsDptPilkada
    extra = 0

class ClusteringInline(admin.StackedInline):
    model = HasilClustering
    extra = 0

@admin.register(KabupatenKota)
class KabupatenKotaAdmin(admin.ModelAdmin):
    list_display = ('nama_kokab','kode_kokab')
    search_fields = ('nama_kokab',)

    def has_delete_permission(self, request, obj=None):
        return False
    def has_add_permission(self, request):
        return False

@admin.register(Kecamatan)
class KecamatanAdmin(ImportExportModelAdmin):
    resource_class = KecamatanResource
    formats = [XLSX]
    list_display = ('info_kecamatan','hasil_clustering')
    ordering = ('kab_kota', 'nama_kecamatan')
    list_filter = ('kab_kota', 'clustering__label_cluster')
    search_fields = ('nama_kecamatan', 'kode_kecamatan')
    inlines = [TpsPemiluInline, TpsPilkadaInline, ClusteringInline]
    list_per_page = 45
    list_max_show_all = 700

    def info_kecamatan(self, obj):
        return format_html('{} <br> <p style="color:gray; font-size:12px;">{} | {}</p>', obj.nama_kecamatan,obj.kode_kecamatan, obj.kab_kota.nama_kokab)
    info_kecamatan.short_description = 'Info Kecamatan'

    def hasil_clustering(self, obj):
        if hasattr(obj, 'clustering'):  
            c = obj.clustering.label_cluster
            colors = ['#ef4444','#f97316','#eab308','#22c55e','#3b82f6','#8b5cf6','#ec4899','#14b8a6','#f43f5e']
            bg_color = colors[c % len(colors)]
            return format_html(
                '<span style="display:inline-flex; align-items:center; justify-content:center; '
                'width:30px; height:30px; border-radius:50%; background-color:{}; color:white; '
                'font-weight:bold; font-size:14px; box-shadow:0 2px 4px rgba(0,0,0,0.2);">{}</span>',
                bg_color, c
            )
        return "-"
    hasil_clustering.short_description = 'Hasil Clustering'
    hasil_clustering.admin_order_field = 'clustering__label_cluster'

    def has_delete_permission(self, request, obj=None):
        return False
    def has_add_permission(self, request):
        return False

@admin.register(Partai)
class PartaiAdmin(admin.ModelAdmin):
    list_display = ('identitas_partai', 'warna_preview')
    ordering = ('no_urut_partai',)

    def identitas_partai(self, obj):
        logo_url = obj.logo_partai.url if obj.logo_partai else ""
        logo_html = format_html('<img src="{}" style="width:40px; height:40px; object-fit:contain; vertical-align:middle; margin-right:10px;"/>', logo_url) if logo_url else ""
        return format_html('{} <b>#{}</b> {}', logo_html, obj.no_urut_partai, obj.nama_partai)
    identitas_partai.short_description = 'Informasi Partai'

    def warna_preview(self, obj):
        return format_html('<div style="width:20px; height:20px; background-color:{}; border-radius:50%;"></div>', obj.warna_partai)
    warna_preview.short_description = 'Warna'

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'warna_partai':
            kwargs['widget'] = forms.TextInput(attrs={'type': 'color'})
        return super().formfield_for_dbfield(db_field, **kwargs)
    
    def has_delete_permission(self, request, obj=None):
        return False
    def has_add_permission(self, request):
        return False
