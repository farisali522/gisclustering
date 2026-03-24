import os
import uuid
from django.db import models
from core.models import KabupatenKota, Partai, Kecamatan

def path_dan_nama_unik_caleg_prov(instance, filename):
    extension = filename.split('.')[-1]
    # Simpan di folder foto_caleg_prov/nama_dapil/nama_partai/
    dapil_str = instance.dapil.nama_dapil if instance.dapil else "tanpa_dapil"
    partai_str = instance.partai.nama_partai if instance.partai else "tanpa_partai"
    nama_baru = f"{instance.no_urut}_{uuid.uuid4().hex[:8]}.{extension}"
    return os.path.join(f'foto_caleg_prov/{dapil_str}/{partai_str}/', nama_baru)

class DapilProv(models.Model):
    nama_dapil = models.CharField(max_length=100, verbose_name="Nama Dapil")
    jumlah_kursi = models.IntegerField(default=0, verbose_name="Jumlah Kursi")
    wilayah_kokab = models.ManyToManyField(KabupatenKota, related_name='dapil_prov', verbose_name="Cakupan Wilayah (Kab/Kota)")
    
    def __str__(self):
        return self.nama_dapil

    class Meta:
        verbose_name_plural = "Dapil Provinsi"
        ordering = ['nama_dapil']

class CalegProv(models.Model):
    GENDER_CHOICES = (
        ('L', 'Laki-laki'),
        ('P', 'Perempuan'),
    )

    nama_caleg = models.CharField(max_length=100, verbose_name="Nama Caleg")
    no_urut = models.IntegerField(verbose_name="Nomor Urut", default=1)
    dapil = models.ForeignKey(DapilProv, on_delete=models.CASCADE, related_name='caleg', verbose_name="Dapil")
    partai = models.ForeignKey(Partai, on_delete=models.CASCADE, related_name='caleg_prov', verbose_name="Partai")
    jenis_kelamin = models.CharField(max_length=1, choices=GENDER_CHOICES, verbose_name="Jenis Kelamin", null=True, blank=True)
    foto_caleg = models.ImageField(upload_to=path_dan_nama_unik_caleg_prov, null=True, blank=True, verbose_name="Foto Caleg (Opsional)")
    
    def __str__(self):
        return f"{self.no_urut}. {self.nama_caleg} ({self.partai.nama_partai})"

    class Meta:
        verbose_name_plural = "Caleg Provinsi"
        ordering = ['dapil', 'partai', 'no_urut']
        unique_together = ('dapil', 'partai', 'no_urut') # Satu Dapil, satu partai, gak boleh ada nomor urut kembar


class RekapSuaraPilegProv(models.Model):
    kecamatan = models.OneToOneField(Kecamatan, on_delete=models.CASCADE, related_name='rekap_pileg_prov', verbose_name="Kecamatan")
    total_suara_tidak_sah = models.IntegerField(default=0, verbose_name="Total Suara Tidak Sah")

    @property
    def total_suara_sah(self):
        return sum(d.jumlah_suara for d in self.kecamatan.detail_pileg_prov.all())

    @property
    def total_semua_suara(self):
        return self.total_suara_sah + self.total_suara_tidak_sah

    @property
    def persentase_suara_sah_str(self):
        t = self.total_semua_suara
        pct = (self.total_suara_sah / t * 100) if t > 0 else 0
        return f"{pct:.2f}"

    @property
    def persentase_suara_tidak_sah_str(self):
        t = self.total_semua_suara
        pct = (self.total_suara_tidak_sah / t * 100) if t > 0 else 0
        return f"{pct:.2f}"

    @property
    def persentase_dpt_masuk_str(self):
        try:
            dpt = self.kecamatan.tps_pemilu.rekap_dpt_pemilu
            pct = (self.total_semua_suara / dpt * 100) if dpt > 0 else 0
            return f"{pct:.2f}"
        except:
            return "0.00"

    def get_total_suara_partai(self, partai):
        """
        Menghitung TOTAL SUARA PARTAI (Coblos Partai Saja + Seluruh Coblos Caleg di bawah Partai tsb)
        Karena sudah 1 class, kita cukup filter berdasarkan partai_id
        """
        return sum(d.jumlah_suara for d in self.kecamatan.detail_pileg_prov.all() if d.partai_id == partai.id)

    def __str__(self):
        return str(self.kecamatan)

    class Meta:
        verbose_name_plural = "Rekap Suara Kecamatan"

