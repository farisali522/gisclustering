import os
import json

# ==============================================================================
# 1. BANGUNKAN MESIN DJANGO 
# ==============================================================================
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webgis_clustering.settings')
import django
django.setup()

from core.models import KabupatenKota, Kecamatan
from geojson.models import KabupatenGeoJSON, KecamatanGeoJSON

def load_kokab():
    file_path = 'backup_peta_kokab.json'
    if not os.path.exists(file_path):
        print(f"⚠️ File {file_path} tidak ditemukan. Skip load Kokab.")
        return

    print(f"🚀 Membaca {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    sukses = 0
    for feat in data.get('features', []):
        kode = feat.get('properties', {}).get('kode_kokab')
        geom = feat.get('geometry')
        
        if kode and geom:
            kab = KabupatenKota.objects.filter(kode_kokab=kode).first()
            if kab:
                KabupatenGeoJSON.objects.update_or_create(kabupaten=kab, defaults={'geojson_data': geom})
                sukses += 1
                print(f" ✅ [KOKAB] Peta terpasang via Kode {kode} ({kab.nama_kokab})")
                
    print(f"🎉 Selesai! {sukses} Peta Kokab direstore dengan akurasi 100%.\n")

def load_kecamatan():
    file_path = 'backup_peta_kecamatan.json'
    if not os.path.exists(file_path):
        print(f"⚠️ File {file_path} tidak ditemukan. Skip load Kecamatan.")
        return

    print(f"🚀 Membaca {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    sukses = 0
    for feat in data.get('features', []):
        kode = feat.get('properties', {}).get('kode_kecamatan')
        geom = feat.get('geometry')
        
        if kode and geom:
            kec = Kecamatan.objects.filter(kode_kecamatan=kode).first()
            if kec:
                KecamatanGeoJSON.objects.update_or_create(kecamatan=kec, defaults={'geojson_data': geom})
                sukses += 1
                print(f" ✅ [KECAMATAN] Peta terpasang via Kode {kode} ({kec.nama_kecamatan})")

    print(f"🎉 Selesai! {sukses} Peta Kecamatan direstore dengan akurasi 100%.\n")

if __name__ == '__main__':
    print("🔄 MEMULAI PROSES LOAD PETA (Berbasis Kode Wilayah Unik)...")
    load_kokab()
    load_kecamatan()