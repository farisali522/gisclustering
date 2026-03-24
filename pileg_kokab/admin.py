from django.contrib import admin
from django import forms
from django.db.models import Sum, OuterRef, Subquery, IntegerField
from django.db.models.functions import Coalesce
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.contrib.humanize.templatetags.humanize import intcomma
from import_export.admin import ImportExportModelAdmin
from import_export.formats.base_formats import XLSX
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget
from core.models import Partai, Kecamatan, KabupatenKota
from .models import DapilKokab, CalegKokab, RekapSuaraPilegKokab, DetailSuaraPilegKokab, RekapSuaraPilegKokabKab, RekapSuaraPilegKokabDapil

@admin.register(RekapSuaraPilegKokabKab)
class RekapSuaraPilegKokabKabAdmin(admin.ModelAdmin):
    list_display = ('wilayah_kab', 'info_tps_dpt_kab')
    search_fields = ('nama_kokab',)
    ordering = ('nama_kokab',)

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False
    def has_change_permission(self, request, obj=None): return False

    def get_list_display(self, request):
        cols = ['wilayah_kab', 'info_tps_dpt_kab']
        
        partais = list(Partai.objects.all().order_by('no_urut_partai'))
        for p in partais:
            fn = f'col_kab_p_{p.id}'
            p_id = p.id
            p_logo = p.logo_partai.url if p.logo_partai else None
            p_name = p.nama_partai
            p_no   = p.no_urut_partai
            p_color = getattr(p, 'warna_partai', '#ffc107')

            def _gv_kab(obj, pid=p_id, c=p_color):
                if not hasattr(obj, '_party_votes'):
                    from django.db.models import Sum
                    qs = DetailSuaraPilegKokab.objects.filter(kecamatan__kab_kota=obj).values('partai_id').annotate(total=Sum('jumlah_suara'))
                    obj._party_votes = {item['partai_id']: item['total'] for item in qs}
                    obj._max_vote = max(obj._party_votes.values()) if obj._party_votes else -1

                ds = obj._party_votes.get(pid, 0)
                sah = getattr(obj, 'agg_sah', 0)
                fmt_v = "{:,}".format(ds).replace(',', '.')
                
                is_winner = ds > 0 and ds == obj._max_vote
                box_style = f"background-color: {c}20; border: 2px solid {c}; border-radius: 6px; padding: 4px;" if is_winner else "padding: 4px;"
                
                if sah > 0:
                    pct = f"({(ds/sah*100):.1f}%)"
                    return format_html('<div style="text-align:center; min-width:50px; {}"><b>{}</b><br><small style="color:#666; font-size:11.5px;">{}</small></div>', box_style, fmt_v, pct)
                return format_html('<div style="text-align:center; {}">{}</div>', box_style, fmt_v)

            if p_logo:
                _gv_kab.short_description = mark_safe(f'<div style="text-align:center;"><img src="{p_logo}" title="{p_name}" style="height:20px; object-fit:contain;"><br><span style="font-size:11px;">#{p_no}</span></div>')
            else:
                _gv_kab.short_description = f"#{p_no}"
            setattr(self, fn, _gv_kab)
            cols.append(fn)

        cols += ['total_suara_sah_kab', 'total_suara_tidak_sah_kab', 'total_suara_semua_kab']
        return cols

    def wilayah_kab(self, obj):
        from django.urls import reverse
        url = reverse('admin:pileg_kokab_rekapsuarapilegkokabdapil_changelist')
        full_url = f"{url}?kab_kota__id__exact={obj.id}"
        return format_html('<a href="{}" title="Buka Detail Dapil di Kokab Ini" style="color:#007bff;"><b>{}</b></a>', full_url, obj.nama_kokab)
    wilayah_kab.short_description = 'Kabupaten / Kota'
    wilayah_kab.admin_order_field = 'nama_kokab'

    def info_tps_dpt_kab(self, obj):
        return format_html('<b>TPS:</b> {}<br><b>DPT:</b> {}', intcomma(getattr(obj, 'agg_tps', 0)), intcomma(getattr(obj, 'agg_dpt', 0)))
    info_tps_dpt_kab.short_description = 'TPS / DPT'

    def total_suara_sah_kab(self, obj):
        pct_str = f"{obj.pct_sah:.2f}"
        return format_html('<span style="color:#28a745;"><b>{}</b></span><br><small style="color:#666;">({}%)</small>', intcomma(getattr(obj, 'agg_sah', 0)), pct_str)
    total_suara_sah_kab.short_description = 'Suara Sah'

    def total_suara_tidak_sah_kab(self, obj):
        pct_str = f"{obj.pct_tidak_sah:.2f}"
        return format_html('<span style="color:#dc3545;"><b>{}</b></span><br><small style="color:#666;">({}%)</small>', intcomma(getattr(obj, 'agg_tidak_sah', 0)), pct_str)
    total_suara_tidak_sah_kab.short_description = 'Tidak Sah'

    def total_suara_semua_kab(self, obj):
        pct_str = f"{obj.pct_semua:.2f}"
        return format_html('<span style="color:#007bff;"><b>{}</b></span><br><small style="color:#666;">({}%)</small>', intcomma(obj.t_total), pct_str)
    total_suara_semua_kab.short_description = 'Total Suara'


