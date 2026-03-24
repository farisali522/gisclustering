import os
import uuid
from django.db import models
from core.models import Kecamatan, Partai, KabupatenKota

def path_dan_nama_unik_walbup(instance, filename):
    extension = filename.split('.')[-1]
    # Folder dipisah per Kabupaten biar rapi
    nama_baru = f"{instance.no_urut_paslon}_{uuid.uuid4().hex[:8]}.{extension}"
    return os.path.join(f'paslon_walbup/{instance.kab_kota.nama_kokab}/', nama_baru)

class PaslonWalbup(models.Model):
    kab_kota = models.ForeignKey(KabupatenKota, on_delete=models.CASCADE, related_name='paslon_walbup', verbose_name="Kabupaten/Kota")
    no_urut_paslon = models.IntegerField(verbose_name="Nomor Urut")
    nama_calon = models.CharField(max_length=100, verbose_name="Nama Bupati/Walikota")
    nama_wakil = models.CharField(max_length=100, verbose_name="Nama Wakil")
    foto_paslon = models.ImageField(upload_to=path_dan_nama_unik_walbup, null=True, blank=True, verbose_name="Foto Paslon")
    warna_hex = models.CharField(max_length=7, default='#808080', verbose_name="Warna")

    def __str__(self):
        return f"[{self.kab_kota.nama_kokab}] {self.no_urut_paslon}. {self.nama_calon}"

    class Meta:
        verbose_name_plural = "Paslon Pilwalbup"
        ordering = ['kab_kota', 'no_urut_paslon']
        unique_together = ('kab_kota', 'no_urut_paslon') # Satu kabupaten gak boleh ada no urut sama

class KoalisiWalbup(models.Model):
    paslon = models.ForeignKey(PaslonWalbup, on_delete=models.CASCADE, related_name='partai_pendukung', verbose_name="Paslon")
    partai = models.ForeignKey(Partai, on_delete=models.CASCADE, verbose_name="Partai")
    # Field pembantu untuk kunci keunikan per wilayah
    kab_kota = models.ForeignKey(KabupatenKota, on_delete=models.CASCADE, editable=False)

    def save(self, *args, **kwargs):
        self.kab_kota = self.paslon.kab_kota
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.kab_kota.nama_kokab}] {self.partai.nama_partai} -> {self.paslon.nama_calon}"

    class Meta:
        verbose_name_plural = "Data Koalisi Pilwalbup"
        unique_together = ('kab_kota', 'partai') # PENGUNCI: Partai hanya bisa satu kali per Kab/Kota

class RekapSuaraWalbup(models.Model):
    kecamatan = models.OneToOneField(Kecamatan, on_delete=models.CASCADE, related_name='rekap_pilwalbup', verbose_name="Kecamatan")
    total_suara_tidak_sah = models.IntegerField(default=0, verbose_name="Total Suara Tidak Sah")

    @property
    def total_suara_sah(self):
        return sum(ds.jumlah_suara for ds in self.kecamatan.detail_pilwalbup.all())

    @property
    def total_semua_suara(self):
        return self.total_suara_sah + self.total_suara_tidak_sah

    def get_suara_paslon(self, paslon):
        for ds in self.kecamatan.detail_pilwalbup.all():
            if ds.paslon_id == paslon.id:
                return ds.jumlah_suara
        return 0

    def get_persentase_paslon_str(self, paslon):
        suara = self.get_suara_paslon(paslon)
        sah = self.total_suara_sah
        pct = (suara / sah * 100) if sah > 0 else 0
        return f"{pct:.2f}"

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
            # Menggunakan relasi ke TPS Pilkada karena Pilwalbup biasanya barengan
            dpt = self.kecamatan.tps_pilkada.rekap_dpt_pilkada
            pct = (self.total_semua_suara / dpt * 100) if dpt > 0 else 0
            return f"{pct:.2f}"
        except:
            return "0.00"

    def __str__(self):
        return str(self.kecamatan)

    class Meta:
        verbose_name_plural = "Rekap Suara Kecamatan"

class DetailSuaraWalbup(models.Model):
    kecamatan = models.ForeignKey(Kecamatan, on_delete=models.CASCADE, related_name='detail_pilwalbup', verbose_name="Kecamatan")
    paslon = models.ForeignKey(PaslonWalbup, on_delete=models.CASCADE, related_name='suara_wilayah', verbose_name="Paslon")
    jumlah_suara = models.IntegerField(default=0, verbose_name="Jumlah Suara")

    def __str__(self):
        return f"{self.paslon.no_urut_paslon} - {self.kecamatan.nama_kecamatan}"

    class Meta:
        verbose_name_plural = "Data Detail Suara Pilwalbup"
        unique_together = ('kecamatan', 'paslon')

from django.db.models import Sum

class RekapKokabPilwalbupManager(models.Manager):
    def get_queryset(self):
        from django.db.models import Sum, Subquery, OuterRef, IntegerField
        from django.db.models.functions import Coalesce
        from core.models import Kecamatan
        from .models import DetailSuaraWalbup, RekapSuaraWalbup
        qs = super().get_queryset()
        return qs.annotate(
            agg_sah=Coalesce(
                Subquery(
                    DetailSuaraWalbup.objects.filter(kecamatan__kab_kota=OuterRef('pk'))
                    .values('kecamatan__kab_kota')
                    .annotate(t=Sum('jumlah_suara'))
                    .values('t'), output_field=IntegerField()
                ), 0
            ),
            agg_tidak_sah=Coalesce(
                Subquery(
                    RekapSuaraWalbup.objects.filter(kecamatan__kab_kota=OuterRef('pk'))
                    .values('kecamatan__kab_kota')
                    .annotate(t=Sum('total_suara_tidak_sah'))
                    .values('t'), output_field=IntegerField()
                ), 0
            ),
            agg_tps=Coalesce(
                Subquery(
                    Kecamatan.objects.filter(kab_kota=OuterRef('pk'))
                    .values('kab_kota')
                    .annotate(t=Sum('tps_pilkada__rekap_tps_pilkada'))
                    .values('t'), output_field=IntegerField()
                ), 0
            ),
            agg_dpt=Coalesce(
                Subquery(
                    Kecamatan.objects.filter(kab_kota=OuterRef('pk'))
                    .values('kab_kota')
                    .annotate(t=Sum('tps_pilkada__rekap_dpt_pilkada'))
                    .values('t'), output_field=IntegerField()
                ), 0
            )
        )

class RekapKokabPilwalbup(KabupatenKota):
    objects = RekapKokabPilwalbupManager()

    class Meta:
        proxy = True
        verbose_name = "Rekap Kabupaten"
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

    def get_total_suara_paslon(self, paslon):
        from django.db.models import Sum
        return DetailSuaraWalbup.objects.filter(
            kecamatan__kab_kota=self, paslon=paslon
        ).aggregate(total=Sum('jumlah_suara'))['total'] or 0