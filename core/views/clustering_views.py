from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Sum, Count
import pandas as pd
import io
import json

from ..utils.clustering_engine import ClusteringEngine, CLUSTER_COLORS
from ..services.data_service import ElectoralDataEngine
# from ..constants import CLUSTER_COLORS  # <--- Moved to clustering_engine.py
from ..models import Kecamatan, Partai, HasilClustering
from pilpres.models import Koalisi as KoalisiPilpres, DetailSuara as DSPilpres
from pilgub.models import KoalisiGubernur, DetailSuaraGubernur as DSPilgub
from pilwalbup.models import KoalisiWalbup, DetailSuaraWalbup as DSPilwalbup, PaslonWalbup, RekapSuaraWalbup as RSPilwalbup
from pileg_ri.models import DetailSuaraPilegRI as DSPilegRI
from pileg_prov.models import DetailSuaraPilegProv as DSPilegProv
from pileg_kokab.models import DetailSuaraPilegKokab as DSPilegKokab

# ==============================================================================
# VIEW KONTROLER: ATRIBUT & EKSPOR DATA
# ==============================================================================

@login_required(login_url='login')
def clustering_atribut_view(request):
    """Menampilkan tabel detail 13 atribut pemilu per kecamatan."""
    if not request.user.is_superuser:
        messages.warning(request, "Akses ditolak. Hanya Admin yang dapat melihat detail atribut clustering.")
        return redirect('dashboard')
        
    selected_party_id = request.GET.get('partai_utama') or request.POST.get('partai_utama')
    main_party, kecamatan_data, recap_perc = ElectoralDataEngine(selected_party_id).run()

    # Data tambahan untuk UI (Paslon Koalisi)
    koalisi_pilpres = KoalisiPilpres.objects.filter(partai=main_party).first()
    paslon_pilpres = koalisi_pilpres.paslon if koalisi_pilpres else None
    koalisi_pilgub = KoalisiGubernur.objects.filter(partai=main_party).first()
    paslon_pilgub = koalisi_pilgub.paslon if koalisi_pilgub else None
    koalisi_walbup_qs = KoalisiWalbup.objects.filter(partai=main_party).select_related('paslon', 'paslon__kab_kota')
    count_walbup = koalisi_walbup_qs.count()
    semua_paslon_walbup = [item.paslon for item in koalisi_walbup_qs]

    # Filter Kokab
    list_kokab = sorted(list(set([d['kab_kota'] for d in kecamatan_data])))
    selected_kokab = request.GET.get('kokab', '')
    if selected_kokab:
        kecamatan_data = [d for d in kecamatan_data if d['kab_kota'] == selected_kokab]

    # Logika Paginasi (20 baris per halaman)
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
        'list_kokab': list_kokab,
        'selected_kokab': selected_kokab,
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
    """Mengekspor data 13 atribut pemilu ke dalam format Excel."""
    if not request.user.is_superuser:
        return redirect('dashboard')
        
    selected_party_id = request.GET.get('partai_utama')
    main_party, data, recap = ElectoralDataEngine(selected_party_id).run()
    
    column_mapping = {
        'kode': 'Kode', 'kab_kota': 'Kabupaten/Kota', 'kecamatan': 'Kecamatan',
        'persen_pilpres': 'Perf Pilpres (%)', 'persen_pileg_ri': 'Perf RI (%)', 'persen_pileg_prov': 'Perf Prov (%)',
        'persen_pileg_kokab': 'Perf Kokab (%)', 'persen_pilgub': 'Perf Pilgub (%)', 'persen_pilwalbup': 'Perf Walbup (%)',
        'persen_part_pilpres': 'Part Pilpres (%)', 'persen_part_pileg_ri': 'Part RI (%)', 'persen_part_pileg_prov': 'Part Prov (%)',
        'persen_part_pileg_kokab': 'Part Kab (%)', 'persen_part_pilgub': 'Part Gub (%)', 'persen_part_pilwalbup': 'Part Wkt (%)',
        'persen_baseline_pilwalbup': 'Ratio Dukungan Paslon (%)'
    }
    
    df = pd.DataFrame(data)
    cols_to_export = list(column_mapping.keys())
    df = df[cols_to_export]
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