@admin.register(RekapSuaraPilegKokabDapil)
class RekapSuaraPilegKokabDapilAdmin(admin.ModelAdmin):
    list_display = ('wilayah_dapil', 'info_tps_dpt_dapil')
    list_filter = ('kab_kota',)
    search_fields = ('nama_dapil', 'kab_kota__nama_kokab')
    ordering = ('kab_kota__nama_kokab', 'nama_dapil')

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False
    def has_change_permission(self, request, obj=None): return False

    def get_list_display(self, request):
        cols = ['wilayah_dapil', 'info_tps_dpt_dapil']
        
        partais = list(Partai.objects.all().order_by('no_urut_partai'))
        for p in partais:
            fn = f'col_dapil_p_{p.id}'
            p_id = p.id
            p_logo = p.logo_partai.url if p.logo_partai else None
            p_name = p.nama_partai
            p_no   = p.no_urut_partai
            p_color = getattr(p, 'warna_partai', '#ffc107')

            def _gv_dapil(obj, pid=p_id, c=p_color):
                if not hasattr(obj, '_party_votes'):
                    from django.db.models import Sum
                    qs = DetailSuaraPilegKokab.objects.filter(kecamatan__dapil_kokab=obj).values('partai_id').annotate(total=Sum('jumlah_suara'))
                    obj._party_votes = {item['partai_id']: item['total'] for item in qs}
                    obj._max_vote = max(obj._party_votes.values()) if obj._party_votes else -1

                ds = obj._party_votes.get(pid, 0)
                sah = getattr(obj, 'agg_sah', 0)
                fmt_v = "{:,}".format(ds).replace(',', '.')
                
                is_winner = ds > 0 and ds == obj._max_vote
                box_style = f"background-color: {c}20; border: 2px solid {c}; border-radius: 6px; padding: 4px;" if is_winner else "padding: 4px;"
                
                if sah > 0:
                    pct = f"({(ds/sah*100):.1f}%)"
                    return format_html('<div style="text-align:center; min-width:50px; {}"><b>{}</b><br><small style="color:#666; font-size:11.5px;">{}</small></div>', box_style, fmt_v, pct)
                return format_html('<div style="text-align:center; {}">{}</div>', box_style, fmt_v)

            if p_logo:
                _gv_dapil.short_description = mark_safe(f'<div style="text-align:center;"><img src="{p_logo}" title="{p_name}" style="height:20px; object-fit:contain;"><br><span style="font-size:11px;">#{p_no}</span></div>')
            else:
                _gv_dapil.short_description = f"#{p_no}"
            setattr(self, fn, _gv_dapil)
            cols.append(fn)

        cols += ['total_suara_sah_dapil', 'total_suara_tidak_sah_dapil', 'total_suara_semua_dapil']
        return cols

    def wilayah_dapil(self, obj):
        from django.urls import reverse
        cakupan = ", ".join([k.nama_kecamatan for k in obj.wilayah_kecamatan.all()]) or "-"
        url = reverse('admin:pileg_kokab_rekapsuarapilegkokab_changelist')
        full_url = f"{url}?kecamatan__dapil_kokab__id__exact={obj.id}"
        return format_html('<div style="line-height:1.2;"><a href="{}" title="Buka Detail Kecamatan untuk Dapil Ini"><b>{}</b></a><br><span style="font-size:10.5px; color:#666;">{}</span></div>', full_url, f"{obj.nama_dapil} - {obj.kab_kota.nama_kokab}", cakupan)
    wilayah_dapil.short_description = 'Nama Dapil'
    wilayah_dapil.admin_order_field = 'nama_dapil'

    def info_tps_dpt_dapil(self, obj):
        return format_html('<b>TPS:</b> {}<br><b>DPT:</b> {}', intcomma(getattr(obj, 'agg_tps', 0)), intcomma(getattr(obj, 'agg_dpt', 0)))
    info_tps_dpt_dapil.short_description = 'TPS / DPT'

    def total_suara_sah_dapil(self, obj):
        pct_str = f"{obj.pct_sah:.2f}"
        return format_html('<span style="color:#28a745;"><b>{}</b></span><br><small style="color:#666;">({}%)</small>', intcomma(getattr(obj, 'agg_sah', 0)), pct_str)
    total_suara_sah_dapil.short_description = 'Suara Sah'

    def total_suara_tidak_sah_dapil(self, obj):
        pct_str = f"{obj.pct_tidak_sah:.2f}"
        return format_html('<span style="color:#dc3545;"><b>{}</b></span><br><small style="color:#666;">({}%)</small>', intcomma(getattr(obj, 'agg_tidak_sah', 0)), pct_str)
    total_suara_tidak_sah_dapil.short_description = 'Tidak Sah'

    def total_suara_semua_dapil(self, obj):
        pct_str = f"{obj.pct_semua:.2f}"
        return format_html('<span style="color:#007bff;"><b>{}</b></span><br><small style="color:#666;">({}%)</small>', intcomma(obj.t_total), pct_str)
    total_suara_semua_dapil.short_description = 'Total Suara'


