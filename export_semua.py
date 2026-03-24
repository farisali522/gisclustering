import os
import json

# ==============================================================================
# 1. BANGUNKAN MESIN DJANGO 
# ==============================================================================
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webgis_clustering.settings')
import django
django.setup()

from django.core.management import call_command
from geojson.models import KabupatenGeoJSON, KecamatanGeoJSON

def export_tabular():
    output_file = 'backup_data_pemilu.json'
    print(f"📦 [1/3] Memulai proses backup data tabular...")
    with open(output_file, 'w', encoding='utf-8') as f:
        call_command('dumpdata', 'core', 'pilpres', 'pilgub', 'pilwalbup', 'pileg_ri', 'pileg_prov', 'pileg_kokab', format='json', indent=2, stdout=f)
    print(f"✅ [1/3] SUKSES! Data tabular diexport ke '{output_file}'")

def export_kokab():
    print(f"🗺️ [2/3] Memulai proses export peta Kokab...")
    features = []
    for obj in KabupatenGeoJSON.objects.select_related('kabupaten').all():
        if not obj.geojson_data: continue
        geom = obj.geojson_data
        if isinstance(geom, str):
            try: geom = json.loads(geom)
            except: continue
        features.append({"type": "Feature", "properties": {"kode_kokab": obj.kabupaten.kode_kokab, "kabkot": obj.kabupaten.nama_kokab}, "geometry": geom})
    
    with open('backup_peta_kokab.json', 'w', encoding='utf-8') as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False, indent=2)
    print(f"✅ [2/3] SUKSES! {len(features)} peta Kokab diexport.")

def export_kecamatan():
    print(f"🗺️ [3/3] Memulai proses export peta Kecamatan...")
    features = []
    for obj in KecamatanGeoJSON.objects.select_related('kecamatan', 'kecamatan__kab_kota').all():
        if not obj.geojson_data: continue
        geom = obj.geojson_data
        if isinstance(geom, str):
            try: geom = json.loads(geom)
            except: continue
        features.append({"type": "Feature", "properties": {"kabkot": obj.kecamatan.kab_kota.nama_kokab, "kode_kecamatan": obj.kecamatan.kode_kecamatan, "kecamatan": obj.kecamatan.nama_kecamatan}, "geometry": geom})
    
    with open('backup_peta_kecamatan.json', 'w', encoding='utf-8') as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False, indent=2)
    print(f"✅ [3/3] SUKSES! {len(features)} peta Kecamatan diexport.")

if __name__ == '__main__':
    print("🚀 === MEMULAI FULL BACKUP === 🚀")
    export_tabular()
    export_kokab()
    export_kecamatan()
    print("🎉 === FULL BACKUP SELESAI! ===")