# ==============================================================================
# VIEW KONTROLER: NORMALISASI & VALIDASI MODEL
# ==============================================================================

@login_required
def zscore_normalization_view(request):
    """Transparansi perhitungan Normalisasi Z-Score untuk setiap atribut."""
    if not request.user.is_superuser:
        messages.warning(request, "Akses ditolak. Halaman ini hanya untuk keperluan teknis Admin.")
        return redirect('dashboard')
        
    selected_party_id = request.GET.get('partai_utama') or request.POST.get('partai_utama')
    main_party, kecamatan_data, extra_context = ElectoralDataEngine(selected_party_id).run()

    # Filter Kokab
    list_kokab = sorted(list(set([d['kab_kota'] for d in kecamatan_data])))
    selected_kokab = request.GET.get('kokab', '')
    if selected_kokab:
        kecamatan_data = [d for d in kecamatan_data if d['kab_kota'] == selected_kokab]
    attributes = [
        'persen_pilpres', 'persen_pileg_ri', 'persen_pileg_prov', 'persen_pileg_kokab', 'persen_pilgub', 'persen_pilwalbup',
        'persen_part_pilpres', 'persen_part_pileg_ri', 'persen_part_pileg_prov', 'persen_part_pileg_kokab', 'persen_part_pilgub', 'persen_part_pilwalbup',
        'persen_baseline_pilwalbup'
    ]
    
    df = pd.DataFrame(kecamatan_data)
    zscore_data = []
    
    if not df.empty:
        X_scaled = ClusteringEngine.scale_data(df, attributes)
        scaled_df = pd.DataFrame(X_scaled, columns=[f'z_{attr}' for attr in attributes]).round(3)
        full_df = pd.concat([df, scaled_df], axis=1)
        zscore_data = full_df.to_dict('records')

    context = {
        'list_kokab': list_kokab,
        'selected_kokab': selected_kokab,
        'page_title': 'Transparansi Normalisasi Z-Score',
        'zscore_data': zscore_data,
        'selected_party': main_party,
        'attributes': attributes,
        'active_menu': 'zscore-normalization'
    }
    return render(request, 'modules/zscore_data.html', context)