class DapilKokabResource(resources.ModelResource):
    # Gunakan ForeignKeyWidget agar bisa merujuk nama_kokab langsung dari excel
    kab_kota = fields.Field(
        column_name='kab_kota',
        attribute='kab_kota',
        widget=ForeignKeyWidget(KabupatenKota, 'nama_kokab')
    )
    # Gunakan ManyToManyWidget untuk membaca gabungan kode_kecamatan dengan pemisah koma
    wilayah_kecamatan = fields.Field(
        column_name='kode_kecamatan',
        attribute='wilayah_kecamatan',
        widget=ManyToManyWidget(Kecamatan, field='kode_kecamatan', separator=',')
    )

    class Meta:
        model = DapilKokab
        import_id_fields = ('nama_dapil', 'kab_kota')  # Patokan update/create diganti
        fields = ('nama_dapil', 'kab_kota', 'jumlah_kursi', 'wilayah_kecamatan')
        export_order = ('nama_dapil', 'kab_kota', 'jumlah_kursi', 'wilayah_kecamatan')

@admin.register(DapilKokab)
class DapilKokabAdmin(ImportExportModelAdmin):
    resource_class = DapilKokabResource
    formats = [XLSX]
    list_display = ('nama_dapil', 'kab_kota', 'jumlah_kursi', 'wilayah_cakupan')
    search_fields = ('nama_dapil', 'kab_kota__nama_kokab')
    list_filter = ('kab_kota',)
    filter_horizontal = ('wilayah_kecamatan',)
    ordering = ('kab_kota__nama_kokab', 'nama_dapil')

    def wilayah_cakupan(self, obj):
        nama_kolom = [k.nama_kecamatan for k in obj.wilayah_kecamatan.all()]
        return ", ".join(nama_kolom) if nama_kolom else "-"
    wilayah_cakupan.short_description = "Cakupan Wilayah (Kecamatan)"

class CalegKokabResource(resources.ModelResource):
    dapil = fields.Field(column_name='dapil', attribute='dapil', widget=ForeignKeyWidget(DapilKokab, 'nama_dapil'))
    partai = fields.Field(column_name='partai', attribute='partai', widget=ForeignKeyWidget(Partai, 'nama_partai'))

    class Meta:
        model = CalegKokab
        import_id_fields = ('dapil', 'partai', 'no_urut')
        fields = ('no_urut', 'nama_caleg', 'dapil', 'partai', 'jenis_kelamin')
        export_order = ('no_urut', 'nama_caleg', 'dapil', 'partai', 'jenis_kelamin')

@admin.register(CalegKokab)
class CalegKokabAdmin(ImportExportModelAdmin):
    resource_class = CalegKokabResource
    formats = [XLSX]
    list_display = ('identitas_caleg', 'info_partai', 'dapil_nama')
    list_filter = ('dapil__kab_kota', 'dapil', 'partai', 'jenis_kelamin')
    search_fields = ('nama_caleg', 'partai__nama_partai', 'dapil__nama_dapil')
    list_display_links = ('identitas_caleg',)
    list_per_page = 20

    def identitas_caleg(self, obj):
        from django.utils.html import format_html
        jk = f" ({obj.jenis_kelamin})" if obj.jenis_kelamin else ""
        if obj.foto_caleg:
            img = f'<img src="{obj.foto_caleg.url}" style="width:30px; height:30px; min-width:30px; border-radius:50%; object-fit:cover; vertical-align:middle; margin-right:8px; box-shadow:0 1px 3px rgba(0,0,0,0.1);"/>'
            return format_html('{} <b>{}.</b> {} {}', format_html(img), obj.no_urut, obj.nama_caleg, jk)
        
        # Desain Avatar Inisial Elegan
        if obj.nama_caleg:
            kata = obj.nama_caleg.strip().split()
            if len(kata) >= 2:
                ikon = (kata[0][0] + kata[1][0]).upper()
            elif len(kata) == 1:
                ikon = kata[0][0:2].upper()
            else:
                ikon = "?"
        else:
            ikon = "?"

        if obj.jenis_kelamin == 'P':
            warna_bg = '#ff7675'
            warna_tx = '#ffffff'
        else:
            warna_bg = '#74b9ff'
            warna_tx = '#ffffff'
            
        placeholder = f'<div style="width:30px; height:30px; border-radius:50%; background:{warna_bg}; display:inline-block; vertical-align:middle; margin-right:8px; text-align:center; line-height:30px; color:{warna_tx}; font-size:12px; font-weight:bold; font-family:-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif;">{ikon}</div>'
        return format_html('{} <b>{}.</b> {} {}', format_html(placeholder), obj.no_urut, obj.nama_caleg, jk)
    identitas_caleg.short_description = "No Urut & Nama Caleg"

    def info_partai(self, obj):
        from django.utils.html import format_html
        p = obj.partai
        if p.logo_partai:
            img = f'<img src="{p.logo_partai.url}" style="height:25px; object-fit:contain; vertical-align:middle; margin-right:6px;"/>'
            return format_html('{} <b>{}</b>. {}', format_html(img), p.no_urut_partai, p.nama_partai)
        return format_html('<b>{}</b>. {}', p.no_urut_partai, p.nama_partai)
    info_partai.short_description = "Partai"
    
    def dapil_nama(self, obj): 
        return f"{obj.dapil.nama_dapil} - {obj.dapil.kab_kota.nama_kokab}"
    dapil_nama.short_description = "Dapil"

