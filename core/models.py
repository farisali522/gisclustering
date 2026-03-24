import os
import uuid
from django.db import models

def path_logo_unik(instance, filename):
    ext = filename.split('.')[-1]
    return os.path.join('logos/', f"{instance.no_urut_partai}_{uuid.uuid4().hex[:8]}.{ext}")

class KabupatenKota(models.Model):
    kode_kokab = models.CharField(max_length=10, unique=True, verbose_name="Kode Kab/Kota")
    nama_kokab = models.CharField(max_length=100, unique=True, verbose_name="Nama Kab/Kota")

    def __str__(self):
        return self.nama_kokab

    class Meta:
        verbose_name_plural = "Kabupaten Kota"
        ordering = ['nama_kokab']

class Kecamatan(models.Model):
    kab_kota = models.ForeignKey(KabupatenKota, on_delete=models.CASCADE, related_name='kecamatans', verbose_name="Kabupaten")
    kode_kecamatan = models.CharField(max_length=10, unique=True, verbose_name="Kode Kecamatan")
    nama_kecamatan = models.CharField(max_length=100, verbose_name="Nama Kecamatan")

    def __str__(self):
        return self.nama_kecamatan

    class Meta:
        unique_together = ('kab_kota', 'nama_kecamatan')
        verbose_name_plural = "Kecamatan"
        ordering = ['kab_kota', 'nama_kecamatan']

class TpsDptPemilu(models.Model):
    kecamatan = models.OneToOneField(Kecamatan, on_delete=models.CASCADE, related_name='tps_pemilu')
    rekap_tps_pemilu = models.IntegerField(default=0, verbose_name="TPS Pemilu")
    rekap_dpt_pemilu = models.IntegerField(default=0, verbose_name="DPT Pemilu")

    def __str__(self):
        return self.kecamatan.nama_kecamatan

    class Meta:
        verbose_name_plural = "TPS & DPT Pemilu"

class TpsDptPilkada(models.Model):
    kecamatan = models.OneToOneField(Kecamatan, on_delete=models.CASCADE, related_name='tps_pilkada')
    rekap_tps_pilkada = models.IntegerField(default=0, verbose_name="TPS Pilkada")
    rekap_dpt_pilkada = models.IntegerField(default=0, verbose_name="DPT Pilkada")

    def __str__(self):
        return self.kecamatan.nama_kecamatan

    class Meta:
        verbose_name_plural = "TPS & DPT Pilkada"

class HasilClustering(models.Model):
    kecamatan = models.OneToOneField(Kecamatan, on_delete=models.CASCADE, related_name='clustering')
    label_cluster = models.IntegerField(default=0, verbose_name="Cluster")

    def __str__(self):
        return f"C{self.label_cluster} - {self.kecamatan.nama_kecamatan}"

    class Meta:
        verbose_name_plural = "Hasil Clustering"

class Partai(models.Model):
    nama_partai = models.CharField(max_length=100, verbose_name="Nama Partai")
    no_urut_partai = models.IntegerField(unique=True, verbose_name="Nomor Urut")
    logo_partai = models.ImageField(upload_to=path_logo_unik, null=True, blank=True)
    warna_partai = models.CharField(max_length=7, default='#808080', verbose_name="Warna")

    def __str__(self):
        return f"{self.no_urut_partai}. {self.nama_partai}"

    class Meta:
        verbose_name_plural = "Partai"
        ordering = ['no_urut_partai']