@login_required(login_url='login')
def export_zscore_excel(request):
    """Mengekspor hasil normalisasi Z-Score ke Excel."""
    if not request.user.is_superuser:
        return redirect('dashboard')
        
    selected_party_id = request.GET.get('partai_utama')
    main_party, kecamatan_data, extra = ElectoralDataEngine(selected_party_id).run()

    # Apply Kokab Filter
    selected_kokab = request.GET.get('kokab', '')
    if selected_kokab:
        kecamatan_data = [d for d in kecamatan_data if d['kab_kota'] == selected_kokab]

    attributes = [
        'persen_pilpres', 'persen_pileg_ri', 'persen_pileg_prov', 'persen_pileg_kokab', 'persen_pilgub', 'persen_pilwalbup',
        'persen_part_pilpres', 'persen_part_pileg_ri', 'persen_part_pileg_prov', 'persen_part_pileg_kokab', 'persen_part_pilgub', 'persen_part_pilwalbup',
        'persen_baseline_pilwalbup'
    ]
    
    df = pd.DataFrame(kecamatan_data)
    if not df.empty:
        X_scaled = ClusteringEngine.scale_data(df, attributes)
        scaled_cols = [f'Z {attr.replace("_", " ").title()}' for attr in attributes]
        scaled_df = pd.DataFrame(X_scaled, columns=scaled_cols)
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
    """Menampilkan hasil validasi K-Optimal (Elbow, Silhouette, DBI)."""
    if not request.user.is_superuser:
        messages.warning(request, "Akses ditolak. Validasi permodelan hanya dapat diakses oleh Admin.")
        return redirect('dashboard')
        
    selected_party_id = request.GET.get('partai_utama')
    main_party, kecamatan_data, extra = ElectoralDataEngine(selected_party_id).run()
    attributes = [
        'persen_pilpres', 'persen_pileg_ri', 'persen_pileg_prov', 'persen_pileg_kokab', 'persen_pilgub', 'persen_pilwalbup',
        'persen_part_pilpres', 'persen_part_pileg_ri', 'persen_part_pileg_prov', 'persen_part_pileg_kokab', 'persen_part_pilgub', 'persen_part_pilwalbup',
        'persen_baseline_pilwalbup'
    ]
    
    df = pd.DataFrame(kecamatan_data)
    validation_results = []
    
    if not df.empty:
        X_scaled = ClusteringEngine.scale_data(df, attributes)
        validation_results = ClusteringEngine.run_clustering_validation(X_scaled, 2, 10)
        
        # Logika pemeringkatan otomatis hasil validasi
        if validation_results:
            silh_desc = sorted(validation_results, key=lambda x: x['silhouette'], reverse=True)
            dbi_asc = sorted(validation_results, key=lambda x: x['dbi'])
            p1, pn = (validation_results[0]['k'], validation_results[0]['sse']), (validation_results[-1]['k'], validation_results[-1]['sse'])
            A, B, C = p1[1] - pn[1], pn[0] - p1[0], p1[0]*pn[1] - pn[0]*p1[1]
            sqrt_ab = (A**2 + B**2)**0.5
            max_dist, elbow_k = -1, 5
            for r in validation_results:
                dist = abs(A*r['k'] + B*r['sse'] + C) / sqrt_ab
                if dist > max_dist: max_dist, elbow_k = dist, r['k']
            for r in validation_results:
                r['rank_silhouette'] = next((i + 1 for i, s in enumerate(silh_desc) if s['k'] == r['k']), 99)
                r['is_top3_silhouette'] = (r['rank_silhouette'] <= 3)
                r['rank_dbi'] = next((i + 1 for i, d in enumerate(dbi_asc) if d['k'] == r['k']), 99)
                r['is_top3_dbi'] = (r['rank_dbi'] <= 3)
                r['is_elbow'] = (r['k'] == elbow_k)

    context = {
        'page_title': 'Validasi Modeling (K-Optimal)',
        'results': validation_results,
        'results_json': validation_results,
        'selected_party': main_party,
        'active_menu': 'clustering-validation'
    }
    return render(request, 'modules/clustering_validation.html', context)

# ==============================================================================
# VIEW KONTROLER: HASIL KLASTERISASI & VISUALISASI
# ==============================================================================