class RekapSuaraPilegKokabResource(resources.ModelResource):
    kecamatan = fields.Field(column_name='kode_kecamatan', attribute='kecamatan', widget=ForeignKeyWidget(Kecamatan, 'kode_kecamatan'))
    
    class Meta:
        model = RekapSuaraPilegKokab
        import_id_fields = ('kecamatan',)
        fields = ('kecamatan', 'total_suara_tidak_sah')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            partais = Partai.objects.all().order_by('no_urut_partai')
            for p in partais:
                fn_p = f"P_{p.nama_partai}"
                if fn_p not in self.fields:
                    self.fields[fn_p] = fields.Field(column_name=fn_p, attribute=fn_p)
                
                for i in range(1, 13):
                    fn_c = f"C_{p.nama_partai}_{i}"
                    if fn_c not in self.fields:
                        self.fields[fn_c] = fields.Field(column_name=fn_c, attribute=fn_c)
        except Exception:
            pass

    def get_export_order(self):
        return list(self.fields.keys())

    def export_field(self, field, obj, **kwargs):
        if field.attribute and field.attribute.startswith('P_'):
            nama_p = field.attribute[2:]
            ds = DetailSuaraPilegKokab.objects.filter(kecamatan=obj.kecamatan, partai__nama_partai__iexact=nama_p, caleg__isnull=True).first()
            return ds.jumlah_suara if ds else 0
            
        elif field.attribute and field.attribute.startswith('C_'):
            parts = field.attribute[2:].rsplit('_', 1)
            if len(parts) == 2 and parts[1].isdigit():
                nama_p, no_urut = parts[0], int(parts[1])
                from django.db.models import Sum
                total = DetailSuaraPilegKokab.objects.filter(kecamatan=obj.kecamatan, partai__nama_partai__iexact=nama_p, caleg__no_urut=no_urut).aggregate(t=Sum('jumlah_suara'))['t']
                return total or 0
                
        return super().export_field(field, obj, **kwargs)

    def after_import_row(self, row, row_result, **kwargs):
        kode = row.get('kode_kecamatan')
        if not kode: return
        kec = Kecamatan.objects.filter(kode_kecamatan=kode).first()
        if not kec: return

        try:
            dapil_kecs = list(kec.dapil_kokab.all())
        except Exception:
            dapil_kecs = []

        for key, val in row.items():
            if not key or val in [None, '', '-']: continue
            try:
                jumlah_suara = int(float(str(val).replace(',', '').replace('.', '') if str(val).count('.') > 1 else str(val)))
            except (ValueError, TypeError):
                continue
            if jumlah_suara < 0:
                continue

            k_str = str(key).strip().upper()
            
            if k_str.startswith('P_'):
                nama_p = k_str[2:]
                prt = Partai.objects.filter(nama_partai__iexact=nama_p).first()
                if prt:
                    DetailSuaraPilegKokab.objects.update_or_create(
                        kecamatan=kec, partai=prt, caleg=None,
                        defaults={'jumlah_suara': jumlah_suara}
                    )
                    
            elif k_str.startswith('C_'):
                parts = k_str[2:].rsplit('_', 1)
                if len(parts) == 2 and parts[1].isdigit():
                    nama_p, no_urut = parts[0], int(parts[1])
                    prt = Partai.objects.filter(nama_partai__iexact=nama_p).first()
                    if prt:
                        clg = CalegKokab.objects.filter(partai=prt, no_urut=no_urut, dapil__in=dapil_kecs).first()
                        if clg:
                            DetailSuaraPilegKokab.objects.update_or_create(
                                kecamatan=kec, partai=prt, caleg=clg,
                                defaults={'jumlah_suara': jumlah_suara}
                            )

