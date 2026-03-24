from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import Paslon, Koalisi, RekapSuara, DetailSuara, Partai, RekapKokabPilpres
from django.contrib.humanize.templatetags.humanize import intcomma
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget
from import_export.formats.base_formats import XLSX
from core.models import Kecamatan, KabupatenKota

# --- 1. SETTING IMPORT EXPORT ---
class RekapSuaraResource(resources.ModelResource):
    kecamatan = fields.Field(column_name='kode_kecamatan', attribute='kecamatan', widget=ForeignKeyWidget(Kecamatan, 'kode_kecamatan'))
    class Meta:
        model = RekapSuara
        import_id_fields = ('kecamatan',)
        fields = ('kecamatan', 'total_suara_tidak_sah')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            for p in Paslon.objects.all():
                fn = f'paslon_{p.no_urut_paslon}'
                self.fields[fn] = fields.Field(column_name=fn, attribute=fn)
        except: pass

    def export_field(self, field, obj, **kwargs):
        if field.attribute and field.attribute.startswith('paslon_'):
            no = field.attribute.split('_')[1]
            ds = DetailSuara.objects.filter(kecamatan=obj.kecamatan, paslon__no_urut_paslon=no).first()
            return ds.jumlah_suara if ds else 0
        return super().export_field(field, obj, **kwargs)

    def after_import_row(self, row, row_result, **kwargs):
        kode = row.get('kode_kecamatan')
        if not kode: return
        
        # Cari Object Kecamatan berdasarkan kode yang ada di Excel
        kec = Kecamatan.objects.filter(kode_kecamatan=kode).first()
        if not kec: return

        for k, v in row.items():
            if k.startswith('paslon_'):
                no = k.split('_')[1]
                p = Paslon.objects.filter(no_urut_paslon=no).first()
                if p:
                    # Cari rekap atau buat baru kalau belum ada
                    DetailSuara.objects.update_or_create(
                        kecamatan_id=kec.id, paslon=p, defaults={'jumlah_suara': int(v or 0)}
                    )

