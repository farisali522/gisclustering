from django.db.models import Sum, F, OuterRef, Subquery, IntegerField, Count
from django.db.models.functions import Coalesce
from core.models import Kecamatan, Partai
from pilpres.models import DetailSuara as DSPilpres, Koalisi as KoalisiPilpres
from pileg_ri.models import DetailSuaraPilegRI as DSPilegRI
from pileg_prov.models import DetailSuaraPilegProv as DSPilegProv
from pileg_kokab.models import DetailSuaraPilegKokab as DSPilegKokab
from pilgub.models import DetailSuaraGubernur as DSPilgub, KoalisiGubernur
from pilwalbup.models import DetailSuaraWalbup as DSPilwalbup, KoalisiWalbup, PaslonWalbup

# ==============================================================================
# BAGIAN 1: DATABASE SELECTORS (Helper Query Database)
# ==============================================================================

def get_sah_subquery(model):
    """Subquery otomatis untuk menghitung Total Suara Sah per Kecamatan."""
    return Subquery(
        model.objects.filter(kecamatan=OuterRef('pk'))
        .values('kecamatan')
        .annotate(total=Sum('jumlah_suara'))
        .values('total'),
        output_field=IntegerField()
    )

def get_party_votes_subquery(model, party_id):
    """Subquery untuk menghitung perolehan suara Partai Utama."""
    if not party_id: return Coalesce(0, 0)
    return Subquery(
        model.objects.filter(kecamatan=OuterRef('pk'), partai_id=party_id)
        .values('kecamatan')
        .annotate(total=Sum('jumlah_suara'))
        .values('total'),
        output_field=IntegerField()
    )

def get_paslon_votes_subquery(model, paslon_id):
    """Subquery untuk menghitung perolehan suara Pasangan Calon (Paslon)."""
    if not paslon_id: return Coalesce(0, 0)
    return Subquery(
        model.objects.filter(kecamatan=OuterRef('pk'), paslon_id=paslon_id)
        .values('kecamatan')
        .annotate(total=Sum('jumlah_suara'))
        .values('total'),
        output_field=IntegerField()
    )

# ==============================================================================
# BAGIAN 2: ELECTORAL DATA ENGINE (Mesin Agregasi Utama)
# ==============================================================================