@login_required(login_url='login')
def clustering_results_view(request):
    """Eksekusi K-Means dan visualisasi hasil klasterisasi (PCA & Tabel)."""
    if not request.user.is_superuser:
        messages.warning(request, "Akses ditolak. Hasil klasterisasi bersifat terbatas.")
        return redirect('dashboard')
        
    k_param = request.GET.get('k')
    if k_param:
        k_final = int(k_param)
    else:
        k_from_db = HasilClustering.objects.values('label_cluster').distinct().count()
        k_final = k_from_db if k_from_db > 0 else 5

    selected_party_id = request.GET.get('partai_utama')
    main_party, kecamatan_data, extra = ElectoralDataEngine(selected_party_id).run()
    attributes = [
        'persen_pilpres', 'persen_pileg_ri', 'persen_pileg_prov', 'persen_pileg_kokab', 'persen_pilgub', 'persen_pilwalbup',
        'persen_part_pilpres', 'persen_part_pileg_ri', 'persen_part_pileg_prov', 'persen_part_pileg_kokab', 'persen_part_pilgub', 'persen_part_pilwalbup',
        'persen_baseline_pilwalbup'
    ]
    attr_labels = [
        'Perf Pres', 'Perf RI', 'Perf Prov', 'Perf Kab', 'Perf Gub', 'Perf Wkt',
        'Part Pres', 'Part RI', 'Part Prov', 'Part Kab', 'Part Gub', 'Part Wkt', 'Ratio Duk'
    ]
    df = pd.DataFrame(kecamatan_data)
    pca_data, centroid_data, result_rows = [], [], []

    list_kokab = sorted(list(set([d['kab_kota'] for d in kecamatan_data]))) if kecamatan_data else []
    selected_kokab = request.GET.get('kokab', '')

    if not df.empty:
        X_scaled = ClusteringEngine.scale_data(df, attributes)
        labels = ClusteringEngine.run_kmeans(X_scaled, k_final)
        df['cluster_label'] = labels
        # Simpan hasil ke database secara permanen
        for _, row in df.iterrows():
            HasilClustering.objects.update_or_create(kecamatan_id=int(row['id']), defaults={'label_cluster': int(row['cluster_label'])})
        
        cluster_info = {cid: {'name': f'Klaster {cid}', 'color': CLUSTER_COLORS.get(cid, '#94a3b8')} for cid in range(max(10, k_final))}
        pca_data, acc_pca = ClusteringEngine.get_pca_projection(X_scaled, labels, df, cluster_info)
        acc_pca = round(acc_pca, 2)
        
        # Hitung rata-rata tiap atribut per cluster (untuk profiling)
        for c in range(k_final):
            cluster_df = df[df['cluster_label'] == c]
            means = cluster_df[attributes].mean().round(3).tolist()
            c_style = cluster_info.get(c, {'name': f'Klaster {c}', 'color': '#94a3b8'})
            centroid_data.append({'cluster': c, 'name': c_style['name'], 'color': c_style['color'], 'count': len(cluster_df), 'means': means})
        
        for _, row in df.iterrows():
            if selected_kokab and row['kab_kota'] != selected_kokab:
                continue
                
            cid = int(row['cluster_label'])
            c_style = cluster_info.get(cid, {'name': f'Klaster {cid}', 'color': '#94a3b8'})
            result_rows.append({'kode': row['kode'], 'kab_kota': row['kab_kota'], 'kecamatan': row['kecamatan'], 'cluster': cid, 'cluster_name': c_style['name'], 'color': c_style['color']})

        # Hitung Cross Tabulation Rekap Kokab
        rekap_kokab = []
        crosstab = pd.crosstab(df['kab_kota'], df['cluster_label'])
        
        # Mapping kab_kota -> prefix kode untuk keperluan sorting (misal '3201' untuk Bogor)
        kab_kode_map = {row['kab_kota']: str(row['kode'])[:4] for _, row in df.iterrows()}
        sorted_kabs = sorted(df['kab_kota'].unique(), key=lambda k: kab_kode_map.get(k, k))

        for kab in sorted_kabs:
            if selected_kokab and kab != selected_kokab:
                continue
            counts = []
            for c in range(k_final):
                val = int(crosstab.loc[kab, c]) if c in crosstab.columns and kab in crosstab.index else 0
                counts.append({'cluster': c, 'count': val, 'color': cluster_info.get(c, {}).get('color', '#94a3b8')})
            rekap_kokab.append({'kab_kota': kab, 'counts': counts, 'total': sum(c['count'] for c in counts)})

    context = {
        'list_kokab': list_kokab,
        'selected_kokab': selected_kokab,
        'page_title': 'Hasil Cluster', 'result_rows': result_rows, 'result_rows_json': result_rows, 'pca_data': pca_data,
        'centroid_data': centroid_data, 'attr_labels': attr_labels, 'attr_labels_list': attr_labels, 'k_final': k_final,
        'rekap_kokab': rekap_kokab if 'rekap_kokab' in locals() else [],
        'acc_pca': acc_pca if not df.empty else 0, 'selected_party': main_party, 'k_range': range(2, 11),
        'k_final_for_export': k_final, 'cluster_colors': CLUSTER_COLORS,
    }
    return render(request, 'modules/clustering_results.html', context)