# --- 2. FORM KHUSUS INPUT DI REKAP ---
class RekapSuaraForm(forms.ModelForm):
    class Meta:
        model = RekapSuara
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        obj = self.instance
        if obj and obj.pk:
            ss = obj.total_suara_sah
            tst = obj.total_semua_suara
            txt_pct_ts = obj.persentase_suara_tidak_sah_str
        else:
            ss = 0
            tst = 0
            txt_pct_ts = "0.00"
            
        script_hitung = """
        <style>
        /* Override tampilan bawaan Django Admin agar sesuai screenshot & lebih modern */
        #rekapsuara_form, #content-main {
            font-family: 'Segoe UI', system-ui, -apple-system, BlinkMacSystemFont, 'Roboto', 'Helvetica Neue', sans-serif !important;
        }
        .form-row { 
            padding: 16px 24px; 
            border-bottom: 1px solid #eaeaea; 
            background: #ffffff; 
        }
        .form-row:nth-child(even) { background: #fafafa; }
        .form-row > div { 
            display: flex; 
            align-items: flex-start; 
            margin: 0; 
            padding: 0;
        }
        .form-row label { 
            width: 220px !important; 
            font-weight: 600 !important; 
            font-size: 14px !important;
            padding-top: 12px; 
            color: #333333; 
        }
        .readonly { 
            padding: 12px 16px; 
            background: #f0f2f5; 
            border-radius: 6px; 
            width: 100%; 
            max-width: 500px; 
            display: inline-block; 
            font-weight: 700; 
            font-size: 15px;
            color: #1c1e21;
        }
        /* Custom Input Styling */
        .vIntegerField, .input-paslon, #input-total-tidak-sah { 
            width: 100% !important; 
            max-width: 350px !important; 
            padding: 12px 16px !important; 
            border-radius: 6px !important; 
            border: 1px solid #ced4da !important; 
            font-size: 16px !important; 
            font-weight: 600 !important;
            color: #212529 !important;
            box-shadow: 0 1px 2px rgba(0,0,0,0.02) !important; 
            transition: all 0.2s ease-in-out !important;
            font-family: inherit !important;
        }
        .vIntegerField:focus, .input-paslon:focus, #input-total-tidak-sah:focus { 
            border-color: #80bdff !important; 
            outline: 0 !important;
            box-shadow: 0 0 0 0.2rem rgba(0,123,255,.25) !important;
        }
        
        .help { 
            display: block; 
            margin-top: 10px; 
            font-size: 13px !important; 
            color: #6c757d;
        }
        .help span { 
            color: #495057; 
            font-weight: 800; 
            font-size: 14px;
        }
        </style>
        <script>
        document.addEventListener('DOMContentLoaded', function() {
            let suaraSah = 0;
            try {
                // Ambil div readonly, formatnya "12,943 <br> (45.00%)"
                const sahRow = document.querySelector('.field-total_suara_sah_human .readonly');
                if (sahRow) {
                    const textContent = sahRow.innerText || sahRow.textContent;
                    // Ambil baris pertama text, hapus semua koma & titik
                    const rawNum = textContent.split('\\n')[0].replace(/[,.]/g, '').trim();
                    suaraSah = parseInt(rawNum) || 0;
                }
            } catch(e) {}

            const inputTidakSah = document.getElementById('input-total-tidak-sah');
            const spanTidakSah = document.getElementById('pct-ts-text');
            if (inputTidakSah && spanTidakSah) {
                inputTidakSah.addEventListener('input', function() {
                    const val = parseInt(this.value) || 0;
                    const newTotal = suaraSah + val;
                    let percent = (val / newTotal * 100).toFixed(2);
                    if (isNaN(percent) || !isFinite(percent)) percent = "0.00";
                    spanTidakSah.innerText = `(${percent}%)`;
                });
            }

            document.querySelectorAll('.input-paslon').forEach(function(inputElement) {
                inputElement.addEventListener('input', function() {
                    const idPaslon = this.getAttribute('data-id');
                    const spanOutput = document.getElementById(`pct-paslon-${idPaslon}`);
                    if (spanOutput) {
                        const val = parseInt(this.value) || 0;
                        let percent = (val / suaraSah * 100).toFixed(2);
                        if (isNaN(percent) || !isFinite(percent)) percent = "0.00";
                        spanOutput.innerText = `(${percent}%)`;
                    }
                });
            });
        });
        </script>
        """

        self.fields['total_suara_tidak_sah'].help_text = format_html(
            '<span id="pct-ts-text">({}%)</span> dari Total Suara{}', 
            txt_pct_ts, mark_safe(script_hitung)
        )
        self.fields['total_suara_tidak_sah'].widget.attrs.update({
            'id': 'input-total-tidak-sah'
        })
        
        try:
            for p in Paslon.objects.all():
                fn = f'suara_paslon_{p.no_urut_paslon}'
                if fn in self.fields:
                    v = obj.get_suara_paslon(p) if obj and obj.pk else 0
                    txt_pct = obj.get_persentase_paslon_str(p) if obj and obj.pk else "0.00"
                    
                    self.fields[fn].initial = v
                    self.fields[fn].label = f"Suara # {p.no_urut_paslon} ({p.nama_capres})"
                    self.fields[fn].help_text = format_html(
                        '<span id="pct-paslon-{}">({}%)</span> dari Suara Sah', 
                        p.no_urut_paslon, txt_pct
                    )
                    self.fields[fn].widget.attrs.update({
                        'class': 'input-paslon',
                        'data-id': p.no_urut_paslon,
                    })
        except: pass

class KabupatenListFilter(admin.SimpleListFilter):
    title = 'Kabupaten/Kota'
    parameter_name = 'kokab'

    def lookups(self, request, model_admin):
        kokab_list = KabupatenKota.objects.all().order_by('nama_kokab')
        return [(k.id, k.nama_kokab) for k in kokab_list]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(kecamatan__kab_kota_id=self.value())
        return queryset

