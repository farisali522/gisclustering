from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
import pandas as pd
import io
from core.models import Kecamatan, Partai
from core.services.data_service import ElectoralDataEngine
from pilpres.models import Koalisi as KoalisiPilpres
from pilgub.models import KoalisiGubernur
from pilwalbup.models import KoalisiWalbup

# ==============================================================================
# VIEW KONTROLER: DASHBOARD UTAMA
# ==============================================================================

@login_required(login_url='login')
def dashboard_view(request):
    """Menampilkan ringkasan (Overview) statistik pemilu di Dashboard Utama."""
    selected_party_id = request.GET.get('partai_utama')
    selected_party, kecamatan_data, recap_perc = ElectoralDataEngine(selected_party_id).run()
    
    # Metadata Koalisi untuk Legenda Paslon di Dashboard
    koalisi_pilpres = KoalisiPilpres.objects.filter(partai=selected_party).first()
    paslon_pilpres = koalisi_pilpres.paslon if koalisi_pilpres else None
    
    koalisi_pilgub = KoalisiGubernur.objects.filter(partai=selected_party).first()
    paslon_pilgub = koalisi_pilgub.paslon if koalisi_pilgub else None
    
    koalisi_walbup_qs = KoalisiWalbup.objects.filter(partai=selected_party).select_related('paslon', 'paslon__kab_kota')
    count_walbup = koalisi_walbup_qs.count()
    semua_paslon_walbup = [item.paslon for item in koalisi_walbup_qs]

    context = {
        'selected_party': selected_party,
        'recap_perc': recap_perc,
        'paslon_pilpres': paslon_pilpres,
        'paslon_pilgub': paslon_pilgub,
        'count_walbup': count_walbup,
        'semua_paslon_walbup': semua_paslon_walbup,
        'daftar_partai': Partai.objects.all().order_by('no_urut_partai')
    }
    return render(request, 'pages/dashboard.html', context)

# ==============================================================================
# VIEW KONTROLER: EKSPOR DATA MENTAH (Full Export)
# ==============================================================================

