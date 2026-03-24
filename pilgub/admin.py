from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import PaslonGubernur, KoalisiGubernur, RekapSuaraGubernur, DetailSuaraGubernur, RekapKokabPilgub
from core.models import Kecamatan, Partai, KabupatenKota
from django.contrib.humanize.templatetags.humanize import intcomma
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget
from import_export.formats.base_formats import XLSX

# --- 1. SETTING IMPORT EXPORT ---
class RekapSuaraGubernurResource(resources.ModelResource):
    kecamatan = fields.Field(column_name='kode_kecamatan', attribute='kecamatan', widget=ForeignKeyWidget(Kecamatan, 'kode_kecamatan'))
    class Meta:
        model = RekapSuaraGubernur
        import_id_fields = ('kecamatan',)
        fields = ('kecamatan', 'total_suara_tidak_sah')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            for p in PaslonGubernur.objects.all():
                fn = f'paslon_{p.no_urut_paslon}'
                self.fields[fn] = fields.Field(column_name=fn, attribute=fn)
        except: pass

    def export_field(self, field, obj, **kwargs):
        if field.attribute and field.attribute.startswith('paslon_'):
            no = field.attribute.split('_')[1]
            ds = DetailSuaraGubernur.objects.filter(kecamatan=obj.kecamatan, paslon__no_urut_paslon=no).first()
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
                p = PaslonGubernur.objects.filter(no_urut_paslon=no).first()
                if p:
                    DetailSuaraGubernur.objects.update_or_create(
                        kecamatan_id=kec.id, paslon=p, defaults={'jumlah_suara': int(v or 0)}
                    )