class ElectoralDataEngine:
    """
    Engine profesional untuk mengumpulkan, menghitung, dan memformat 13 atribut
    clustering dari 6 tingkatan pemilu secara efisien (High Performance).
    """
    
    def __init__(self, party_id=None):
        self.main_party = self._get_main_party(party_id)
        self.paslon_pilpres_id = self._get_paslon_id(KoalisiPilpres)
        self.paslon_pilgub_id = self._get_paslon_id(KoalisiGubernur)

    def _get_main_party(self, party_id):
        """Mencari objek Partai Utama (Default: GERINDRA jika ID kosong)."""
        if party_id:
            try: return Partai.objects.get(id=party_id)
            except (Partai.DoesNotExist, ValueError): pass
        return Partai.objects.get(no_urut_partai=2)

    def _get_paslon_id(self, KoalisiModel):
        """Mencari ID Paslon yang diusung oleh Partai Utama di level tertentu."""
        koalisi = KoalisiModel.objects.filter(partai=self.main_party).first()
        return koalisi.paslon_id if koalisi else None

    # --------------------------------------------------------------------------
    # KERANGKA ANOTASI DATABASE (Subquery Orchestration)
    # --------------------------------------------------------------------------
    def _get_annotated_queryset(self):
        """Menggunakan Subquery untuk menarik semua data dalam satu tarikan Query tunggal."""
        return Kecamatan.objects.select_related('kab_kota', 'tps_pemilu', 'tps_pilkada').annotate(
            
            # --- Performa Suara (Votes) ---
            perf_pilpres_votes = Coalesce(get_paslon_votes_subquery(DSPilpres, self.paslon_pilpres_id), 0),
            perf_pilpres_sah   = Coalesce(get_sah_subquery(DSPilpres), 0),
            
            perf_ri_votes      = Coalesce(get_party_votes_subquery(DSPilegRI, self.main_party.id), 0),
            perf_ri_sah        = Coalesce(get_sah_subquery(DSPilegRI), 0),
            
            perf_prov_votes    = Coalesce(get_party_votes_subquery(DSPilegProv, self.main_party.id), 0),
            perf_prov_sah      = Coalesce(get_sah_subquery(DSPilegProv), 0),
            
            perf_kokab_votes   = Coalesce(get_party_votes_subquery(DSPilegKokab, self.main_party.id), 0),
            perf_kokab_sah     = Coalesce(get_sah_subquery(DSPilegKokab), 0),
            
            perf_pilgub_votes  = Coalesce(get_paslon_votes_subquery(DSPilgub, self.paslon_pilgub_id), 0),
            perf_pilgub_sah    = Coalesce(get_sah_subquery(DSPilgub), 0),
            
            perf_walbup_votes  = Coalesce(Subquery(
                DSPilwalbup.objects.filter(
                    kecamatan=OuterRef('pk'),
                    paslon_id=Subquery(
                        KoalisiWalbup.objects.filter(
                            partai=self.main_party,
                            paslon__kab_kota=OuterRef(OuterRef('kab_kota_id'))
                        ).values('paslon_id')[:1]
                    )
                ).values('kecamatan').annotate(total=Sum('jumlah_suara')).values('total'),
                output_field=IntegerField()
            ), 0),
            perf_walbup_sah    = Coalesce(get_sah_subquery(DSPilwalbup), 0),

            # --- Partisipasi Pemilih (Turnout) ---
            part_pilpres_sah     = F('perf_pilpres_sah'),
            part_pilpres_tdk_sah = Coalesce(F('rekap_pilpres__total_suara_tidak_sah'), 0),
            part_pilpres_dpt     = Coalesce(F('tps_pemilu__rekap_dpt_pemilu'), 1),
            
            part_ri_sah          = F('perf_ri_sah'),
            part_ri_tdk_sah      = Coalesce(F('rekap_pileg_ri__total_suara_tidak_sah'), 0),
            
            part_prov_sah        = F('perf_prov_sah'),
            part_prov_tdk_sah    = Coalesce(F('rekap_pileg_prov__total_suara_tidak_sah'), 0),
            
            part_kokab_sah       = F('perf_kokab_sah'),
            part_kokab_tdk_sah   = Coalesce(F('rekap_pileg_kokab__total_suara_tidak_sah'), 0),
            
            part_pilgub_sah      = F('perf_pilgub_sah'),
            part_pilgub_tdk_sah  = Coalesce(F('rekap_pilgub__total_suara_tidak_sah'), 0),
            part_pilgub_dpt      = Coalesce(F('tps_pilkada__rekap_dpt_pilkada'), 1),
            
            part_walbup_sah      = F('perf_walbup_sah'),
            part_walbup_tdk_sah  = Coalesce(F('rekap_pilwalbup__total_suara_tidak_sah'), 0),
            
            # --- Metadata Wilayah ---
            t_pemilu_c  = Coalesce(F('tps_pemilu__rekap_tps_pemilu'), 0),
            d_pemilu_c  = Coalesce(F('tps_pemilu__rekap_dpt_pemilu'), 0),
            t_pilkada_c = Coalesce(F('tps_pilkada__rekap_tps_pilkada'), 0),
            d_pilkada_c = Coalesce(F('tps_pilkada__rekap_dpt_pilkada'), 0),
            
        ).order_by('kode_kecamatan')

    # --------------------------------------------------------------------------
    # ALUR EKSEKUSI (Execution Flow)
    # --------------------------------------------------------------------------
    def run(self):
        """Menjalankan orkestrasi pengambilan data dan format akhir."""
        raw_qs = self._get_annotated_queryset()
        paslon_counts = self._get_walbup_paslon_counts()
        kecamatan_list = [self._format_kec_item(k, paslon_counts.get(k.kab_kota_id, 0)) for k in raw_qs]
        return self.main_party, kecamatan_list, self._calculate_totals(raw_qs)

    def _get_walbup_paslon_counts(self):
        """Menghitung total paslon per Kab/Kota untuk perhitungan Rasio Dukungan."""
        return {item['kab_kota_id']: item['count'] for item in PaslonWalbup.objects.exclude(nama_calon__icontains='KOTAK KOSONG').values('kab_kota_id').annotate(count=Count('id'))}

    def _format_kec_item(self, k, n_paslon):
        """Membersihkan mentahan database menjadi objek data yang siap diklasifikasi."""
        def pct(v, s): return round((v / s) * 100, 3) if s > 0 else 0
        def part_pct(sah, tsah, dpt): return round(((sah + tsah) / dpt) * 100, 3) if dpt > 0 else 0
        
        return {
            'id': k.id, 'kode': k.kode_kecamatan, 'kab_kota': k.kab_kota.nama_kokab, 'kecamatan': k.nama_kecamatan,
            
            # Persentase Performa Suara
            'persen_pilpres': pct(k.perf_pilpres_votes, k.perf_pilpres_sah),
            'persen_pileg_ri':      pct(k.perf_ri_votes, k.perf_ri_sah),
            'persen_pileg_prov':    pct(k.perf_prov_votes, k.perf_prov_sah),
            'persen_pileg_kokab':   pct(k.perf_kokab_votes, k.perf_kokab_sah),
            'persen_pilgub':  pct(k.perf_pilgub_votes, k.perf_pilgub_sah),
            'persen_pilwalbup':  pct(k.perf_walbup_votes, k.perf_walbup_sah),
            
            # Persentase Partisipasi Pemilih
            'persen_part_pilpres': part_pct(k.part_pilpres_sah, k.part_pilpres_tdk_sah, k.part_pilpres_dpt),
            'persen_part_pileg_ri':      part_pct(k.part_ri_sah, k.part_ri_tdk_sah, k.part_pilpres_dpt),
            'persen_part_pileg_prov':    part_pct(k.part_prov_sah, k.part_prov_tdk_sah, k.part_pilpres_dpt),
            'persen_part_pileg_kokab':   part_pct(k.part_kokab_sah, k.part_kokab_tdk_sah, k.part_pilpres_dpt),
            'persen_part_pilgub':  part_pct(k.part_pilgub_sah, k.part_pilgub_tdk_sah, k.part_pilgub_dpt),
            'persen_part_pilwalbup':  part_pct(k.part_walbup_sah, k.part_walbup_tdk_sah, k.part_pilgub_dpt),
            
            # Parameter Tambahan
            'persen_baseline_pilwalbup': (1 / n_paslon) * 100 if n_paslon > 0 else 0,
            
            'raw': {
                'pilpres_votes': k.perf_pilpres_votes, 'pilpres_sah': k.perf_pilpres_sah, 'pilpres_tsah': k.part_pilpres_tdk_sah,
                'ri_votes': k.perf_ri_votes, 'ri_sah': k.perf_ri_sah, 'ri_tsah': k.part_ri_tdk_sah,
                'prov_votes': k.perf_prov_votes, 'prov_sah': k.perf_prov_sah, 'prov_tsah': k.part_prov_tdk_sah,
                'kokab_votes': k.perf_kokab_votes, 'kokab_sah': k.perf_kokab_sah, 'kokab_tsah': k.part_kokab_tdk_sah,
                'pilgub_votes': k.perf_pilgub_votes, 'pilgub_sah': k.perf_pilgub_sah, 'pilgub_tsah': k.part_pilgub_tdk_sah,
                'walbup_votes': k.perf_walbup_votes, 'walbup_sah': k.perf_walbup_sah, 'walbup_tsah': k.part_walbup_tdk_sah,
                'tps_pemilu': k.t_pemilu_c, 'dpt_pemilu': k.d_pemilu_c, 'tps_pilkada': k.t_pilkada_c, 'dpt_pilkada': k.d_pilkada_c,
            }
        }

    def _calculate_totals(self, raw_qs):
        """Penjumlahan global untuk statistik ringkasan di Header Dashboard."""
        c = ['pilpres', 'ri', 'prov', 'kokab', 'pilgub', 'walbup']
        sums = raw_qs.aggregate(**{f'{cat}_v': Sum(f'perf_{cat}_votes') for cat in c}, **{f'{cat}_s': Sum(f'perf_{cat}_sah') for cat in c})
        return {cat: round((sums[f'{cat}_v'] / sums[f'{cat}_s'] * 100), 2) if sums[f'{cat}_s'] > 0 else 0 for cat in c}

# ==============================================================================
# BAGIAN 3: FUNGSI PEMBUNGKUS (Wrapper Kompatibilitas)
# ==============================================================================

def get_clustering_data(party_id=None):
    """Pintu masuk satus-satunya bagi Views untuk memanggil mesin aggregasi."""
    return ElectoralDataEngine(party_id).run()