@admin.register(RekapSuara)
class RekapSuaraAdmin(ImportExportModelAdmin):
    resource_class = RekapSuaraResource
    formats = [XLSX]
    list_per_page = 20
    list_max_show_all = 700
    ordering = ('kecamatan__kab_kota', 'kecamatan__nama_kecamatan')
    search_fields = ('kecamatan__nama_kecamatan',)
    list_filter = (KabupatenListFilter,)

    def has_delete_permission(self, request, obj=None):
        return False

    # Optimasi query biar loading cepat dan enteng
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'kecamatan', 'kecamatan__tps_pemilu', 'kecamatan__kab_kota'
        ).prefetch_related('kecamatan__detail_pilpres')

    # Layout Detail Edit View (Detail Change)
    def get_form(self, request, obj=None, **kwargs):
        class _RekapForm(RekapSuaraForm):
            pass
                
        import copy
        _RekapForm.base_fields = copy.deepcopy(RekapSuaraForm.base_fields)
        _RekapForm.declared_fields = copy.deepcopy(RekapSuaraForm.declared_fields)

        try:
            for p in Paslon.objects.all():
                fn = f'suara_paslon_{p.no_urut_paslon}'
                fld = forms.IntegerField(required=False)
                _RekapForm.base_fields[fn] = fld
                _RekapForm.declared_fields[fn] = fld
        except: pass
        
        kwargs['form'] = _RekapForm
        return super().get_form(request, obj, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        return ['kecamatan', 'info_tps_dpt', 'total_suara_semua_human', 'total_suara_sah_human']

    def get_fields(self, request, obj=None):
        f = ['kecamatan', 'info_tps_dpt', 'total_suara_semua_human', 'total_suara_sah_human', 'total_suara_tidak_sah']
        try:
            for p in Paslon.objects.all():
                f.append(f'suara_paslon_{p.no_urut_paslon}')
        except: pass
        return f

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        for p in Paslon.objects.all():
            fn = f'suara_paslon_{p.no_urut_paslon}'
            if fn in form.cleaned_data:
                nilai = form.cleaned_data[fn]
                if nilai is not None:
                    DetailSuara.objects.update_or_create(
                        kecamatan=obj.kecamatan,
                        paslon=p,
                        defaults={'jumlah_suara': nilai}
                    )

    # List View Setting
    def get_list_display(self, request):
        paslons = Paslon.objects.all()
        for p in paslons:
            fn = f'paslon_{p.no_urut_paslon}'
            if not hasattr(self, fn):
                def make_gv(paslon):
                    def gv(obj):
                        try:
                            v = obj.get_suara_paslon(paslon)
                            txt_pct = obj.get_persentase_paslon_str(paslon)
                            return format_html('<b>{}</b><br><small style="color:#666;">({}%)</small>', intcomma(v), txt_pct)
                        except: return "0"
                    return gv
                
                method = make_gv(p)
                foto = format_html('<img src="{}" style="width:25px; height:25px; min-width:25px; object-fit:cover; border-radius:3px; vertical-align:middle; margin-right:5px;"/>', p.foto_paslon.url) if p.foto_paslon else ""
                method.short_description = format_html('{} #{}', foto, p.no_urut_paslon)
                setattr(self, fn, method)
        
        cols = ['wilayah', 'info_tps_dpt']
        cols += [f'paslon_{p.no_urut_paslon}' for p in paslons]
        cols += ['total_suara_sah_human', 'total_suara_tidak_sah_human', 'total_suara_semua_human']
        return cols

    def info_tps_dpt(self, obj):
        try:
            t = obj.kecamatan.tps_pemilu
            return format_html('<b>TPS:</b> {}<br><b>DPT:</b> {}', intcomma(t.rekap_tps_pemilu), intcomma(t.rekap_dpt_pemilu))
        except: return "-"
    info_tps_dpt.short_description = 'Info TPS/DPT'

    def wilayah(self, obj):
        return format_html('<b>{}</b><br><small style="color:#666;">{}</small>', obj.kecamatan.nama_kecamatan, obj.kecamatan.kab_kota.nama_kokab)
    wilayah.short_description = 'Wilayah'
    wilayah.admin_order_field = 'kecamatan__nama_kecamatan'

    def total_suara_sah_human(self, obj):
        try:
            txt_p = obj.persentase_suara_sah_str
            return format_html('<span style="color:#28a745;"><b>{}</b></span><br><small style="color:#666;">({}%)</small>', intcomma(obj.total_suara_sah), txt_p)
        except: return "0"
    total_suara_sah_human.short_description = 'Suara Sah'

    def total_suara_tidak_sah_human(self, obj):
        try:
            from django.urls import reverse
            txt_p = obj.persentase_suara_tidak_sah_str
            url = reverse('admin:pilpres_rekapsuara_change', args=[obj.pk])
            return format_html('<a href="{}#input-total-tidak-sah" title="Edit Suara Tidak Sah" style="color:#dc3545;"><b>{}</b></a><br><small style="color:#666;">({}%)</small>', url, intcomma(obj.total_suara_tidak_sah), txt_p)
        except: return "0"
    total_suara_tidak_sah_human.short_description = 'Tidak Sah'

    def total_suara_semua_human(self, obj):
        try:
            txt_p = obj.persentase_dpt_masuk_str
            return format_html('<span style="color:#007bff;"><b>{}</b></span><br><small style="color:#666;">({}%)</small>', intcomma(obj.total_semua_suara), txt_p)
        except: return "0"
    total_suara_semua_human.short_description = 'Total Suara'

from django.contrib.admin.widgets import FilteredSelectMultiple
from django.core.exceptions import ValidationError

# --- 3. PASLON ADMIN ---
class PaslonForm(forms.ModelForm):
    partai_koalisi = forms.ModelMultipleChoiceField(
        queryset=Partai.objects.all(),
        widget=FilteredSelectMultiple("Koalisi Partai", is_stacked=False),
        required=False,
    )

    class Meta:
        model = Paslon
        fields = '__all__'
        widgets = {
            'warna_hex': forms.TextInput(attrs={'type': 'color', 'style': 'height: 40px; width: 60px; padding: 0; border: none; cursor: pointer;'}),
        }

    def clean_partai_koalisi(self):
        partai_terpilih = self.cleaned_data.get('partai_koalisi', [])
        for prt in partai_terpilih:
            # Check if this partai is already registered to ANOTHER koalisi
            konflik = Koalisi.objects.filter(partai=prt)
            if self.instance and self.instance.pk:
                konflik = konflik.exclude(paslon=self.instance)
            konflik = konflik.first()
            if konflik:
                raise ValidationError(f"GAGAL: Partai '{prt.nama_partai}' sudah menjadi koalisi Paslon {konflik.paslon.nama_capres}!")
        return partai_terpilih

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Pre-select partai yang sudah masuk koalisi Paslon ini
            self.fields['partai_koalisi'].initial = self.instance.partai_pendukung.values_list('partai', flat=True)

    def save(self, commit=True):
        paslon = super().save(commit=commit)
        if commit:
            self._save_koalisi(paslon)
        else:
            old_save_m2m = self.save_m2m
            def new_save_m2m():
                old_save_m2m()
                self._save_koalisi(paslon)
            self.save_m2m = new_save_m2m
        return paslon

    def _save_koalisi(self, paslon):
        partai_terpilih = self.cleaned_data.get('partai_koalisi', [])
        # Hapus yang tidak dicentang lagi
        Koalisi.objects.filter(paslon=paslon).exclude(partai__in=partai_terpilih).delete()
        # Tambah yang baru dicentang
        for prt in partai_terpilih:
            Koalisi.objects.get_or_create(paslon=paslon, partai=prt)

@admin.register(Paslon)
class PaslonAdmin(admin.ModelAdmin):
    form = PaslonForm
    list_display = ('identitas', 'logos_koalisi', 'visual_warna')
    fieldsets = (
        (None, {
            'fields': ('no_urut_paslon', 'nama_capres', 'nama_cawapres', 'foto_paslon', 'warna_hex', 'partai_koalisi')
        }),
    )
    
    def identitas(self, obj):
        url = obj.foto_paslon.url if obj.foto_paslon else ""
        img = format_html('<img src="{}" style="width:40px; height:40px; min-width:40px; object-fit:cover; border-radius:5px; margin-right:10px;"/>', url) if url else ""
        return format_html('{} #{} {} - {}', img, obj.no_urut_paslon, obj.nama_capres, obj.nama_cawapres)
    identitas.short_description = "Pasangan Calon"

    def logos_koalisi(self, obj):
        # Pakai object-fit: contain biar logo partai tidak gepeng
        logos = "".join([format_html('<img src="{}" style="height:25px; max-width:40px; object-fit:contain; margin-right:6px;" title="{}"/>', k.partai.logo_partai.url, k.partai.nama_partai) for k in obj.partai_pendukung.all() if k.partai.logo_partai])
        return format_html(logos) if logos else "-"
    logos_koalisi.short_description = "Koalisi Partai"

    def visual_warna(self, obj):
        return format_html(
            '<div style="width: 24px; height: 24px; border-radius: 50%; background-color: {}; border: 1px solid #ccc; box-shadow: 0 2px 4px rgba(0,0,0,0.1);" title="{}"></div>',
            obj.warna_hex, obj.warna_hex
        )
    visual_warna.short_description = "Warna"

from django.db.models import Sum

@admin.register(RekapKokabPilpres)
class RekapKokabPilpresAdmin(admin.ModelAdmin):
    ordering = ('nama_kokab',)

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False

    def get_queryset(self, request):
        return super().get_queryset(request)

    def get_list_display(self, request):
        paslons = Paslon.objects.all()
        for p in paslons:
            fn = f'total_paslon_{p.no_urut_paslon}'
            if not hasattr(self, fn):
                def make_gv(paslon):
                    def gv(obj):
                        total_paslon = obj.get_total_suara_paslon(paslon)
                        total_sah = getattr(obj, 'agg_sah', 0)
                        pct = (total_paslon / total_sah * 100) if total_sah > 0 else 0
                        pct_str = f"{pct:.2f}"
                        return format_html('<b>{}</b><br><small style="color:#666;">({}%)</small>', intcomma(total_paslon), pct_str)
                    return gv
                
                method = make_gv(p)
                foto = format_html('<img src="{}" style="width:20px; height:20px; min-width:20px; object-fit:cover; border-radius:3px; vertical-align:middle; margin-right:5px;"/>', p.foto_paslon.url) if p.foto_paslon else ""
                method.short_description = format_html('{} #{}', foto, p.no_urut_paslon)
                setattr(self, fn, method)
        
        cols = ['wilayah_kokab', 'info_tps_dpt_kokab']
        cols += [f'total_paslon_{p.no_urut_paslon}' for p in paslons]
        cols += ['total_sah_kokab', 'total_tidak_sah_kokab', 'total_semua_kokab']
        return cols

    def wilayah_kokab(self, obj):
        from django.urls import reverse
        url = reverse('admin:pilpres_rekapsuara_changelist')
        full_url = f"{url}?kokab={obj.id}"
        return format_html('<a href="{}" title="Buka Detail Kecamatan di Kokab Ini" style="color:#007bff;"><b>{}</b></a>', full_url, obj.nama_kokab)
    wilayah_kokab.short_description = 'Kabupaten / Kota'
    wilayah_kokab.admin_order_field = 'nama_kokab'

    def info_tps_dpt_kokab(self, obj):
        return format_html('<b>TPS:</b> {}<br><b>DPT:</b> {}', intcomma(getattr(obj, 'agg_tps', 0)), intcomma(getattr(obj, 'agg_dpt', 0)))
    info_tps_dpt_kokab.short_description = 'Total TPS/DPT'

    def total_sah_kokab(self, obj):
        pct_str = f"{obj.pct_sah:.2f}"
        return format_html('<span style="color:#28a745;"><b>{}</b></span><br><small style="color:#666;">({}%)</small>', intcomma(getattr(obj, 'agg_sah', 0)), pct_str)
    total_sah_kokab.short_description = 'Total Sah'

    def total_tidak_sah_kokab(self, obj):
        pct_str = f"{obj.pct_tidak_sah:.2f}"
        return format_html('<span style="color:#dc3545;"><b>{}</b></span><br><small style="color:#666;">({}%)</small>', intcomma(getattr(obj, 'agg_tidak_sah', 0)), pct_str)
    total_tidak_sah_kokab.short_description = 'Tidak Sah'

    def total_semua_kokab(self, obj):
        pct_str = f"{obj.pct_semua:.2f}"
        return format_html('<span style="color:#007bff;"><b>{}</b></span><br><small style="color:#666;">({}%)</small>', intcomma(obj.t_total), pct_str)
    total_semua_kokab.short_description = 'Total Suara'