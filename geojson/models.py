from django.db import models
from core.models import KabupatenKota, Kecamatan

class KabupatenGeoJSON(models.Model):
    kabupaten = models.OneToOneField(
        KabupatenKota, 
        on_delete=models.CASCADE, 
        related_name='geojson_data',
        verbose_name="Kabupaten/Kota"
    )
    geojson_data = models.JSONField(
        verbose_name="Data GeoJSON Polygon", 
        help_text="Format JSON / Koordinat batas peta. Gunakan format GeoJSON murni tanpa 'FeatureCollection'.",
        null=True, 
        blank=True
    )

    class Meta:
        verbose_name = "Batas Kokab"
        verbose_name_plural = "Batas Kokab"

    def __str__(self):
        return f"Peta Wilayah - {self.kabupaten.nama_kokab}"


class KecamatanGeoJSON(models.Model):
    kecamatan = models.OneToOneField(
        Kecamatan,
        on_delete=models.CASCADE,
        related_name='geojson_data',
        verbose_name="Kecamatan"
    )
    geojson_data = models.JSONField(
        verbose_name="Data GeoJSON Polygon", 
        help_text="Format JSON / Koordinat batas peta. Gunakan format GeoJSON murni tanpa 'FeatureCollection'.",
        null=True, 
        blank=True
    )

    class Meta:
        verbose_name = "Batas Peta Kecamatan"
        verbose_name_plural = "Batas Kecamatan"

    def __str__(self):
        return f"Peta Wilayah - {self.kecamatan.nama_kecamatan}"