@login_required(login_url='login')
def export_dashboard_excel(request):
    """Mengekspor seluruh data mentah Pemilu & Pilkada ke dalam satu file Excel multi-sheet."""
    from collections import defaultdict
    from pilpres.models import DetailSuara as DSPilpres, RekapSuara as RSPilpres, Paslon as PaslonPilpres
    from pileg_ri.models import DetailSuaraPilegRI as DSPilegRI, RekapSuaraPilegRI as RSPilegRI
    from pileg_prov.models import DetailSuaraPilegProv as DSPilegProv, RekapSuaraPilegProv as RSPilegProv
    from pileg_kokab.models import DetailSuaraPilegKokab as DSPilegKokab, RekapSuaraPilegKokab as RSPilegKokab
    from pilgub.models import DetailSuaraGubernur as DSPilgub, RekapSuaraGubernur as RSPilgub, PaslonGubernur
    from pilwalbup.models import DetailSuaraWalbup as DSPilwalbup, RekapSuaraWalbup as RSPilwalbup, PaslonWalbup
    from django.db.models import Sum, Max

    # 1. Persiapan Data Dasar (Kecamatan)
    kecamatan_list = Kecamatan.objects.select_related('kab_kota', 'tps_pemilu', 'tps_pilkada').all().order_by('kab_kota__nama_kokab', 'nama_kecamatan')
    
    base_pemilu, base_pilkada = [], []
    for k in kecamatan_list:
        base_pemilu.append({
            'kecamatan_id': k.id, 'Kode Kecamatan': k.kode_kecamatan, 'Kabupaten/Kota': k.kab_kota.nama_kokab, 'Kecamatan': k.nama_kecamatan,
            'DPT': k.tps_pemilu.rekap_dpt_pemilu if hasattr(k, 'tps_pemilu') else 0,
            'TPS': k.tps_pemilu.rekap_tps_pemilu if hasattr(k, 'tps_pemilu') else 0,
        })
        base_pilkada.append({
            'kecamatan_id': k.id, 'Kode Kecamatan': k.kode_kecamatan, 'Kabupaten/Kota': k.kab_kota.nama_kokab, 'Kecamatan': k.nama_kecamatan,
            'DPT': k.tps_pilkada.rekap_dpt_pilkada if hasattr(k, 'tps_pilkada') else 0,
            'TPS': k.tps_pilkada.rekap_tps_pilkada if hasattr(k, 'tps_pilkada') else 0,
        })
        
    df_base_pemilu, df_base_pilkada = pd.DataFrame(base_pemilu), pd.DataFrame(base_pilkada)
    partais = Partai.objects.all().order_by('no_urut_partai')
    
    # 2. Helper untuk Membangun Sheet Pileg
    def build_pileg_df(DetailModel, RekapModel):
        if df_base_pemilu.empty: return pd.DataFrame()
        df = df_base_pemilu.copy()
        qs_detail = DetailModel.objects.values('kecamatan_id', 'partai__no_urut_partai', 'partai__nama_partai').annotate(total=Sum('jumlah_suara'))
        suara_dict = defaultdict(dict)
        for row in qs_detail: suara_dict[row['kecamatan_id']][f"{row['partai__no_urut_partai']}. {row['partai__nama_partai']}"] = row['total']
        ts_dict = {r['kecamatan_id']: r['total_suara_tidak_sah'] for r in RekapModel.objects.values('kecamatan_id', 'total_suara_tidak_sah')}
        
        for p in partais:
            c_name = f"{p.no_urut_partai}. {p.nama_partai}"
            df[c_name] = df['kecamatan_id'].map(lambda x: suara_dict.get(x, {}).get(c_name, 0))
            
        sah_dict = {r['kecamatan_id']: r['total'] for r in DetailModel.objects.values('kecamatan_id').annotate(total=Sum('jumlah_suara'))}
        df['Suara Sah'] = df['kecamatan_id'].map(lambda x: sah_dict.get(x, 0))
        df['Suara Tidak Sah'] = df['kecamatan_id'].map(lambda x: ts_dict.get(x, 0))
        df['Total Suara'] = df['Suara Sah'] + df['Suara Tidak Sah']
        return df.drop(columns=['kecamatan_id'])

    # 3. Helper untuk Membangun Sheet Pilpres/Pilgub
    def build_pilpres_gub_df(base_df, DetailModel, RekapModel, PaslonModel, is_pilpres=True):
        if base_df.empty: return pd.DataFrame()
        df = base_df.copy()
        paslons = PaslonModel.objects.all().order_by('no_urut_paslon')
        qs_detail = DetailModel.objects.values('kecamatan_id', 'paslon__no_urut_paslon').annotate(total=Sum('jumlah_suara'))
        suara_dict = defaultdict(dict)
        for row in qs_detail: suara_dict[row['kecamatan_id']][row['paslon__no_urut_paslon']] = row['total']
        ts_dict = {r['kecamatan_id']: r['total_suara_tidak_sah'] for r in RekapModel.objects.values('kecamatan_id', 'total_suara_tidak_sah')}
        
        for p in paslons:
            name = f"Paslon {p.no_urut_paslon} - {p.nama_capres if is_pilpres else p.nama_cagub}"
            df[name] = df['kecamatan_id'].map(lambda x: suara_dict.get(x, {}).get(p.no_urut_paslon, 0))
            
        sah_dict = {r['kecamatan_id']: r['total'] for r in DetailModel.objects.values('kecamatan_id').annotate(total=Sum('jumlah_suara'))}
        df['Suara Sah'] = df['kecamatan_id'].map(lambda x: sah_dict.get(x, 0))
        df['Suara Tidak Sah'] = df['kecamatan_id'].map(lambda x: ts_dict.get(x, 0))
        df['Total Suara'] = df['Suara Sah'] + df['Suara Tidak Sah']
        return df.drop(columns=['kecamatan_id'])
        
    # 4. Sheet Khusus Pilkada Kab/Kota (Pilwalbup)
    def build_walbup_df():
        if df_base_pilkada.empty: return pd.DataFrame()
        df = df_base_pilkada.copy()
        qs_detail = DSPilwalbup.objects.values('kecamatan_id', 'paslon__no_urut_paslon').annotate(total=Sum('jumlah_suara'))
        suara_dict = defaultdict(dict)
        for row in qs_detail: suara_dict[row['kecamatan_id']][f"Paslon {row['paslon__no_urut_paslon']}"] = row['total']
        ts_dict = {r['kecamatan_id']: r['total_suara_tidak_sah'] for r in RSPilwalbup.objects.values('kecamatan_id', 'total_suara_tidak_sah')}
        
        max_p = PaslonWalbup.objects.aggregate(m=Max('no_urut_paslon'))['m'] or 0
        for i in range(1, max_p + 1):
            df[f'Paslon {i}'] = df['kecamatan_id'].map(lambda x: suara_dict.get(x, {}).get(f"Paslon {i}", 0))
            
        sah_dict = {r['kecamatan_id']: r['total'] for r in DSPilwalbup.objects.values('kecamatan_id').annotate(total=Sum('jumlah_suara'))}
        df['Suara Sah'] = df['kecamatan_id'].map(lambda x: sah_dict.get(x, 0))
        df['Suara Tidak Sah'] = df['kecamatan_id'].map(lambda x: ts_dict.get(x, 0))
        df['Total Suara'] = df['Suara Sah'] + df['Suara Tidak Sah']
        return df.drop(columns=['kecamatan_id'])

    # 5. Kompilasi Semua Sheet
    dfs = {
        'Pilpres': build_pilpres_gub_df(df_base_pemilu, DSPilpres, RSPilpres, PaslonPilpres, True),
        'Pileg RI': build_pileg_df(DSPilegRI, RSPilegRI),
        'Pileg Prov': build_pileg_df(DSPilegProv, RSPilegProv),
        'Pileg Kokab': build_pileg_df(DSPilegKokab, RSPilegKokab),
        'Pilgub': build_pilpres_gub_df(df_base_pilkada, DSPilgub, RSPilgub, PaslonGubernur, False),
        'Pilwalbup': build_walbup_df(),
    }
    
    # 6. Menulis ke Stream Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in dfs.items():
            if df.empty: df = pd.DataFrame({'Data Kosong': []})
            df.to_excel(writer, index=False, sheet_name=sheet_name)
            worksheet = writer.sheets[sheet_name]
            # Auto-adjust column width
            for idx, col in enumerate(df.columns):
                col_letter = chr(65 + idx) if idx < 26 else chr(64 + idx//26) + chr(65 + idx%26)
                max_len = max(df[col].astype(str).map(len).max() if not df.empty else 0, len(str(col))) + 2
                worksheet.column_dimensions[col_letter].width = min(max_len, 35)
    output.seek(0)
    
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="Export_Data_Lengkap_Pemilu_Pilkada.xlsx"'
    return response