class RekapSuaraPilegKokabForm(forms.ModelForm):
    class Meta:
        model = RekapSuaraPilegKokab
        fields = ['kecamatan', 'total_suara_tidak_sah']

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        obj = self.instance
        if not (obj and obj.pk):
            return

        from collections import OrderedDict, defaultdict
        fmt = lambda v: "{:,}".format(v).replace(',', '.')

        if self.request and self.request.GET:
            self.fields['_preserved_filters'] = forms.CharField(
                initial=self.request.GET.urlencode(),
                widget=forms.HiddenInput(), required=False
            )

        filter_p = self.request.GET.get('p') if self.request else None
        edit_ts = self.request.GET.get('ts') == '1' if self.request else False

        try:
            dapil_kecs = obj.kecamatan.dapil_kokab.all()
            nama_kab  = obj.kecamatan.kab_kota.nama_kokab
            nama_dapil = ", ".join([d.nama_dapil for d in dapil_kecs]) if dapil_kecs else "-"
        except Exception:
            dapil_kecs = []
            nama_kab  = "-"
            nama_dapil = "-"

        t_sah   = obj.total_suara_sah
        t_total = obj.total_semua_suara

        script_hitung = """
        <style>
        #rekapsuarapilegkokab_form, #content-main { font-family: 'Segoe UI', system-ui, -apple-system, BlinkMacSystemFont, 'Roboto', 'Helvetica Neue', sans-serif !important; }
        .form-row { padding: 16px 24px; border-bottom: 1px solid #eaeaea; background: #ffffff; }
        .form-row:nth-child(even) { background: #fafafa; }
        .form-row > div { display: flex; align-items: flex-start; margin: 0; padding: 0; }
        .form-row label { width: 220px !important; font-weight: 600 !important; font-size: 14px !important; padding-top: 12px; color: #333333; }
        .readonly { padding: 12px 16px; background: #f0f2f5; border-radius: 6px; width: 100%; max-width: 500px; display: inline-block; font-weight: 700; font-size: 15px; color: #1c1e21; }
        .vIntegerField, .input-paslon, #input-total-tidak-sah { width: 100% !important; max-width: 350px !important; padding: 12px 16px !important; border-radius: 6px !important; border: 1px solid #ced4da !important; font-size: 16px !important; font-weight: 600 !important; color: #212529 !important; box-shadow: 0 1px 2px rgba(0,0,0,0.02) !important; transition: all 0.2s ease-in-out !important; font-family: inherit !important; }
        .vIntegerField:focus, .input-paslon:focus, #input-total-tidak-sah:focus { border-color: #80bdff !important; outline: 0 !important; box-shadow: 0 0 0 0.2rem rgba(0,123,255,.25) !important; }
        .help { display: block; margin-top: 10px; font-size: 13px !important; color: #6c757d; }
        .help span { color: #495057; font-weight: 800; font-size: 14px; }
        </style>
        """

        self.fields['info_kb'] = forms.CharField(label=mark_safe(script_hitung + "Kabupaten/Kota"), initial=nama_kab, required=False, disabled=True, widget=forms.TextInput(attrs={'class': 'readonly'}))
        self.fields['info_dp'] = forms.CharField(label="Dapil Kab/Kota", initial=nama_dapil, required=False, disabled=True, widget=forms.TextInput(attrs={'class': 'readonly'}))
        self.fields['res_s'] = forms.CharField(label="Total Suara Sah", initial=fmt(t_sah), required=False, disabled=True, widget=forms.TextInput(attrs={'class': 'readonly', 'style': 'color:#28a745;'}))
        self.fields['res_t'] = forms.CharField(label="Total Suara Masuk", initial=fmt(t_total), required=False, disabled=True, widget=forms.TextInput(attrs={'class': 'readonly', 'style': 'color:#007bff;'}))
            
        if 'total_suara_tidak_sah' in self.fields:
            self.fields['total_suara_tidak_sah'].widget.attrs.update({'id': 'input-total-tidak-sah'})

        order = OrderedDict()

        if filter_p:
            from django.urls import reverse
            reset_url = reverse('admin:pileg_kokab_rekapsuarapilegkokab_change', args=[obj.pk])
            self.fields['reset_filter'] = forms.CharField(
                label=mark_safe(f'<div style="display:inline-flex; align-items:center;"><a href="{reset_url}" style="background:#ffc107; color:#212529; text-decoration:none; padding:6px 14px; border-radius:4px; font-weight:600; font-size:13px; box-shadow:0 1px 2px rgba(0,0,0,0.1);">Tampilkan Semua Partai</a></div>'),
                required=False, disabled=True, widget=forms.HiddenInput())
            order['reset_filter'] = self.fields.pop('reset_filter')

        for k in ['kecamatan', 'info_kb', 'info_dp', 'res_s', 'total_suara_tidak_sah', 'res_t']:
            if k not in self.fields: continue
            if filter_p and k in ['res_s', 'res_t', 'total_suara_tidak_sah']: continue
            order[k] = self.fields.pop(k)

        p_ids = {d.partai_id: d.jumlah_suara for d in DetailSuaraPilegKokab.objects.filter(kecamatan=obj.kecamatan, caleg__isnull=True)}
        c_ids = {d.caleg_id: d.jumlah_suara for d in DetailSuaraPilegKokab.objects.filter(kecamatan=obj.kecamatan, caleg__isnull=False)}

        caleg_by_partai = defaultdict(list)
        if dapil_kecs:
            for c in CalegKokab.objects.filter(dapil__in=dapil_kecs).select_related('partai', 'dapil').order_by('dapil__nama_dapil', 'no_urut'):
                caleg_by_partai[c.partai_id].append(c)

        if filter_p:
            pid_int = int(filter_p)
            p_obj = Partai.objects.filter(id=pid_int).first()
            if p_obj:
                p_suara = p_ids.get(pid_int, 0)
                c_suara_total = sum(c_ids.get(c.id, 0) for c in caleg_by_partai.get(pid_int, []))
                logo_url = p_obj.logo_partai.url if p_obj.logo_partai else ""
                logo_html = f'<img src="{logo_url}" style="height:24px; vertical-align:middle; margin-right:8px;">' if logo_url else ""
                self.fields['res_p_total'] = forms.CharField(label=mark_safe(f"{logo_html}<b>Total Suara {p_obj.nama_partai} (Partai + Caleg)</b>"), initial=fmt(p_suara + c_suara_total), required=False, disabled=True, widget=forms.TextInput(attrs={'class': 'readonly', 'style': 'color:#e83e8c; background:#fff0f5; border:2px solid #e83e8c;'}))
                order['res_p_total'] = self.fields.pop('res_p_total')

        if edit_ts:
            from django.urls import reverse
            reset_url = reverse('admin:pileg_kokab_rekapsuarapilegkokab_change', args=[obj.pk])
            self.fields['reset_filter_ts'] = forms.CharField(label=mark_safe(f'<div style="display:inline-flex; align-items:center;"><a href="{reset_url}" style="background:#f8f9fa; color:#495057; border:1px solid #ced4da; text-decoration:none; padding:6px 14px; border-radius:4px; font-weight:600; font-size:13px;">Tampilkan Seluruh Partai & Caleg &rarr;</a></div>'), required=False, disabled=True, widget=forms.HiddenInput())
            order['reset_filter_ts'] = self.fields.pop('reset_filter_ts')
            self.fields = order
            return

        partais = Partai.objects.all().order_by('no_urut_partai')
        for p in partais:
            if filter_p and str(p.id) != filter_p:
                continue

            val_p = p_ids.get(p.id, 0)
            pct_p = f"({(val_p/t_sah*100):.2f}%)" if t_sah > 0 else "(0.00%)"
            logo = format_html('<div style="display:inline-flex; align-items:center; background:#fff; padding:3px; border-radius:4px; border:1px solid #ddd; margin-right:8px; vertical-align:middle;"><img src="{}" style="height:22px;"></div>', p.logo_partai.url) if p.logo_partai else ""
            f_p = f'su_p_{p.id}'
            self.fields[f_p] = forms.IntegerField(label=mark_safe(f"{logo}<b>{p.no_urut_partai}. {p.nama_partai}</b>"), initial=val_p, required=False, min_value=0, help_text=format_html('<span style="color:#666;">{} dari Suara Sah</span>', pct_p), widget=forms.NumberInput(attrs={'class': 'input-paslon', 'style': 'font-weight:bold; border-color:#333;'}))
            order[f_p] = self.fields.pop(f_p)

            for c in caleg_by_partai.get(p.id, []):
                val_c = c_ids.get(c.id, 0)
                pct_c = f"({(val_c/t_sah*100):.2f}%)" if t_sah > 0 else "(0.00%)"
                f_c = f'su_c_{c.id}'
                
                label_caleg = f"\u2514 {c.no_urut}. {c.nama_caleg}"
                if len(dapil_kecs) > 1:
                    label_caleg += f" ({c.dapil.nama_dapil})"
                    
                self.fields[f_c] = forms.IntegerField(label=label_caleg, initial=val_c, required=False, min_value=0, help_text=format_html('<span style="color:#666;">{} dari Suara Sah</span>', pct_c), widget=forms.NumberInput(attrs={'class': 'input-paslon'}))
                order[f_c] = self.fields.pop(f_c)

        self.fields = order


