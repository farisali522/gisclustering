from django.contrib import admin
from django import forms
from django.contrib import messages
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import PaslonWalbup, KoalisiWalbup, RekapSuaraWalbup, DetailSuaraWalbup, RekapKokabPilwalbup
from core.models import Kecamatan, Partai, KabupatenKota
from django.db.models import Max
from django.contrib.humanize.templatetags.humanize import intcomma
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget
from import_export.formats.base_formats import XLSX
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.core.exceptions import ValidationError

# --- 1. SETTING IMPORT EXPORT ---
class RekapSuaraWalbupResource(resources.ModelResource):
    kecamatan = fields.Field(column_name='kode_kecamatan', attribute='kecamatan', widget=ForeignKeyWidget(Kecamatan, 'kode_kecamatan'))
    
    class Meta:
        model = RekapSuaraWalbup
        import_id_fields = ('kecamatan',)
        fields = ('kecamatan', 'total_suara_tidak_sah')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            db_max = PaslonWalbup.objects.aggregate(Max('no_urut_paslon'))['no_urut_paslon__max'] or 0
            max_no = max(5, db_max) 
            for i in range(1, max_no + 1):
                fn = f'paslon_{i}'
                self.fields[fn] = fields.Field(column_name=fn, attribute=fn)
        except: pass

    def export_field(self, field, obj, **kwargs):
        if field.attribute and field.attribute.startswith('paslon_'):
            no = field.attribute.split('_')[1]
            ds = DetailSuaraWalbup.objects.filter(
                kecamatan=obj.kecamatan, 
                paslon__no_urut_paslon=no,
                paslon__kab_kota=obj.kecamatan.kab_kota
            ).first()
            return ds.jumlah_suara if ds else 0
        return super().export_field(field, obj, **kwargs)

    def after_import_row(self, row, row_result, **kwargs):
        kode = row.get('kode_kecamatan')
        if not kode: return
        kec = Kecamatan.objects.filter(kode_kecamatan=kode).select_related('kab_kota').first()
        if not kec: return
        for k, v in row.items():
            if k and str(k).startswith('paslon_'):
                no = k.split('_')[1]
                p = PaslonWalbup.objects.filter(no_urut_paslon=no, kab_kota=kec.kab_kota).first()
                if p:
                    DetailSuaraWalbup.objects.update_or_create(
                        kecamatan=kec, paslon=p, defaults={'jumlah_suara': int(v or 0)}
                    )