# --- 2. FORM KHUSUS INPUT DI REKAP ---
class RekapSuaraGubernurForm(forms.ModelForm):
    class Meta:
        model = RekapSuaraGubernur
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
        /* Override tampilan admin untuk layout modern */
        #rekapsuara_form, #content-main { font-family: 'Segoe UI', system-ui, -apple-system, BlinkMacSystemFont, 'Roboto', 'Helvetica Neue', sans-serif !important; }
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
        <script>
        document.addEventListener('DOMContentLoaded', function() {
            let suaraSah = 0;
            try {
                const sahRow = document.querySelector('.field-total_suara_sah_human .readonly');
                if (sahRow) {
                    const textContent = sahRow.innerText || sahRow.textContent;
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
            for p in PaslonGubernur.objects.all():
                fn = f'suara_paslon_{p.no_urut_paslon}'
                if fn in self.fields:
                    v = obj.get_suara_paslon(p) if obj and obj.pk else 0
                    txt_pct = obj.get_persentase_paslon_str(p) if obj and obj.pk else "0.00"
                    
                    self.fields[fn].initial = v
                    self.fields[fn].label = f"Suara # {p.no_urut_paslon} ({p.nama_cagub})"
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

@admin.register(RekapSuaraGubernur)
class RekapSuaraGubernurAdmin(ImportExportModelAdmin):
    resource_class = RekapSuaraGubernurResource
    formats = [XLSX]
    list_per_page = 20
    list_max_show_all = 700
    ordering = ('kecamatan__kab_kota', 'kecamatan__nama_kecamatan')
    search_fields = ('kecamatan__nama_kecamatan',)
    list_filter = (KabupatenListFilter,)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'kecamatan', 'kecamatan__tps_pilkada', 'kecamatan__kab_kota'
        ).prefetch_related('kecamatan__detail_pilgub')

    def get_form(self, request, obj=None, **kwargs):
        class _RekapForm(RekapSuaraGubernurForm):
            pass
                
        import copy
        _RekapForm.base_fields = copy.deepcopy(RekapSuaraGubernurForm.base_fields)
        _RekapForm.declared_fields = copy.deepcopy(RekapSuaraGubernurForm.declared_fields)

        try:
            for p in PaslonGubernur.objects.all():
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
            for p in PaslonGubernur.objects.all():
                f.append(f'suara_paslon_{p.no_urut_paslon}')
        except: pass
        return f

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        for p in PaslonGubernur.objects.all():
            fn = f'suara_paslon_{p.no_urut_paslon}'
            if fn in form.cleaned_data:
                nilai = form.cleaned_data[fn]
                if nilai is not None:
                    DetailSuaraGubernur.objects.update_or_create(
                        kecamatan=obj.kecamatan,
                        paslon=p,
                        defaults={'jumlah_suara': nilai}
                    )

    def get_list_display(self, request):
        paslons = PaslonGubernur.objects.all()
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
            t = obj.kecamatan.tps_pilkada
            return format_html('<b>TPS:</b> {}<br><b>DPT:</b> {}', intcomma(t.rekap_tps_pilkada), intcomma(t.rekap_dpt_pilkada))
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
            url = reverse('admin:pilgub_rekapsuaragubernur_change', args=[obj.pk])
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
class PaslonGubernurForm(forms.ModelForm):
    partai_koalisi = forms.ModelMultipleChoiceField(
        queryset=Partai.objects.all(),
        widget=FilteredSelectMultiple("Koalisi Partai", is_stacked=False),
        required=False,
    )

    class Meta:
        model = PaslonGubernur
        fields = '__all__'
        widgets = {
            'warna_hex': forms.TextInput(attrs={'type': 'color', 'style': 'height: 40px; width: 60px; padding: 0; border: none; cursor: pointer;'}),
        }

    def clean_partai_koalisi(self):
        partai_terpilih = self.cleaned_data.get('partai_koalisi', [])
        for prt in partai_terpilih:
            # Check if this partai is already registered to ANOTHER koalisi
            konflik = KoalisiGubernur.objects.filter(partai=prt)
            if self.instance and self.instance.pk:
                konflik = konflik.exclude(paslon=self.instance)
            konflik = konflik.first()
            if konflik:
                raise ValidationError(f"GAGAL: Partai '{prt.nama_partai}' sudah menjadi koalisi Paslon {konflik.paslon.nama_cagub}!")
        return partai_terpilih

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Pre-select partai yang sudah masuk koalisi PaslonGubernur ini
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
        KoalisiGubernur.objects.filter(paslon=paslon).exclude(partai__in=partai_terpilih).delete()
        # Tambah yang baru dicentang
        for prt in partai_terpilih:
            KoalisiGubernur.objects.get_or_create(paslon=paslon, partai=prt)

@admin.register(PaslonGubernur)
class PaslonGubernurAdmin(admin.ModelAdmin):
    form = PaslonGubernurForm
    list_display = ('identitas', 'logos_koalisi', 'visual_warna')
    fieldsets = (
        (None, {
            'fields': ('no_urut_paslon', 'nama_cagub', 'nama_cawagub', 'foto_paslon', 'warna_hex', 'partai_koalisi')
        }),
    )
    
    def identitas(self, obj):
        url = obj.foto_paslon.url if obj.foto_paslon else ""
        img = format_html('<img src="{}" style="width:40px; height:40px; min-width:40px; object-fit:cover; border-radius:5px; margin-right:10px;"/>', url) if url else ""
        return format_html('{} #{} {} - {}', img, obj.no_urut_paslon, obj.nama_cagub, obj.nama_cawagub)
    identitas.short_description = "Pasangan Calon Gubernur"

    def logos_koalisi(self, obj):
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

@admin.register(RekapKokabPilgub)
class RekapKokabPilgubAdmin(admin.ModelAdmin):
    ordering = ('nama_kokab',)

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False

    def get_queryset(self, request):
        return super().get_queryset(request)

    def get_list_display(self, request):
        paslons = PaslonGubernur.objects.all()
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
                foto = format_html('<img src="{}" style="width:20px; height:20px; min-width:20px; border-radius:3px; object-fit:cover; vertical-align:middle; margin-right:5px;"/>', p.foto_paslon.url) if p.foto_paslon else ""
                method.short_description = format_html('{} #{}', foto, p.no_urut_paslon)
                setattr(self, fn, method)
        
        cols = ['wilayah_kokab', 'info_tps_dpt_kokab']
        cols += [f'total_paslon_{p.no_urut_paslon}' for p in paslons]
        cols += ['total_sah_kokab', 'total_tidak_sah_kokab', 'total_semua_kokab']
        return cols

    def wilayah_kokab(self, obj):
        from django.urls import reverse
        url = reverse('admin:pilgub_rekapsuaragubernur_changelist')
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