@admin.register(RekapSuaraPilegKokab)
class RekapSuaraPilegKokabAdmin(ImportExportModelAdmin):
    form = RekapSuaraPilegKokabForm
    resource_class = RekapSuaraPilegKokabResource
    formats = [XLSX]
    search_fields = ('kecamatan__nama_kecamatan',)
    list_filter = ('kecamatan__kab_kota',)
    ordering = ('kecamatan__kab_kota', 'kecamatan__nama_kecamatan')
    list_per_page = 20

    def has_delete_permission(self, request, obj=None): return False

    def lookup_allowed(self, lookup, value):
        # Izinkan filter melalui URL untuk relasi kecamatan ke dapil_kokab
        if lookup.startswith('kecamatan__dapil_kokab'):
            return True
        return super().lookup_allowed(lookup, value)

    def get_wilayah_dyn(self, obj): return ""

    def get_list_display(self, request):
        base_query = request.GET.urlencode()

        def _gen_wilayah(obj, bq=base_query):
            from django.urls import reverse
            url = reverse('admin:pileg_kokab_rekapsuarapilegkokab_change', args=[obj.pk])
            full_url = f"{url}?{bq}".rstrip('?')
            content = format_html('<div style="line-height:1.2;"><b>{}</b><br><span style="font-size:10.5px; color:#666;">{}</span></div>', obj.kecamatan.nama_kecamatan, obj.kecamatan.kab_kota.nama_kokab)
            return mark_safe(f'<a href="{full_url}">{content}</a>')
        _gen_wilayah.short_description = 'Wilayah Kecamatan'
        _gen_wilayah.admin_order_field = 'kecamatan__nama_kecamatan'
        setattr(self, 'get_wilayah_dyn', _gen_wilayah)

        cols = ['get_wilayah_dyn', 'info_tps_dpt']

        p_params = request.GET.copy()
        for k in ['p', 'f']:
            if k in p_params: p_params.pop(k)
        p_query = p_params.urlencode()
        p_conn = '&' if p_query else ''

        partais = list(Partai.objects.all().order_by('no_urut_partai'))
        for p in partais:
            fn = f'col_p_{p.id}'
            p_id = p.id
            p_logo = p.logo_partai.url if p.logo_partai else None
            p_name = p.nama_partai
            p_no   = p.no_urut_partai
            p_color = getattr(p, 'warna_partai', '#ffc107')

            def _gv(obj, pid=p_id, c=p_color, bq=p_query, qc=p_conn):
                from django.urls import reverse
                
                if not hasattr(obj, '_party_votes'):
                    from django.db.models import Sum
                    qs = DetailSuaraPilegKokab.objects.filter(kecamatan=obj.kecamatan).values('partai_id').annotate(total=Sum('jumlah_suara'))
                    obj._party_votes = {item['partai_id']: item['total'] for item in qs}
                    obj._max_vote = max(obj._party_votes.values()) if obj._party_votes else -1
                
                total = obj._party_votes.get(pid, 0)
                sah = obj.total_suara_sah
                fmt_v = "{:,}".format(total).replace(',', '.')
                url = reverse('admin:pileg_kokab_rekapsuarapilegkokab_change', args=[obj.pk])
                full_url = f"{url}?{bq}{qc}p={pid}".rstrip('&')
                
                is_winner = total > 0 and total == obj._max_vote
                box_style = f"background-color: {c}20; border: 2px solid {c}; border-radius: 6px; padding: 4px;" if is_winner else "padding: 4px;"
                
                if sah > 0:
                    pct = f"({(total/sah*100):.1f}%)"
                    return format_html('<div style="text-align:center; min-width:50px; {}"><a href="{}"><b>{}</b></a><br><small style="color:#666; font-size:11.5px;">{}</small></div>', box_style, full_url, fmt_v, pct)
                return format_html('<div style="text-align:center; {}"><a href="{}">{}</a></div>', box_style, full_url, fmt_v)

            if p_logo:
                _gv.short_description = mark_safe(f'<div style="text-align:center; min-width:40px;"><img src="{p_logo}" title="{p_name}" style="height:20px; object-fit:contain;"><br><span style="font-size:11px;">#{p_no}</span></div>')
            else:
                _gv.short_description = f"#{p_no}"
            setattr(self, fn, _gv)
            cols.append(fn)

        cols += ['total_suara_sah_human', 'total_suara_tidak_sah_human', 'total_suara_semua_human']
        return cols

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        for n, v in form.cleaned_data.items():
            if n.startswith('su_p_'):
                DetailSuaraPilegKokab.objects.update_or_create(
                    kecamatan=obj.kecamatan, partai_id=int(n[5:]), caleg=None,
                    defaults={'jumlah_suara': v or 0})
            elif n.startswith('su_c_'):
                clg = CalegKokab.objects.get(id=int(n[5:]))
                DetailSuaraPilegKokab.objects.update_or_create(
                    kecamatan=obj.kecamatan, partai=clg.partai, caleg=clg,
                    defaults={'jumlah_suara': v or 0})

    def get_fields(self, request, obj=None):
        if obj and obj.pk:
            dummy = RekapSuaraPilegKokabForm(instance=obj, request=request)
            return list(dummy.fields.keys())
        return ['kecamatan', 'total_suara_tidak_sah']

    def get_form(self, request, obj=None, **kwargs):
        class _DynamicForm(RekapSuaraPilegKokabForm):
            pass

        import copy
        _DynamicForm.base_fields = copy.deepcopy(RekapSuaraPilegKokabForm.base_fields)
        _DynamicForm.declared_fields = copy.deepcopy(RekapSuaraPilegKokabForm.declared_fields)

        if obj and obj.pk:
            dummy = RekapSuaraPilegKokabForm(instance=obj, request=request)
            for f_name, f_obj in dummy.fields.items():
                if f_name not in _DynamicForm.base_fields:
                    _DynamicForm.base_fields[f_name] = f_obj
                    _DynamicForm.declared_fields[f_name] = f_obj

        kwargs['form'] = _DynamicForm
        FormClass = super().get_form(request, obj, **kwargs)

        class RequestForm(FormClass):
            def __init__(self_, *args, **kwargs_inner):
                kwargs_inner['request'] = request
                super().__init__(*args, **kwargs_inner)
        return RequestForm

    def get_readonly_fields(self, request, obj=None):
        return ['kecamatan', 'info_tps_dpt']

    def _preserve_query_params(self, request, response):
        from django.http import HttpResponseRedirect, QueryDict
        from urllib.parse import urlparse, urlunparse
        if not isinstance(response, HttpResponseRedirect): return response
        source = None
        if '_preserved_filters' in request.POST:
            source = QueryDict(request.POST.get('_preserved_filters'), mutable=True)
        if not source:
            source = request.GET.copy()
        if source:
            for k in ['_save', '_continue', '_addanother']:
                if k in source: source.pop(k)
            if source:
                parsed = urlparse(response['Location'])
                dest = QueryDict(parsed.query, mutable=True)
                for key, vals in source.lists():
                    dest.setlist(key, vals)
                response['Location'] = urlunparse(parsed._replace(query=dest.urlencode()))
        return response

    def response_add(self, request, obj, post_url_continue=None):
        return self._preserve_query_params(request, super().response_add(request, obj, post_url_continue))

    def response_change(self, request, obj):
        return self._preserve_query_params(request, super().response_change(request, obj))

    def construct_change_message(self, request, form, formsets, add):
        return "Menambah rekap suara Pileg Kokab baru." if add else "Memperbarui rincian perolehan suara (Partai & Caleg Kokab)."

    def info_tps_dpt(self, obj):
        try:
            tps_pm = obj.kecamatan.tps_pemilu
            return format_html('<b>TPS:</b> {}<br><b>DPT:</b> {}', intcomma(tps_pm.rekap_tps_pemilu), intcomma(tps_pm.rekap_dpt_pemilu))
        except:
            return "-"
    info_tps_dpt.short_description = 'TPS / DPT'

    def total_suara_sah_human(self, obj):
        try:
            return format_html('<span style="color:#28a745;"><b>{}</b></span><br><small style="color:#666;">({}%)</small>', intcomma(obj.total_suara_sah), obj.persentase_suara_sah_str)
        except: return "0"
    total_suara_sah_human.short_description = 'Suara Sah'

    def total_suara_tidak_sah_human(self, obj):
        try:
            from django.urls import reverse
            url = reverse('admin:pileg_kokab_rekapsuarapilegkokab_change', args=[obj.pk])
            full_url = f"{url}?ts=1#input-total-tidak-sah"
            return format_html('<a href="{}" title="Edit Suara Tidak Sah Saja" style="color:#dc3545;"><b>{}</b></a><br><small style="color:#666;">({}%)</small>', full_url, intcomma(obj.total_suara_tidak_sah), obj.persentase_suara_tidak_sah_str)
        except: return "0"
    total_suara_tidak_sah_human.short_description = 'Tidak Sah'

    def total_suara_semua_human(self, obj):
        try:
            return format_html('<span style="color:#007bff;"><b>{}</b></span><br><small style="color:#666;">({}%)</small>', intcomma(obj.total_semua_suara), obj.persentase_dpt_masuk_str)
        except: return "0"
    total_suara_semua_human.short_description = 'Total Suara'