class DetailSuaraPilegProv(models.Model):
    kecamatan = models.ForeignKey(Kecamatan, on_delete=models.CASCADE, related_name='detail_pileg_prov', verbose_name="Kecamatan")
    partai = models.ForeignKey(Partai, on_delete=models.CASCADE, related_name='suara_pileg_prov', verbose_name="Partai")
    caleg = models.ForeignKey(CalegProv, on_delete=models.CASCADE, related_name='suara_pileg_prov', verbose_name="Caleg", null=True, blank=True)
    jumlah_suara = models.IntegerField(default=0, verbose_name="Jumlah Suara")

    def __str__(self):
        if self.caleg:
            return f"Caleg: {self.caleg.nama_caleg} ({self.partai.nama_partai}) - {self.kecamatan.nama_kecamatan}"
        return f"PARTAI SAJA: {self.partai.nama_partai} - {self.kecamatan.nama_kecamatan}"

    class Meta:
        verbose_name_plural = "Data Detail Suara (Pileg Provinsi)"
        unique_together = ('kecamatan', 'partai', 'caleg')

class RekapSuaraPilegProvKabManager(models.Manager):
    def get_queryset(self):
        from django.db.models import Sum, Subquery, OuterRef, IntegerField
        from django.db.models.functions import Coalesce
        from core.models import Kecamatan
        from .models import DetailSuaraPilegProv, RekapSuaraPilegProv
        qs = super().get_queryset()
        return qs.annotate(
            agg_sah=Coalesce(
                Subquery(
                    DetailSuaraPilegProv.objects.filter(kecamatan__kab_kota=OuterRef('pk'))
                    .values('kecamatan__kab_kota')  
                    .annotate(t=Sum('jumlah_suara'))
                    .values('t'), output_field=IntegerField()
                ), 0
            ),
            agg_tidak_sah=Coalesce(
                Subquery(
                    RekapSuaraPilegProv.objects.filter(kecamatan__kab_kota=OuterRef('pk'))
                    .values('kecamatan__kab_kota')
                    .annotate(t=Sum('total_suara_tidak_sah'))   
                    .values('t'), output_field=IntegerField()
                ), 0
            ),
            agg_tps=Coalesce(
                Subquery(
                    Kecamatan.objects.filter(kab_kota=OuterRef('pk'))
                    .values('kab_kota')
                    .annotate(t=Sum('tps_pemilu__rekap_tps_pemilu'))
                    .values('t'), output_field=IntegerField()
                ), 0
            ),
            agg_dpt=Coalesce(
                Subquery(
                    Kecamatan.objects.filter(kab_kota=OuterRef('pk'))
                    .values('kab_kota')
                    .annotate(t=Sum('tps_pemilu__rekap_dpt_pemilu'))
                    .values('t'), output_field=IntegerField()
                ), 0
            )
        )

