from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, F, OuterRef, Subquery, IntegerField, Count
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
import pandas as pd
import io
import json
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, davies_bouldin_score

# Import model-model dari berbagai aplikasi pemilu
from pilpres.models import DetailSuara as DSPilpres, RekapSuara as RSPilpres, Koalisi as KoalisiPilpres
from pileg_ri.models import DetailSuaraPilegRI as DSPilegRI, RekapSuaraPilegRI as RSPilegRI
from pileg_prov.models import DetailSuaraPilegProv as DSPilegProv, RekapSuaraPilegProv as RSPilegProv
from pileg_kokab.models import DetailSuaraPilegKokab as DSPilegKokab, RekapSuaraPilegKokab as RSPilegKokab
from pilgub.models import DetailSuaraGubernur as DSPilgub, RekapSuaraGubernur as RSPilgub, KoalisiGubernur
from pilwalbup.models import DetailSuaraWalbup as DSPilwalbup, RekapSuaraWalbup as RSPilwalbup, KoalisiWalbup
from core.models import Kecamatan, Partai, HasilClustering

def landing_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'pages/landing.html')

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Username atau password salah.')
    
    return render(request, 'pages/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required(login_url='login')
@login_required(login_url='login')
def dashboard_view(request):
    selected_party_id = request.GET.get('partai_utama')
    selected_party, kecamatan_data, recap_perc = get_clustering_data(selected_party_id)
    
    # Coalition data same as clustering view for consistency
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

@login_required(login_url='login')
def export_dashboard_excel(request):
    from collections import defaultdict
    from pilpres.models import Paslon as PaslonPilpres
    from pilgub.models import PaslonGubernur
    from pilwalbup.models import PaslonWalbup
    from django.db.models import Max

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

    dfs = {
        'Pilpres': build_pilpres_gub_df(df_base_pemilu, DSPilpres, RSPilpres, PaslonPilpres, True),
        'Pileg RI': build_pileg_df(DSPilegRI, RSPilegRI),
        'Pileg Prov': build_pileg_df(DSPilegProv, RSPilegProv),
        'Pileg Kokab': build_pileg_df(DSPilegKokab, RSPilegKokab),
        'Pilgub': build_pilpres_gub_df(df_base_pilkada, DSPilgub, RSPilgub, PaslonGubernur, False),
        'Pilwalbup': build_walbup_df(),
    }
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in dfs.items():
            if df.empty: df = pd.DataFrame({'Data Kosong': []})
            df.to_excel(writer, index=False, sheet_name=sheet_name)
            worksheet = writer.sheets[sheet_name]
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

# Helper untuk mendapatkan data clustering (12 parameter)
def get_clustering_data(party_id=None):
    # Memungkinkan pemilihan partai (Default: Gerindra No Urut 2)
    main_party = None
    if party_id:
        try:
            main_party = Partai.objects.get(id=party_id)
        except (Partai.DoesNotExist, ValueError):
            pass
            
    if not main_party:
        main_party = Partai.objects.get(no_urut_partai=2)

    # Koalisi Logic
    koalisi_pilpres = KoalisiPilpres.objects.filter(partai=main_party).first()
    paslon_pilpres_id = koalisi_pilpres.paslon_id if koalisi_pilpres else None
    
    koalisi_pilgub = KoalisiGubernur.objects.filter(partai=main_party).first()
    paslon_pilgub_id = koalisi_pilgub.paslon_id if koalisi_pilgub else None
    
    koalisi_pilwalbup = KoalisiWalbup.objects.filter(partai=main_party).values('kab_kota_id', 'paslon_id')
    walbup_map = {item['kab_kota_id']: item['paslon_id'] for item in koalisi_pilwalbup}

    def get_sah_subquery(model):
        return Subquery(
            model.objects.filter(kecamatan=OuterRef('pk'))
            .values('kecamatan')
            .annotate(total=Sum('jumlah_suara'))
            .values('total'),
            output_field=IntegerField()
        )

    def get_party_votes_subquery(model, party_id):
        if not party_id: return Coalesce(0, 0)
        return Subquery(
            model.objects.filter(kecamatan=OuterRef('pk'), partai_id=party_id)
            .values('kecamatan')
            .annotate(total=Sum('jumlah_suara'))
            .values('total'),
            output_field=IntegerField()
        )

    def get_paslon_votes_subquery(model, paslon_id):
        if not paslon_id: return Coalesce(0, 0)
        return Subquery(
            model.objects.filter(kecamatan=OuterRef('pk'), paslon_id=paslon_id)
            .values('kecamatan')
            .annotate(total=Sum('jumlah_suara'))
            .values('total'),
            output_field=IntegerField()
        )

    raw_data = Kecamatan.objects.select_related('kab_kota', 'tps_pemilu', 'tps_pilkada').annotate(
        perf_pilpres_votes=Coalesce(get_paslon_votes_subquery(DSPilpres, paslon_pilpres_id), 0),
        perf_pilpres_sah=Coalesce(get_sah_subquery(DSPilpres), 0),
        perf_ri_votes=Coalesce(get_party_votes_subquery(DSPilegRI, main_party.id if main_party else None), 0),
        perf_ri_sah=Coalesce(get_sah_subquery(DSPilegRI), 0),
        perf_prov_votes=Coalesce(get_party_votes_subquery(DSPilegProv, main_party.id if main_party else None), 0),
        perf_prov_sah=Coalesce(get_sah_subquery(DSPilegProv), 0),
        perf_kokab_votes=Coalesce(get_party_votes_subquery(DSPilegKokab, main_party.id if main_party else None), 0),
        perf_kokab_sah=Coalesce(get_sah_subquery(DSPilegKokab), 0),
        perf_pilgub_votes=Coalesce(get_paslon_votes_subquery(DSPilgub, paslon_pilgub_id), 0),
        perf_pilgub_sah=Coalesce(get_sah_subquery(DSPilgub), 0),
        perf_walbup_sah=Coalesce(get_sah_subquery(DSPilwalbup), 0),
        part_pilpres_sah=Coalesce(get_sah_subquery(DSPilpres), 0),
        part_pilpres_tdk_sah=Coalesce(F('rekap_pilpres__total_suara_tidak_sah'), 0),
        part_pilpres_dpt=Coalesce(F('tps_pemilu__rekap_dpt_pemilu'), 1),
        part_ri_sah=Coalesce(get_sah_subquery(DSPilegRI), 0),
        part_ri_tdk_sah=Coalesce(F('rekap_pileg_ri__total_suara_tidak_sah'), 0),
        part_prov_sah=Coalesce(get_sah_subquery(DSPilegProv), 0),
        part_prov_tdk_sah=Coalesce(F('rekap_pileg_prov__total_suara_tidak_sah'), 0),
        part_kokab_sah=Coalesce(get_sah_subquery(DSPilegKokab), 0),
        part_kokab_tdk_sah=Coalesce(F('rekap_pileg_kokab__total_suara_tidak_sah'), 0),
        part_pilgub_sah=Coalesce(get_sah_subquery(DSPilgub), 0),
        part_pilgub_tdk_sah=Coalesce(F('rekap_pilgub__total_suara_tidak_sah'), 0),
        part_pilgub_dpt=Coalesce(F('tps_pilkada__rekap_dpt_pilkada'), 1),
        part_walbup_sah=Coalesce(get_sah_subquery(DSPilwalbup), 0),
        part_walbup_tdk_sah=Coalesce(F('rekap_pilwalbup__total_suara_tidak_sah'), 0),
        tps_pemilu_count=Coalesce(F('tps_pemilu__rekap_tps_pemilu'), 0),
        dpt_pemilu_count=Coalesce(F('tps_pemilu__rekap_dpt_pemilu'), 0),
        tps_pilkada_count=Coalesce(F('tps_pilkada__rekap_tps_pilkada'), 0),
        dpt_pilkada_count=Coalesce(F('tps_pilkada__rekap_dpt_pilkada'), 0),
    ).order_by('kab_kota__nama_kokab', 'nama_kecamatan')
    
    # Hitung Jumlah Paslon per Kabupaten (n_paslon_pilkada_kokab)
    # Kotak kosong tidak dihitung sebagai paslon (sesuai permintaan user)
    from pilwalbup.models import PaslonWalbup
    paslon_counts = {
        item['kab_kota_id']: item['count'] 
        for item in PaslonWalbup.objects.exclude(nama_calon__icontains='KOTAK KOSONG').values('kab_kota_id').annotate(count=Count('id'))
    }

    kecamatan_data = []
    for k in raw_data:
        target_paslon_walbup = walbup_map.get(k.kab_kota_id)
        perf_walbup_votes = 0
        if target_paslon_walbup:
            perf_walbup_votes = DSPilwalbup.objects.filter(kecamatan=k, paslon_id=target_paslon_walbup).aggregate(Sum('jumlah_suara'))['jumlah_suara__sum'] or 0

        # Parameter ke-13: Jumlah Paslon di Kabupaten tersebut
        n_paslon = paslon_counts.get(k.kab_kota_id, 0)

        data = {
            'id': k.id,
            'kode': k.kode_kecamatan,
            'kab_kota': k.kab_kota.nama_kokab,
            'kecamatan': k.nama_kecamatan,
            'perf_pilpres': round((k.perf_pilpres_votes / k.perf_pilpres_sah) * 100, 2) if k.perf_pilpres_sah > 0 else 0,
            'perf_ri': round((k.perf_ri_votes / k.perf_ri_sah) * 100, 2) if k.perf_ri_sah > 0 else 0,
            'perf_prov': round((k.perf_prov_votes / k.perf_prov_sah) * 100, 2) if k.perf_prov_sah > 0 else 0,
            'perf_kokab': round((k.perf_kokab_votes / k.perf_kokab_sah) * 100, 2) if k.perf_kokab_sah > 0 else 0,
            'perf_pilgub': round((k.perf_pilgub_votes / k.perf_pilgub_sah) * 100, 2) if k.perf_pilgub_sah > 0 else 0,
            'perf_walbup': round((perf_walbup_votes / k.perf_walbup_sah) * 100, 2) if k.perf_walbup_sah > 0 else 0,
            'part_pilpres': round(((k.part_pilpres_sah + k.part_pilpres_tdk_sah) / k.part_pilpres_dpt) * 100, 2) if k.part_pilpres_dpt > 0 else 0,
            'part_ri': round(((k.part_ri_sah + k.part_ri_tdk_sah) / k.part_pilpres_dpt) * 100, 2) if k.part_pilpres_dpt > 0 else 0,
            'part_prov': round(((k.part_prov_sah + k.part_prov_tdk_sah) / k.part_pilpres_dpt) * 100, 2) if k.part_pilpres_dpt > 0 else 0,
            'part_kokab': round(((k.part_kokab_sah + k.part_kokab_tdk_sah) / k.part_pilpres_dpt) * 100, 2) if k.part_pilpres_dpt > 0 else 0,
            'part_pilgub': round(((k.part_pilgub_sah + k.part_pilgub_tdk_sah) / k.part_pilgub_dpt) * 100, 2) if k.part_pilgub_dpt > 0 else 0,
            'part_walbup': round(((k.part_walbup_sah + k.part_walbup_tdk_sah) / k.part_pilgub_dpt) * 100, 2) if k.part_pilgub_dpt > 0 else 0,
            'n_paslon_pilkada_kokab': round((1 / n_paslon) * 100, 2) if n_paslon > 0 else 0,
            'raw': {
                'pilpres_votes': k.perf_pilpres_votes,
                'pilpres_sah': k.perf_pilpres_sah,
                'pilpres_tsah': k.part_pilpres_tdk_sah,
                'ri_votes': k.perf_ri_votes,
                'ri_sah': k.perf_ri_sah,
                'ri_tsah': k.part_ri_tdk_sah,
                'prov_votes': k.perf_prov_votes,
                'prov_sah': k.perf_prov_sah,
                'prov_tsah': k.part_prov_tdk_sah,
                'kokab_votes': k.perf_kokab_votes,
                'kokab_sah': k.perf_kokab_sah,
                'kokab_tsah': k.part_kokab_tdk_sah,
                'pilgub_votes': k.perf_pilgub_votes,
                'pilgub_sah': k.perf_pilgub_sah,
                'pilgub_tsah': k.part_pilgub_tdk_sah,
                'walbup_votes': perf_walbup_votes,
                'walbup_sah': k.perf_walbup_sah,
                'walbup_tsah': k.part_walbup_tdk_sah,
                'tps_pemilu': k.tps_pemilu_count,
                'dpt_pemilu': k.dpt_pemilu_count,
                'tps_pilkada': k.tps_pilkada_count,
                'dpt_pilkada': k.dpt_pilkada_count,
            }
        }
        kecamatan_data.append(data)
    
    # Hitung Recap Persentase (Weighted Average) untuk 6 Parameter Performa
    total_votes_agg = {
        'pilpres': sum(k.perf_pilpres_votes for k in raw_data),
        'ri': sum(k.perf_ri_votes for k in raw_data),
        'prov': sum(k.perf_prov_votes for k in raw_data),
        'kokab': sum(k.perf_kokab_votes for k in raw_data),
        'pilgub': sum(k.perf_pilgub_votes for k in raw_data),
        'walbup': 0
    }
    total_sah_agg = {
        'pilpres': sum(k.perf_pilpres_sah for k in raw_data),
        'ri': sum(k.perf_ri_sah for k in raw_data),
        'prov': sum(k.perf_prov_sah for k in raw_data),
        'kokab': sum(k.perf_kokab_sah for k in raw_data),
        'pilgub': sum(k.perf_pilgub_sah for k in raw_data),
        'walbup': sum(k.perf_walbup_sah for k in raw_data)
    }

    # Hitung manual total walbup votes untuk recap
    for k in raw_data:
        target_paslon_walbup = walbup_map.get(k.kab_kota_id)
        if target_paslon_walbup:
            v = DSPilwalbup.objects.filter(kecamatan=k, paslon_id=target_paslon_walbup).aggregate(Sum('jumlah_suara'))['jumlah_suara__sum'] or 0
            total_votes_agg['walbup'] += v

    recap_perc = {
        'pilpres': round((total_votes_agg['pilpres'] / total_sah_agg['pilpres'] * 100), 2) if total_sah_agg['pilpres'] > 0 else 0,
        'ri': round((total_votes_agg['ri'] / total_sah_agg['ri'] * 100), 2) if total_sah_agg['ri'] > 0 else 0,
        'prov': round((total_votes_agg['prov'] / total_sah_agg['prov'] * 100), 2) if total_sah_agg['prov'] > 0 else 0,
        'kokab': round((total_votes_agg['kokab'] / total_sah_agg['kokab'] * 100), 2) if total_sah_agg['kokab'] > 0 else 0,
        'pilgub': round((total_votes_agg['pilgub'] / total_sah_agg['pilgub'] * 100), 2) if total_sah_agg['pilgub'] > 0 else 0,
        'walbup': round((total_votes_agg['walbup'] / total_sah_agg['walbup'] * 100), 2) if total_sah_agg['walbup'] > 0 else 0,
    }
    
    return main_party, kecamatan_data, recap_perc

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

@login_required(login_url='login')
def clustering_atribut_view(request):
    if not request.user.is_superuser:
        messages.warning(request, "Akses ditolak. Hanya Admin yang dapat melihat detail atribut clustering.")
        return redirect('dashboard')
        
    selected_party_id = request.GET.get('partai_utama') or request.POST.get('partai_utama')
    main_party, kecamatan_data, recap_perc = get_clustering_data(selected_party_id)

    # Data tambahan untuk UI
    koalisi_pilpres = KoalisiPilpres.objects.filter(partai=main_party).first()
    paslon_pilpres = koalisi_pilpres.paslon if koalisi_pilpres else None
    koalisi_pilgub = KoalisiGubernur.objects.filter(partai=main_party).first()
    paslon_pilgub = koalisi_pilgub.paslon if koalisi_pilgub else None
    koalisi_walbup_qs = KoalisiWalbup.objects.filter(partai=main_party).select_related('paslon', 'paslon__kab_kota')
    count_walbup = koalisi_walbup_qs.count()
    semua_paslon_walbup = [item.paslon for item in koalisi_walbup_qs]

    # Pagination Logic
    show_all = request.GET.get('show_all') == 'true'
    page = request.GET.get('page', 1)
    
    if show_all:
        page_obj = kecamatan_data
    else:
        paginator = Paginator(kecamatan_data, 20)
        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

    context = {
        'kecamatan_data': page_obj,
        'selected_party': main_party,
        'paslon_pilpres': paslon_pilpres,
        'paslon_pilgub': paslon_pilgub,
        'count_walbup': count_walbup,
        'semua_paslon_walbup': semua_paslon_walbup,
        'total_kecamatan': len(kecamatan_data),
        'recap_perc': recap_perc,
        'daftar_partai': Partai.objects.all().order_by('no_urut_partai'),
        'is_paginated': not show_all,
        'show_all': show_all,
    }
    return render(request, 'modules/clustering_atribut.html', context)

@login_required(login_url='login')
def export_clustering_excel(request):
    if not request.user.is_superuser:
        return redirect('dashboard')
        
    selected_party_id = request.GET.get('partai_utama')
    main_party, data, recap = get_clustering_data(selected_party_id)
    
    # Ambil list kolom dari mapping untuk filter data (buang 'id' dan 'raw')
    column_mapping = {
        'kode': 'Kode', 'kab_kota': 'Kabupaten/Kota', 'kecamatan': 'Kecamatan',
        'perf_pilpres': 'Perf Pilpres (%)', 'perf_ri': 'Perf RI (%)', 'perf_prov': 'Perf Prov (%)',
        'perf_kokab': 'Perf Kokab (%)', 'perf_pilgub': 'Perf Pilgub (%)', 'perf_walbup': 'Perf Walbup (%)',
        'part_pilpres': 'Part Pilpres (%)', 'part_ri': 'Part RI (%)', 'part_prov': 'Part Prov (%)',
        'part_kokab': 'Part Kokab (%)', 'part_pilgub': 'Part Pilgub (%)', 'part_walbup': 'Part Walbup (%)',
        'n_paslon_pilkada_kokab': 'Ratio Dukungan Paslon (%)'
    }
    
    df = pd.DataFrame(data)
    
    # Filter hanya kolom yang didefinisikan di mapping (membuang 'id' dan kolom 'raw' yang berisi dictionary)
    cols_to_export = list(column_mapping.keys())
    df = df[cols_to_export]
    
    # Rename columns for excel
    df = df.rename(columns=column_mapping)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data Clustering')
    
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="clustering_{main_party.nama_partai}.xlsx"'
    return response

@login_required
def zscore_normalization_view(request):
    if not request.user.is_superuser:
        messages.warning(request, "Akses ditolak. Halaman ini hanya untuk keperluan teknis Admin.")
        return redirect('dashboard')
        
    """
    Diagnostic view to show standardized (Z-Score) values.
    Helpful for understanding how data is transformed before clustering.
    """
    main_party, kecamatan_data, extra_context = get_clustering_data()
    
    attributes = [
        'perf_pilpres', 'perf_ri', 'perf_prov', 'perf_kokab', 'perf_pilgub', 'perf_walbup',
        'part_pilpres', 'part_ri', 'part_prov', 'part_kokab', 'part_pilgub', 'part_walbup',
        'n_paslon_pilkada_kokab'
    ]
    
    df = pd.DataFrame(kecamatan_data)
    zscore_data = []
    
    if not df.empty:
        X = df[attributes]
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Add scaled values to the dictionary records
        scaled_df = pd.DataFrame(X_scaled, columns=[f'z_{attr}' for attr in attributes])
        full_df = pd.concat([df, scaled_df], axis=1)
        zscore_data = full_df.to_dict('records')

    context = {
        'page_title': 'Transparansi Normalisasi Z-Score',
        'zscore_data': zscore_data,
        'selected_party': main_party,
        'attributes': attributes,
        'active_menu': 'zscore-normalization'
    }
    return render(request, 'modules/zscore_data.html', context)

@login_required(login_url='login')
def export_zscore_excel(request):
    if not request.user.is_superuser:
        return redirect('dashboard')
        
    selected_party_id = request.GET.get('partai_utama')
    main_party, kecamatan_data, extra = get_clustering_data(selected_party_id)
    
    attributes = [
        'perf_pilpres', 'perf_ri', 'perf_prov', 'perf_kokab', 'perf_pilgub', 'perf_walbup',
        'part_pilpres', 'part_ri', 'part_prov', 'part_kokab', 'part_pilgub', 'part_walbup',
        'n_paslon_pilkada_kokab'
    ]
    
    df = pd.DataFrame(kecamatan_data)
    if not df.empty:
        X = df[attributes]
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Create scaled column names
        scaled_cols = [f'Z {attr.replace("_", " ").title()}' for attr in attributes]
        scaled_df = pd.DataFrame(X_scaled, columns=scaled_cols)
        
        # Combine with basic info
        info_df = df[['kode', 'kab_kota', 'kecamatan']]
        info_df.columns = ['Kode', 'Kabupaten/Kota', 'Kecamatan']
        
        final_df = pd.concat([info_df, scaled_df], axis=1)
    else:
        final_df = pd.DataFrame(columns=['Kode', 'Kabupaten/Kota', 'Kecamatan'] + attributes)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        final_df.to_excel(writer, index=False, sheet_name='Z-Score Analysis')
    
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="zscore_{main_party.nama_partai}.xlsx"'
    return response

@login_required(login_url='login')
def clustering_validation_view(request):
    if not request.user.is_superuser:
        messages.warning(request, "Akses ditolak. Validasi permodelan hanya dapat diakses oleh Admin.")
        return redirect('dashboard')
        
    """
    Tahap 4 CRISP-DM: Modeling (Validasi K-Optimal)
    Menghitung SSE, Silhouette Score, and DBI untuk mencari nilai K terbaik.
    """
    selected_party_id = request.GET.get('partai_utama')
    main_party, kecamatan_data, extra = get_clustering_data(selected_party_id)
    
    attributes = [
        'perf_pilpres', 'perf_ri', 'perf_prov', 'perf_kokab', 'perf_pilgub', 'perf_walbup',
        'part_pilpres', 'part_ri', 'part_prov', 'part_kokab', 'part_pilgub', 'part_walbup',
        'n_paslon_pilkada_kokab'
    ]
    
    df = pd.DataFrame(kecamatan_data)
    validation_results = []
    
    if not df.empty:
        # Preparation
        X = df[attributes]
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Modeling & Validation Loop
        for k in range(2, 11):
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(X_scaled)
            
            validation_results.append({
                'k': k,
                'sse': kmeans.inertia_,
                'silhouette': silhouette_score(X_scaled, labels),
                'dbi': davies_bouldin_score(X_scaled, labels)
            })
            
        # Tandai skor terbaik (Ranking)
        if validation_results:
            # Sort for Silhouette (Descending)
            silh_desc = sorted(validation_results, key=lambda x: x['silhouette'], reverse=True)
            # Sort for DBI (Ascending)
            dbi_asc = sorted(validation_results, key=lambda x: x['dbi'])
            
            # Elbow Point (Secant-Line Distance)
            p1 = (validation_results[0]['k'], validation_results[0]['sse'])
            pn = (validation_results[-1]['k'], validation_results[-1]['sse'])
            A = p1[1] - pn[1]
            B = pn[0] - p1[0]
            C = p1[0]*pn[1] - pn[0]*p1[1]
            sqrt_ab = (A**2 + B**2)**0.5
            
            max_dist = -1
            elbow_k = 5
            for r in validation_results:
                dist = abs(A*r['k'] + B*r['sse'] + C) / sqrt_ab
                if dist > max_dist:
                    max_dist = dist
                    elbow_k = r['k']
            
            for r in validation_results:
                # Rank Silhouette
                r['rank_silhouette'] = next((i + 1 for i, s in enumerate(silh_desc) if s['k'] == r['k']), 99)
                r['is_top3_silhouette'] = (r['rank_silhouette'] <= 3)
                
                # Rank DBI
                r['rank_dbi'] = next((i + 1 for i, d in enumerate(dbi_asc) if d['k'] == r['k']), 99)
                r['is_top2_dbi'] = (r['rank_dbi'] <= 2)
                
                r['is_elbow'] = (r['k'] == elbow_k)

    context = {
        'page_title': 'Validasi Modeling (K-Optimal)',
        'results': validation_results,
        'results_json': validation_results,
        'selected_party': main_party,
        'active_menu': 'clustering-validation'
    }
    return render(request, 'modules/clustering_validation.html', context)

@login_required(login_url='login')
def clustering_results_view(request):
    if not request.user.is_superuser:
        messages.warning(request, "Akses ditolak. Hasil klasterisasi bersifat terbatas.")
        return redirect('dashboard')
        
    """
    Tahap 5-6 CRISP-DM: Evaluation & Deployment
    Menjalankan K-Means final, menyimpan label ke DB, dan menyiapkan PCA + Heatmap.
    """
    # Deteksi K langsung dari Database jika parameter URL kosong
    k_param = request.GET.get('k')
    if k_param:
        k_final = int(k_param)
    else:
        # Cek jumlah cluster unik yang sudah tersimpan di DB
        k_from_db = HasilClustering.objects.values('label_cluster').distinct().count()
        k_final = k_from_db if k_from_db > 0 else 5

    selected_party_id = request.GET.get('partai_utama')
    main_party, kecamatan_data, extra = get_clustering_data(selected_party_id)

    attributes = [
        'perf_pilpres', 'perf_ri', 'perf_prov', 'perf_kokab', 'perf_pilgub', 'perf_walbup',
        'part_pilpres', 'part_ri', 'part_prov', 'part_kokab', 'part_pilgub', 'part_walbup',
        'n_paslon_pilkada_kokab'
    ]
    attr_labels = [
        'Perf Pres', 'Perf RI', 'Perf Prov', 'Perf Kab', 'Perf Gub', 'Perf Wkt',
        'Part Pres', 'Part RI', 'Part Prov', 'Part Kab', 'Part Gub', 'Part Wkt',
        'Ratio Duk'
    ]

    df = pd.DataFrame(kecamatan_data)
    pca_data = []
    centroid_data = []
    result_rows = []

    if not df.empty:
        X = df[attributes]
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # K-Means Final
        kmeans = KMeans(n_clusters=k_final, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)
        df['cluster_label'] = labels

        # Simpan ke Database (update_or_create)
        for _, row in df.iterrows():
            HasilClustering.objects.update_or_create(
                kecamatan_id=int(row['id']),
                defaults={'label_cluster': int(row['cluster_label'])}
            )

        # Legend Mapping (Berdasarkan Hasil Penelitian User)
        cluster_info = {
            0: {'name': 'Klaster Karakteristik Khusus', 'color': '#6366f1'},
            1: {'name': 'Klaster Pertumbuhan Kritis', 'color': '#ef4444'},
            2: {'name': 'Klaster Partisipasi Aktif', 'color': '#10b981'},
            3: {'name': 'Klaster Urban Dinamis', 'color': '#3b82f6'},
            4: {'name': 'Klaster Performa Konsisten', 'color': '#eab308'}
        }

        # PCA 2D untuk Scatter Plot
        pca = PCA(n_components=2)
        X_pca = pca.fit_transform(X_scaled)
        acc_pca = round(sum(pca.explained_variance_ratio_) * 100, 2)

        for i in range(len(df)):
            cid = int(labels[i])
            c_style = cluster_info.get(cid, {'name': f'Klaster {cid}', 'color': '#94a3b8'})
            pca_data.append({
                'x': round(float(X_pca[i][0]), 4),
                'y': round(float(X_pca[i][1]), 4),
                'label': cid,
                'name': df.iloc[i]['kecamatan'],
                'kab': df.iloc[i]['kab_kota'],
                'cluster_name': c_style['name'],
                'color': c_style['color']
            })

        # Centroid Profiling
        for c in range(k_final):
            cluster_df = df[df['cluster_label'] == c]
            means = cluster_df[attributes].mean().round(2).tolist()
            c_style = cluster_info.get(c, {'name': f'Klaster {c}', 'color': '#94a3b8'})
            centroid_data.append({
                'cluster': c,
                'name': c_style['name'],
                'color': c_style['color'],
                'count': len(cluster_df),
                'means': means
            })

        # Tabel Hasil
        for _, row in df.iterrows():
            cid = int(row['cluster_label'])
            c_style = cluster_info.get(cid, {'name': f'Klaster {cid}', 'color': '#94a3b8'})
            result_rows.append({
                'kode': row['kode'],
                'kab_kota': row['kab_kota'],
                'kecamatan': row['kecamatan'],
                'cluster': cid,
                'cluster_name': c_style['name'],
                'color': c_style['color']
            })

    context = {
        'page_title': 'Hasil Cluster',
        'result_rows': result_rows,
        'result_rows_json': result_rows,
        'pca_data': pca_data,
        'centroid_data': centroid_data,
        'attr_labels': attr_labels,
        'attr_labels_list': attr_labels,
        'k_final': k_final,
        'acc_pca': acc_pca if not df.empty else 0,
        'selected_party': main_party,
        'k_range': range(2, 11),
        'k_final_for_export': k_final,
    }
    return render(request, 'modules/clustering_results.html', context)

@login_required(login_url='login')
def export_clustering_results_excel(request):
    if not request.user.is_superuser:
        return redirect('dashboard')
        
    """Export tabel Hasil Cluster (dengan Kode Kecamatan dan Label Klaster) ke Excel."""
    selected_party_id = request.GET.get('partai_utama')
    k_final = int(request.GET.get('k', 5))
    main_party, kecamatan_data, _ = get_clustering_data(selected_party_id)

    attributes = [
        'perf_pilpres', 'perf_ri', 'perf_prov', 'perf_kokab', 'perf_pilgub', 'perf_walbup',
        'part_pilpres', 'part_ri', 'part_prov', 'part_kokab', 'part_pilgub', 'part_walbup',
        'n_paslon_pilkada_kokab'
    ]
    df = pd.DataFrame(kecamatan_data)
    if df.empty:
        return HttpResponse('Data tidak tersedia.', status=404)

    X_scaled = StandardScaler().fit_transform(df[attributes])
    labels = KMeans(n_clusters=k_final, random_state=42, n_init=10).fit_predict(X_scaled)
    df['Label Klaster'] = labels

    output_df = df[['kode', 'kab_kota', 'kecamatan', 'Label Klaster']].copy()
    output_df.columns = ['Kode Kecamatan', 'Kab/Kota', 'Nama Kecamatan', 'Label Klaster']
    output_df = output_df.sort_values(['Label Klaster', 'Kab/Kota', 'Nama Kecamatan'])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        output_df.to_excel(writer, index=False, sheet_name=f'Hasil_K{k_final}')
    output.seek(0)

    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="hasil_cluster_K{k_final}_{main_party.nama_partai}.xlsx"'
    return response

@login_required(login_url='login')
def clustering_gis_view(request):
    from geojson.models import KabupatenGeoJSON
    from collections import defaultdict
    from pilpres.models import Koalisi as KoalisiPilpres
    from pilgub.models import KoalisiGubernur
    from pilwalbup.models import KoalisiWalbup

    selected_party_id = request.GET.get('partai_utama')
    main_party, kecamatan_data, _ = get_clustering_data(selected_party_id)

    paslon_pilpres_id = KoalisiPilpres.objects.filter(partai=main_party).values_list('paslon_id', flat=True).first()
    paslon_pilgub_id = KoalisiGubernur.objects.filter(partai=main_party).values_list('paslon_id', flat=True).first()
    walbup_paslon_ids = list(KoalisiWalbup.objects.filter(partai=main_party).values_list('paslon_id', flat=True))
    
    koalisi_pilpres = KoalisiPilpres.objects.filter(partai=main_party).select_related('paslon').first()
    paslon_pilpres = koalisi_pilpres.paslon if koalisi_pilpres else None
    koalisi_pilgub = KoalisiGubernur.objects.filter(partai=main_party).select_related('paslon').first()
    paslon_pilgub = koalisi_pilgub.paslon if koalisi_pilgub else None
    
    walbup_koalisi = KoalisiWalbup.objects.filter(partai=main_party).select_related('paslon', 'paslon__kab_kota')
    walbup_names = {k.paslon.kab_kota.nama_kokab: f"{k.paslon.nama_calon} - {k.paslon.nama_wakil}" for k in walbup_koalisi}
    walbup_fotos = {k.paslon.kab_kota.nama_kokab: f"/media/{k.paslon.foto_paslon}" if k.paslon.foto_paslon else "" for k in walbup_koalisi}

    names_info = {
        'pilpres': f"{paslon_pilpres.nama_capres} - {paslon_pilpres.nama_cawapres}" if paslon_pilpres else "Tidak Ada Paslon",
        'pilpres_foto': f"/media/{paslon_pilpres.foto_paslon}" if paslon_pilpres and paslon_pilpres.foto_paslon else "",
        'pilgub': f"{paslon_pilgub.nama_cagub} - {paslon_pilgub.nama_cawagub}" if paslon_pilgub else "Tidak Ada Paslon",
        'pilgub_foto': f"/media/{paslon_pilgub.foto_paslon}" if paslon_pilgub and paslon_pilgub.foto_paslon else "",
        'partai': main_party.nama_partai,
        'partai_logo': f"/media/{main_party.logo_partai}" if main_party.logo_partai else "",
        'walbup': walbup_names,
        'walbup_foto': walbup_fotos,
        'warna': main_party.warna_partai or '#1e3a8a'
    }

    kec_stats_by_kode = {d['kode']: d for d in kecamatan_data}
    kokab_stats_12 = {}
    kokab_groups = defaultdict(list)
    for d in kecamatan_data:
        kokab_groups[d['kab_kota']].append(d)
        
    for kab, items in kokab_groups.items():
        kokab_stats_12[kab] = {
            'perf_pilpres': sum(i['perf_pilpres'] for i in items) / len(items) if items else 0,
            'perf_ri': sum(i['perf_ri'] for i in items) / len(items) if items else 0,
            'perf_prov': sum(i['perf_prov'] for i in items) / len(items) if items else 0,
            'perf_kokab': sum(i['perf_kokab'] for i in items) / len(items) if items else 0,
            'perf_pilgub': sum(i['perf_pilgub'] for i in items) / len(items) if items else 0,
            'perf_walbup': sum(i['perf_walbup'] for i in items) / len(items) if items else 0,
            'part_pilpres': sum(i['part_pilpres'] for i in items) / len(items) if items else 0,
            'part_ri': sum(i['part_ri'] for i in items) / len(items) if items else 0,
            'part_prov': sum(i['part_prov'] for i in items) / len(items) if items else 0,
            'part_kokab': sum(i['part_kokab'] for i in items) / len(items) if items else 0,
            'part_pilgub': sum(i['part_pilgub'] for i in items) / len(items) if items else 0,
            'part_walbup': sum(i['part_walbup'] for i in items) / len(items) if items else 0,
        }

    # === ENGINE REKAPITULASI LEVEL DEWA ===
    def new_stats():
        return {
            'pilpres': {'sah': 0, 'tsah': 0, 'tot': 0, 'items': {}},
            'ri': {'sah': 0, 'tsah': 0, 'tot': 0, 'items': {}},
            'prov': {'sah': 0, 'tsah': 0, 'tot': 0, 'items': {}},
            'kokab': {'sah': 0, 'tsah': 0, 'tot': 0, 'items': {}},
            'pilgub': {'sah': 0, 'tsah': 0, 'tot': 0, 'items': {}},
            'walbup': {'sah': 0, 'tsah': 0, 'tot': 0, 'items': {}},
        }
    
    global_s = new_stats()
    kokab_s = defaultdict(new_stats)
    kec_s = defaultdict(new_stats)
    meta_dict = defaultdict(dict)

    def add_stats(level_key, k_kode, k_kab, item_id, votes, meta):
        kec_s[k_kode][level_key]['items'][item_id] = kec_s[k_kode][level_key]['items'].get(item_id, 0) + votes
        kokab_s[k_kab][level_key]['items'][item_id] = kokab_s[k_kab][level_key]['items'].get(item_id, 0) + votes
        global_s[level_key]['items'][item_id] = global_s[level_key]['items'].get(item_id, 0) + votes
        meta_dict[level_key][item_id] = meta

    # 1. Ekstrak Suara Paslon Pilpres & Pilkada
    for r in DSPilpres.objects.values('kecamatan__kode_kecamatan', 'kecamatan__kab_kota__nama_kokab', 'paslon_id', 'paslon__no_urut_paslon', 'paslon__nama_capres', 'paslon__nama_cawapres', 'paslon__foto_paslon').annotate(votes=Sum('jumlah_suara')):
        if not r['paslon_id']: continue
        foto_url = f"/media/{r['paslon__foto_paslon']}" if r['paslon__foto_paslon'] else ""
        is_main = (r['paslon_id'] == paslon_pilpres_id)
        add_stats('pilpres', r['kecamatan__kode_kecamatan'], r['kecamatan__kab_kota__nama_kokab'], r['paslon_id'], r['votes'] or 0, {
            'no': r['paslon__no_urut_paslon'], 'nama': f"{r['paslon__nama_capres']} - {r['paslon__nama_cawapres']}", 'warna': '#1e3a8a',
            'foto': foto_url, 'is_main': is_main
        })
    for r in DSPilgub.objects.values('kecamatan__kode_kecamatan', 'kecamatan__kab_kota__nama_kokab', 'paslon_id', 'paslon__no_urut_paslon', 'paslon__nama_cagub', 'paslon__nama_cawagub', 'paslon__foto_paslon').annotate(votes=Sum('jumlah_suara')):
        if not r['paslon_id']: continue
        foto_url = f"/media/{r['paslon__foto_paslon']}" if r['paslon__foto_paslon'] else ""
        is_main = (r['paslon_id'] == paslon_pilgub_id)
        add_stats('pilgub', r['kecamatan__kode_kecamatan'], r['kecamatan__kab_kota__nama_kokab'], r['paslon_id'], r['votes'] or 0, {
            'no': r['paslon__no_urut_paslon'], 'nama': f"{r['paslon__nama_cagub']} - {r['paslon__nama_cawagub']}", 'warna': '#1e3a8a',
            'foto': foto_url, 'is_main': is_main
        })
    for r in DSPilwalbup.objects.values('kecamatan__kode_kecamatan', 'kecamatan__kab_kota__nama_kokab', 'paslon_id', 'paslon__no_urut_paslon', 'paslon__nama_calon', 'paslon__nama_wakil', 'paslon__foto_paslon').annotate(votes=Sum('jumlah_suara')):
        if not r['paslon_id']: continue
        foto_url = f"/media/{r['paslon__foto_paslon']}" if r['paslon__foto_paslon'] else ""
        is_main = (r['paslon_id'] in walbup_paslon_ids)
        add_stats('walbup', r['kecamatan__kode_kecamatan'], r['kecamatan__kab_kota__nama_kokab'], r['paslon_id'], r['votes'] or 0, {
            'no': r['paslon__no_urut_paslon'], 'nama': f"{r['paslon__nama_calon']} - {r['paslon__nama_wakil']}", 'warna': '#1e3a8a',
            'foto': foto_url, 'is_main': is_main
        })

    # 2. Ekstrak Suara Partai Pileg
    def process_pileg(level_key, ModelClass):
        for r in ModelClass.objects.values('kecamatan__kode_kecamatan', 'kecamatan__kab_kota__nama_kokab', 'partai_id', 'partai__no_urut_partai', 'partai__nama_partai', 'partai__warna_partai', 'partai__logo_partai').annotate(votes=Sum('jumlah_suara')):
            if not r['partai_id']: continue
            foto_url = f"/media/{r['partai__logo_partai']}" if r['partai__logo_partai'] else ""
            is_main = (r['partai_id'] == main_party.id)
            add_stats(level_key, r['kecamatan__kode_kecamatan'], r['kecamatan__kab_kota__nama_kokab'], r['partai_id'], r['votes'] or 0, {
                'no': r['partai__no_urut_partai'], 'nama': r['partai__nama_partai'], 'warna': r['partai__warna_partai'] or '#888',
                'foto': foto_url, 'is_main': is_main
            })
    process_pileg('ri', DSPilegRI); process_pileg('prov', DSPilegProv); process_pileg('kokab', DSPilegKokab)

    # 3. Add Sah & Tdk Sah directly from the `kecamatan_data`
    for d in kecamatan_data:
        k_kode = d['kode']
        k_kab = d['kab_kota']
        raw = d['raw']
        
        for key in ['pilpres', 'ri', 'prov', 'kokab', 'pilgub', 'walbup']:
            sah = raw.get(f'{key}_sah', 0)
            tsah = raw.get(f'{key}_tsah', 0)
            
            kec_s[k_kode][key]['sah'] += sah
            kec_s[k_kode][key]['tsah'] += tsah
            
            kokab_s[k_kab][key]['sah'] += sah
            kokab_s[k_kab][key]['tsah'] += tsah
            
            global_s[key]['sah'] += sah
            global_s[key]['tsah'] += tsah

    # 4. Format arrays and sort (Jadikan Leaderboard)
    def format_to_array(level_data, level_type):
        for k in ['pilpres', 'ri', 'prov', 'kokab', 'pilgub', 'walbup']:
            level_data[k]['tot'] = level_data[k]['sah'] + level_data[k]['tsah']
            arr = []
            sah = level_data[k]['sah']
            for item_id, votes in level_data[k]['items'].items():
                meta = meta_dict[k].get(item_id, {})
                arr.append({
                    'no': meta.get('no', 0), 
                    'nama': meta.get('nama', '-'), 
                    'warna': meta.get('warna', '#888'),
                    'foto': meta.get('foto', ''),
                    'is_main': meta.get('is_main', False),
                    'votes': votes, 
                    'pct': round((votes / sah * 100), 2) if sah > 0 else 0
                })
            arr = sorted(arr, key=lambda x: x['votes'], reverse=True)
            if k == 'walbup' and level_type == 'global': 
                arr = arr[:10] # Cegah overload di global map
            level_data[k]['items'] = arr

    format_to_array(global_s, 'global')
    for k, v in kokab_s.items(): format_to_array(v, 'kokab')
    for k, v in kec_s.items(): format_to_array(v, 'kecamatan')

    data_peta_kecamatan = []
    kecamatans = Kecamatan.objects.select_related(
        'geojson_data', 'clustering', 'kab_kota'
    ).filter(geojson_data__isnull=False)
    
    # Indexing results to map on GIS
    kec_results_map = {d['kode']: d for d in kecamatan_data}
    
    for kec in kecamatans:
        c_label = kec.clustering.label_cluster if hasattr(kec, 'clustering') else None
        geo_val = kec.geojson_data.geojson_data
        if isinstance(geo_val, str):
            try: geo_val = json.loads(geo_val)
            except: pass
            
        data_peta_kecamatan.append({
            'kode': kec.kode_kecamatan,
            'kecamatan': kec.nama_kecamatan,
            'kab_kota': kec.kab_kota.nama_kokab,
            'cluster': c_label,
            'geojson': geo_val,
            'stats': kec_results_map.get(kec.kode_kecamatan, {})
        })

    data_peta_kokab = []
    kokabs = KabupatenGeoJSON.objects.select_related('kabupaten').all()
    for k in kokabs:
        if k.geojson_data:
            geo_val = k.geojson_data
            if isinstance(geo_val, str):
                try: geo_val = json.loads(geo_val)
                except: pass
            data_peta_kokab.append({
                'kab_kota': k.kabupaten.nama_kokab,
                'kode': k.kabupaten.kode_kokab,
                'geojson': geo_val,
                'stats': kokab_stats_12.get(k.kabupaten.nama_kokab, {})
            })

    stats = {
        'global': global_s,
        'kokab': kokab_s,
        'kecamatan': kec_s,
        'names_info': names_info
    }

    context = {
        'selected_party': main_party,
        'map_data_json': data_peta_kecamatan,
        'kokab_map_data_json': data_peta_kokab,
        'stats_json': stats,
        'categories': ['pilpres', 'ri', 'prov', 'kokab', 'pilgub', 'walbup'],
    }
    return render(request, 'modules/clustering_gis.html', context)