@login_required(login_url='login')
def export_clustering_results_excel(request):
    """Mengekspor daftar kecamatan beserta label klasternya ke Excel."""
    if not request.user.is_superuser: return redirect('dashboard')
    selected_party_id = request.GET.get('partai_utama')
    k_final = int(request.GET.get('k', 5))
    main_party, kecamatan_data, _ = ElectoralDataEngine(selected_party_id).run()
    attributes = [
        'perf_pilpres', 'perf_ri', 'perf_prov', 'perf_kokab', 'perf_pilgub', 'perf_walbup',
        'part_pilpres', 'part_ri', 'part_prov', 'part_kokab', 'part_pilgub', 'part_walbup',
        'n_paslon_pilkada_kokab'
    ]
    df = pd.DataFrame(kecamatan_data)
    if df.empty: return HttpResponse('Data tidak tersedia.', status=404)
    X_scaled = ClusteringEngine.scale_data(df, attributes)
    labels = ClusteringEngine.run_kmeans(X_scaled, k_final)
    df['Label Klaster'] = labels
    
    selected_kokab = request.GET.get('kokab', '')
    if selected_kokab:
        df = df[df['kab_kota'] == selected_kokab]
        
    output_df = df[['kode', 'kab_kota', 'kecamatan', 'Label Klaster']].copy()
    output_df.columns = ['Kode Kecamatan', 'Kab/Kota', 'Nama Kecamatan', 'Label Klaster']
    output_df = output_df.sort_values(['Label Klaster', 'Kab/Kota', 'Nama Kecamatan'])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer: output_df.to_excel(writer, index=False, sheet_name=f'Hasil_K{k_final}')
    output.seek(0)
    response = HttpResponse(output, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="hasil_cluster_K{k_final}_{main_party.nama_partai}.xlsx"'
    return response

@login_required(login_url='login')
def clustering_gis_view(request):
    """Dashboard GIS: Visualisasi spasial hasil klasterisasi dan statistik wilayah."""
    from geojson.models import KabupatenGeoJSON
    from collections import defaultdict
    selected_party_id = request.GET.get('partai_utama')
    main_party, kecamatan_data, _ = ElectoralDataEngine(selected_party_id).run()
    
    # Identifikasi Paslon Pengusung Partai
    paslon_pilpres_id = KoalisiPilpres.objects.filter(partai=main_party).values_list('paslon_id', flat=True).first()
    paslon_pilgub_id = KoalisiGubernur.objects.filter(partai=main_party).values_list('paslon_id', flat=True).first()
    walbup_paslon_ids = list(KoalisiWalbup.objects.filter(partai=main_party).values_list('paslon_id', flat=True))
    
    # Metadata Paslon untuk legenda Peta
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
        'partai': main_party.nama_partai, 'partai_logo': f"/media/{main_party.logo_partai}" if main_party.logo_partai else "",
        'walbup': walbup_names, 'walbup_foto': walbup_fotos, 'warna': main_party.warna_partai or '#1e3a8a'
    }
    
    # Agregasi data per Kabupaten untuk Peta Provinsi
    kokab_stats_12, kokab_groups = {}, defaultdict(list)
    for d in kecamatan_data: kokab_groups[d['kab_kota']].append(d)
    for kab, items in kokab_groups.items():
        kokab_stats_12[kab] = {k: sum(i[k] for i in items) / len(items) if items else 0 for k in ['persen_pilpres', 'persen_pileg_ri', 'persen_pileg_prov', 'persen_pileg_kokab', 'persen_pilgub', 'persen_pilwalbup', 'persen_part_pilpres', 'persen_part_pileg_ri', 'persen_part_pileg_prov', 'persen_part_pileg_kokab', 'persen_part_pilgub', 'persen_part_pilwalbup']}
    
    def new_stats(): return {k: {'sah': 0, 'tsah': 0, 'tot': 0, 'items': {}} for k in ['pilpres', 'ri', 'prov', 'kokab', 'pilgub', 'walbup']}
    global_s, kokab_s, kec_s, meta_dict = new_stats(), defaultdict(new_stats), defaultdict(new_stats), defaultdict(dict)
    
    def add_stats(k, k_kode, k_kab, item_id, v, meta):
        kec_s[k_kode][k]['items'][item_id] = kec_s[k_kode][k]['items'].get(item_id, 0) + v
        kokab_s[k_kab][k]['items'][item_id] = kokab_s[k_kab][k]['items'].get(item_id, 0) + v
        global_s[k]['items'][item_id] = global_s[k]['items'].get(item_id, 0) + v
        meta_dict[k][item_id] = meta
    
    # Tarik Detail Suara untuk Tooltip Peta
    for r in DSPilpres.objects.values('kecamatan__kode_kecamatan', 'kecamatan__kab_kota__nama_kokab', 'paslon_id', 'paslon__no_urut_paslon', 'paslon__nama_capres', 'paslon__nama_cawapres', 'paslon__foto_paslon').annotate(v=Sum('jumlah_suara')):
        if r['paslon_id']: add_stats('pilpres', r['kecamatan__kode_kecamatan'], r['kecamatan__kab_kota__nama_kokab'], r['paslon_id'], r['v'] or 0, {'no': r['paslon__no_urut_paslon'], 'nama': f"{r['paslon__nama_capres']} - {r['paslon__nama_cawapres']}", 'warna': '#1e3a8a', 'foto': f"/media/{r['paslon__foto_paslon']}" if r['paslon__foto_paslon'] else "", 'is_main': (r['paslon_id'] == paslon_pilpres_id)})
    
    for r in DSPilgub.objects.values('kecamatan__kode_kecamatan', 'kecamatan__kab_kota__nama_kokab', 'paslon_id', 'paslon__no_urut_paslon', 'paslon__nama_cagub', 'paslon__nama_cawagub', 'paslon__foto_paslon').annotate(v=Sum('jumlah_suara')):
        if r['paslon_id']: add_stats('pilgub', r['kecamatan__kode_kecamatan'], r['kecamatan__kab_kota__nama_kokab'], r['paslon_id'], r['v'] or 0, {'no': r['paslon__no_urut_paslon'], 'nama': f"{r['paslon__nama_cagub']} - {r['paslon__nama_cawagub']}", 'warna': '#1e3a8a', 'foto': f"/media/{r['paslon__foto_paslon']}" if r['paslon__foto_paslon'] else "", 'is_main': (r['paslon_id'] == paslon_pilgub_id)})
    
    for r in DSPilwalbup.objects.values('kecamatan__kode_kecamatan', 'kecamatan__kab_kota__nama_kokab', 'paslon_id', 'paslon__no_urut_paslon', 'paslon__nama_calon', 'paslon__nama_wakil', 'paslon__foto_paslon').annotate(v=Sum('jumlah_suara')):
        if r['paslon_id']: add_stats('walbup', r['kecamatan__kode_kecamatan'], r['kecamatan__kab_kota__nama_kokab'], r['paslon_id'], r['v'] or 0, {'no': r['paslon__no_urut_paslon'], 'nama': f"{r['paslon__nama_calon']} - {r['paslon__nama_wakil']}", 'warna': '#1e3a8a', 'foto': f"/media/{r['paslon__foto_paslon']}" if r['paslon__foto_paslon'] else "", 'is_main': (r['paslon_id'] in walbup_paslon_ids)})
    
    for k, m in [('ri', DSPilegRI), ('prov', DSPilegProv), ('kokab', DSPilegKokab)]:
        for r in m.objects.values('kecamatan__kode_kecamatan', 'kecamatan__kab_kota__nama_kokab', 'partai_id', 'partai__no_urut_partai', 'partai__nama_partai', 'partai__warna_partai', 'partai__logo_partai').annotate(v=Sum('jumlah_suara')):
            if r['partai_id']: add_stats(k, r['kecamatan__kode_kecamatan'], r['kecamatan__kab_kota__nama_kokab'], r['partai_id'], r['v'] or 0, {'no': r['partai__no_urut_partai'], 'nama': r['partai__nama_partai'], 'warna': r['partai__warna_partai'] or '#888', 'foto': f"/media/{r['partai__logo_partai']}" if r['partai__logo_partai'] else "", 'is_main': (r['partai_id'] == main_party.id)})
    
    for d in kecamatan_data:
        k_kode, k_kab, raw = d['kode'], d['kab_kota'], d['raw']
        for key in ['pilpres', 'ri', 'prov', 'kokab', 'pilgub', 'walbup']:
            s, ts = raw.get(f'{key}_sah', 0), raw.get(f'{key}_tsah', 0)
            for target in [global_s, kokab_s[k_kab], kec_s[k_kode]]: target[key]['sah'] += s; target[key]['tsah'] += ts
    
    def fmt(data, t):
        for k in ['pilpres', 'ri', 'prov', 'kokab', 'pilgub', 'walbup']:
            data[k]['tot'], arr, sah = data[k]['sah'] + data[k]['tsah'], [], data[k]['sah']
            for iid, v in data[k]['items'].items():
                m = meta_dict[k].get(iid, {})
                arr.append({'no': m.get('no', 0), 'nama': m.get('nama', '-'), 'warna': m.get('warna', '#888'), 'foto': m.get('foto', ''), 'is_main': m.get('is_main', False), 'votes': v, 'pct': round((v / sah * 100), 2) if sah > 0 else 0})
            arr = sorted(arr, key=lambda x: x['votes'], reverse=True)
            if k == 'walbup' and t == 'global': arr = arr[:10]
            data[k]['items'] = arr
    
    fmt(global_s, 'global')
    for k, v in kokab_s.items(): fmt(v, 'kokab')
    for k, v in kec_s.items(): fmt(v, 'kecamatan')
    
    kec_results_map = {d['kode']: d for d in kecamatan_data}
    data_peta_kecamatan = [{'kode': k.kode_kecamatan, 'kecamatan': k.nama_kecamatan, 'kab_kota': k.kab_kota.nama_kokab, 'cluster': k.clustering.label_cluster if hasattr(k, 'clustering') else None, 'geojson': json.loads(k.geojson_data.geojson_data) if isinstance(k.geojson_data.geojson_data, str) else k.geojson_data.geojson_data, 'stats': kec_results_map.get(k.kode_kecamatan, {})} for k in Kecamatan.objects.select_related('geojson_data', 'clustering', 'kab_kota').filter(geojson_data__isnull=False)]
    data_peta_kokab = [{'kab_kota': k.kabupaten.nama_kokab, 'kode': k.kabupaten.kode_kokab, 'geojson': json.loads(k.geojson_data) if isinstance(k.geojson_data, str) else k.geojson_data, 'stats': kokab_stats_12.get(k.kabupaten.nama_kokab, {})} for k in KabupatenGeoJSON.objects.select_related('kabupaten').all() if k.geojson_data]
    
    context = {'selected_party': main_party, 'map_data_json': data_peta_kecamatan, 'kokab_map_data_json': data_peta_kokab, 'stats_json': {'global': global_s, 'kokab': kokab_s, 'kecamatan': kec_s, 'names_info': names_info}, 'categories': ['pilpres', 'ri', 'prov', 'kokab', 'pilgub', 'walbup'], 'cluster_colors': CLUSTER_COLORS}
    return render(request, 'modules/clustering_gis.html', context)