# --- 2. FORM KHUSUS INPUT DI REKAP ---
class RekapSuaraWalbupForm(forms.ModelForm):
    class Meta:
        model = RekapSuaraWalbup
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        obj = self.instance
        if obj and hasattr(obj, 'kecamatan') and obj.kecamatan:
            txt_pct_ts = obj.persentase_suara_tidak_sah_str
            kab_kota = obj.kecamatan.kab_kota
            paslons = PaslonWalbup.objects.filter(kab_kota=kab_kota)
        else:
            txt_pct_ts = "0.00"
            paslons = []
            
        script_hitung = """
        <style>
        #rekapsuarawalbup_form, #content-main { font-family: 'Segoe UI', system-ui, -apple-system, BlinkMacSystemFont, 'Roboto', 'Helvetica Neue', sans-serif !important; }
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
        self.fields['total_suara_tidak_sah'].widget.attrs.update({'id': 'input-total-tidak-sah'})
        
        for p in paslons:
            fn = f'suara_paslon_{p.no_urut_paslon}'
            if fn in self.fields:
                v = obj.get_suara_paslon(p) if obj and obj.pk else 0
                txt_pct = obj.get_persentase_paslon_str(p) if obj and obj.pk else "0.00"
                self.fields[fn].initial = v
                self.fields[fn].label = f"Suara # {p.no_urut_paslon} ({p.nama_calon})"
                self.fields[fn].help_text = format_html(
                    '<span id="pct-paslon-{}">({}%)</span> dari Suara Sah', 
                    p.no_urut_paslon, txt_pct
                )
                self.fields[fn].widget.attrs.update({'class': 'input-paslon', 'data-id': p.no_urut_paslon})

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

@admin.register(RekapSuaraWalbup)
class RekapSuaraWalbupAdmin(ImportExportModelAdmin):
    resource_class = RekapSuaraWalbupResource
    formats = [XLSX]
    list_per_page = 20
    ordering = ('kecamatan__kab_kota', 'kecamatan__nama_kecamatan')
    search_fields = ('kecamatan__nama_kecamatan',)
    list_filter = (KabupatenListFilter,)
    actions = ['inisialisasi_rekap']

    def inisialisasi_rekap(self, request, queryset):
        kecamatans = Kecamatan.objects.all()
        count = 0
        for kec in kecamatans:
            obj, created = RekapSuaraWalbup.objects.get_or_create(kecamatan=kec)
            if created: count += 1
        self.message_user(request, f"Sukses! {count} baris rekap baru telah dibuat.", messages.SUCCESS)
    inisialisasi_rekap.short_description = "Bikin Baris Rekap Kosong Untuk Semua Kecamatan"

    def has_delete_permission(self, request, obj=None): return False
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'kecamatan', 'kecamatan__kab_kota', 'kecamatan__tps_pilkada'
        ).prefetch_related('kecamatan__detail_pilwalbup')

    def get_form(self, request, obj=None, **kwargs):
        class _DynamicForm(RekapSuaraWalbupForm): pass
        import copy
        _DynamicForm.base_fields = copy.deepcopy(RekapSuaraWalbupForm.base_fields)
        _DynamicForm.declared_fields = copy.deepcopy(RekapSuaraWalbupForm.declared_fields)
        if obj and hasattr(obj, 'kecamatan') and obj.kecamatan:
            paslons = PaslonWalbup.objects.filter(kab_kota=obj.kecamatan.kab_kota)
            for p in paslons:
                fn = f'suara_paslon_{p.no_urut_paslon}'
                fld = forms.IntegerField(required=False)
                _DynamicForm.base_fields[fn] = fld
                _DynamicForm.declared_fields[fn] = fld
        kwargs['form'] = _DynamicForm
        return super().get_form(request, obj, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        # Jika sedang edit (obj ada pk), buat kecamatan readonly. Kalau baru (Add), boleh pilih.
        if obj and obj.pk:
            return ['kecamatan', 'info_tps_dpt', 'total_suara_semua_human', 'total_suara_sah_human']
        return ['info_tps_dpt', 'total_suara_semua_human', 'total_suara_sah_human']

    def get_fields(self, request, obj=None):
        f = ['kecamatan', 'info_tps_dpt', 'total_suara_semua_human', 'total_suara_sah_human', 'total_suara_tidak_sah']
        if obj and hasattr(obj, 'kecamatan') and obj.kecamatan:
            paslons = PaslonWalbup.objects.filter(kab_kota=obj.kecamatan.kab_kota)
            for p in paslons:
                f.append(f'suara_paslon_{p.no_urut_paslon}')
        return f

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.kecamatan:
            paslons = PaslonWalbup.objects.filter(kab_kota=obj.kecamatan.kab_kota)
            for p in paslons:
                fn = f'suara_paslon_{p.no_urut_paslon}'
                if fn in form.cleaned_data:
                    nilai = form.cleaned_data[fn]
                    if nilai is not None:
                        DetailSuaraWalbup.objects.update_or_create(
                            kecamatan=obj.kecamatan, paslon=p, defaults={'jumlah_suara': nilai}
                        )

    def get_list_display(self, request):
        # Cari nomor urut tertinggi secara global untuk header kolom
        max_no = PaslonWalbup.objects.aggregate(Max('no_urut_paslon'))['no_urut_paslon__max'] or 0
        
        cols = ['wilayah', 'info_tps_dpt']
        
        # Tambahkan kolom paslon #1, #2, dst (selalu muncul)
        for i in range(1, max_no + 1):
            fn = f'display_paslon_{i}'
            if not hasattr(self, fn):
                def make_gv(no):
                    def gv(obj):
                        # Cari Paslon di kabupaten kecamatan ini dengan nomor urut 'no'
                        p = PaslonWalbup.objects.filter(kab_kota=obj.kecamatan.kab_kota, no_urut_paslon=no).first()
                        if not p: return "-"
                        
                        v = obj.get_suara_paslon(p)
                        txt_pct = obj.get_persentase_paslon_str(p)
                        
                        # Tampilkan foto kecil biar tahu itu suara siapa (karena tiap baris paslonnya beda)
                        foto = format_html('<img src="{}" style="width:18px; height:18px; min-width:18px; border-radius:50%; object-fit:cover; vertical-align:middle; margin-right:4px;"/>', p.foto_paslon.url) if p.foto_paslon else ""
                        return format_html('{}<b>{}</b> <br><small style="color:#666;">({}%)</small>', foto, intcomma(v), txt_pct)
                    return gv
                
                method = make_gv(i)
                method.short_description = f"#{i}"
                setattr(self, fn, method)
            cols.append(fn)

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

    def total_suara_sah_human(self, obj):
        return format_html('<span style="color:#28a745;"><b>{}</b></span><br><small style="color:#666;">({}%)</small>', intcomma(obj.total_suara_sah), obj.persentase_suara_sah_str)
    total_suara_sah_human.short_description = 'Suara Sah'

    def total_suara_tidak_sah_human(self, obj):
        from django.urls import reverse
        url = reverse('admin:pilwalbup_rekapsuarawalbup_change', args=[obj.pk])
        return format_html('<a href="{}#input-total-tidak-sah" title="Edit Suara Tidak Sah" style="color:#dc3545;"><b>{}</b></a><br><small style="color:#666;">({}%)</small>', url, intcomma(obj.total_suara_tidak_sah), obj.persentase_suara_tidak_sah_str)
    total_suara_tidak_sah_human.short_description = 'Tidak Sah'

    def total_suara_semua_human(self, obj):
        return format_html('<span style="color:#007bff;"><b>{}</b></span><br><small style="color:#666;">({}%)</small>', intcomma(obj.total_semua_suara), obj.persentase_dpt_masuk_str)
    total_suara_semua_human.short_description = 'Total Suara'

# --- 3. PASLON ADMIN ---
class PaslonWalbupForm(forms.ModelForm):
    partai_koalisi = forms.ModelMultipleChoiceField(
        queryset=Partai.objects.all(),
        widget=FilteredSelectMultiple("Koalisi Partai", is_stacked=False),
        required=False,
    )
    class Meta:
        model = PaslonWalbup
        fields = '__all__'
        widgets = {
            'warna_hex': forms.TextInput(attrs={'type': 'color', 'style': 'height: 40px; width: 60px; padding: 0; border: none; cursor: pointer;'}),
        }
    def clean_partai_koalisi(self):
        partai_terpilih = self.cleaned_data.get('partai_koalisi', [])
        kab_kota = self.cleaned_data.get('kab_kota')
        if kab_kota:
            for prt in partai_terpilih:
                konflik = KoalisiWalbup.objects.filter(kab_kota=kab_kota, partai=prt)
                if self.instance and self.instance.pk:
                    konflik = konflik.exclude(paslon=self.instance)
                konflik = konflik.first()
                if konflik:
                    raise ValidationError(f"GAGAL: Di {kab_kota.nama_kokab}, Partai '{prt.nama_partai}' sudah menjadi koalisi Paslon {konflik.paslon.nama_calon}!")
        return partai_terpilih

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['partai_koalisi'].initial = self.instance.partai_pendukung.values_list('partai', flat=True)

    def save(self, commit=True):
        paslon = super().save(commit=commit)
        if commit: self._save_koalisi(paslon)
        else:
            old_save_m2m = self.save_m2m
            def new_save_m2m():
                old_save_m2m()
                self._save_koalisi(paslon)
            self.save_m2m = new_save_m2m
        return paslon

    def _save_koalisi(self, paslon):
        partai_terpilih = self.cleaned_data.get('partai_koalisi', [])
        KoalisiWalbup.objects.filter(paslon=paslon).exclude(partai__in=partai_terpilih).delete()
        for prt in partai_terpilih:
            KoalisiWalbup.objects.get_or_create(paslon=paslon, partai=prt, kab_kota=paslon.kab_kota)

@admin.register(PaslonWalbup)
class PaslonWalbupAdmin(admin.ModelAdmin):
    form = PaslonWalbupForm
    list_display = ('identitas', 'kab_kota', 'logos_koalisi', 'visual_warna')
    list_filter = ('kab_kota',)
    search_fields = ('nama_calon', 'kab_kota__nama_kokab')
    def identitas(self, obj):
        url = obj.foto_paslon.url if obj.foto_paslon else ""
        img = format_html('<img src="{}" style="width:40px; height:40px; min-width:40px; object-fit:cover; border-radius:5px; margin-right:10px;"/>', url) if url else ""
        return format_html('{} #{} {} - {}', img, obj.no_urut_paslon, obj.nama_calon, obj.nama_wakil)
    identitas.short_description = "Pasangan Calon"
    def logos_koalisi(self, obj):
        logos = "".join([format_html('<img src="{}" style="height:25px; max-width:40px; object-fit:contain; margin-right:6px;" title="{}"/>', k.partai.logo_partai.url, k.partai.nama_partai) for k in obj.partai_pendukung.all() if k.partai.logo_partai])
        return format_html(logos) if logos else "-"
    logos_koalisi.short_description = "Koalisi Partai"
    def visual_warna(self, obj):
        return format_html('<div style="width: 20px; height: 20px; border-radius: 50%; background: {}; border: 1px solid #ccc;"></div>', obj.warna_hex)

@admin.register(RekapKokabPilwalbup)
class RekapKokabPilwalbupAdmin(admin.ModelAdmin):
    ordering = ('nama_kokab',)
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False

    def get_queryset(self, request):
        return super().get_queryset(request)

    def get_list_display(self, request):
        max_no = PaslonWalbup.objects.aggregate(Max('no_urut_paslon'))['no_urut_paslon__max'] or 0
        cols = ['wilayah_kokab', 'info_tps_dpt_kokab']
        for i in range(1, max_no + 1):
            fn = f'total_paslon_{i}'
            if not hasattr(self, fn):
                def make_gv(no):
                    def gv(obj):
                        p = PaslonWalbup.objects.filter(kab_kota=obj, no_urut_paslon=no).first()
                        if not p: return "-"
                        total_p = obj.get_total_suara_paslon(p)
                        total_sah = getattr(obj, 'agg_sah', 0)
                        pct = (total_p / total_sah * 100) if total_sah > 0 else 0
                        pct_str = f"{pct:.2f}"
                        foto = format_html('<img src="{}" style="width:18px; height:18px; min-width:18px; border-radius:50%; object-fit:cover; vertical-align:middle; margin-right:4px;"/>', p.foto_paslon.url) if p.foto_paslon else ""
                        return format_html('{}<b>{}</b> <br><small style="color:#666;">({}%)</small>', foto, intcomma(total_p), pct_str)
                    return gv
                method = make_gv(i)
                method.short_description = f"#{i}"
                setattr(self, fn, method)
            cols.append(fn)
        cols += ['total_sah_kokab', 'total_tidak_sah_kokab', 'total_semua_kokab']
        return cols

    def wilayah_kokab(self, obj):
        from django.urls import reverse
        url = reverse('admin:pilwalbup_rekapsuarawalbup_changelist')
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