class RekapSuaraPilegProvKab(KabupatenKota):
    objects = RekapSuaraPilegProvKabManager()

    class Meta:
        proxy = True
        verbose_name = "Rekap Suara Kokab"
        verbose_name_plural = "Rekap Suara Kokab"

    @property
    def t_total(self):
        return getattr(self, 'agg_sah', 0) + getattr(self, 'agg_tidak_sah', 0)

    @property
    def pct_sah(self):
        t = self.t_total
        return (getattr(self, 'agg_sah', 0) / t * 100) if t > 0 else 0

    @property
    def pct_tidak_sah(self):
        t = self.t_total
        return (getattr(self, 'agg_tidak_sah', 0) / t * 100) if t > 0 else 0

    @property
    def pct_semua(self):
        dpt = getattr(self, 'agg_dpt', 0)
        return (self.t_total / dpt * 100) if dpt > 0 else 0

    def get_suara_partai(self, partai_id):
        from django.db.models import Sum
        return DetailSuaraPilegProv.objects.filter(
            kecamatan__kab_kota=self, partai_id=partai_id
        ).aggregate(total=Sum('jumlah_suara'))['total'] or 0

class RekapSuaraPilegProvDapilManager(models.Manager):
    def get_queryset(self):
        from django.db.models import Sum, Subquery, OuterRef, IntegerField
        from django.db.models.functions import Coalesce
        from core.models import Kecamatan
        from .models import DetailSuaraPilegProv, RekapSuaraPilegProv
        qs = super().get_queryset()
        return qs.annotate(
            agg_sah=Coalesce(
                Subquery(
                    DetailSuaraPilegProv.objects.filter(
                        kecamatan__kab_kota__dapil_prov=OuterRef('pk')
                    )
                    .values('kecamatan__kab_kota__dapil_prov')
                    .annotate(t=Sum('jumlah_suara'))
                    .values('t'),
                    output_field=IntegerField()
                ), 
                0
            ),
            agg_tidak_sah=Coalesce(
                Subquery(
                    RekapSuaraPilegProv.objects.filter(
                        kecamatan__kab_kota__dapil_prov=OuterRef('pk')
                    )
                    .values('kecamatan__kab_kota__dapil_prov')
                    .annotate(t=Sum('total_suara_tidak_sah'))
                    .values('t'),
                    output_field=IntegerField()
                ),
                0
            ),
            agg_tps=Coalesce(
                Subquery(
                    Kecamatan.objects.filter(
                        kab_kota__dapil_prov=OuterRef('pk')
                    )
                    .values('kab_kota__dapil_prov')
                    .annotate(t=Sum('tps_pemilu__rekap_tps_pemilu'))
                    .values('t'),
                    output_field=IntegerField()
                ),
                0
            ),
            agg_dpt=Coalesce(
                Subquery(
                    Kecamatan.objects.filter(
                        kab_kota__dapil_prov=OuterRef('pk')
                    )
                    .values('kab_kota__dapil_prov')
                    .annotate(t=Sum('tps_pemilu__rekap_dpt_pemilu'))
                    .values('t'),
                    output_field=IntegerField()
                ),
                0
            )
        )

class RekapSuaraPilegProvDapil(DapilProv):
    objects = RekapSuaraPilegProvDapilManager()

    class Meta:
        proxy = True
        verbose_name = "Rekap Suara Dapil"
        verbose_name_plural = "Rekap Suara Dapil"

    @property
    def t_total(self):
        return getattr(self, 'agg_sah', 0) + getattr(self, 'agg_tidak_sah', 0)

    @property
    def pct_sah(self):
        t = self.t_total
        return (getattr(self, 'agg_sah', 0) / t * 100) if t > 0 else 0

    @property
    def pct_tidak_sah(self):
        t = self.t_total
        return (getattr(self, 'agg_tidak_sah', 0) / t * 100) if t > 0 else 0

    @property
    def pct_semua(self):
        dpt = getattr(self, 'agg_dpt', 0)
        return (self.t_total / dpt * 100) if dpt > 0 else 0

    def get_suara_partai(self, partai_id):
        from django.db.models import Sum
        return DetailSuaraPilegProv.objects.filter(
            kecamatan__kab_kota__dapil_prov=self, partai_id=partai_id
        ).aggregate(total=Sum('jumlah_suara'))['total'] or 0