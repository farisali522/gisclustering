import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, davies_bouldin_score
import warnings

# Mengabaikan peringatan untuk kebersihan output
warnings.filterwarnings('ignore')

# ==============================================================================
# TAHAP 1: BUSINESS UNDERSTANDING
# ==============================================================================
print("=== TAHAPAN CRISP-DM 1: BUSINESS UNDERSTANDING ===")
# DEFINISI 12 PARAMETER / FITUR PENELITIAN
fitur_cols = [
    '%_v_pres', '%_v_pileg_ri', '%_v_pileg_prov', '%_v_pileg_kokab',
    '%_v_pilkada_gub', '%_v_pilkada_kokab',
    '%_part_pilpres', '%_part_pileg_ri', '%_part_pileg_prov',
    '%_part_pileg_kab', '%_part_pilkada_gub', '%_part_pilkada_kokab'
]
print(f"[INFO] Fokus: Pemetaan Zonasi Strategis Wilayah (Clustering)")
print(f"[INFO] Total Parameter: {len(fitur_cols)} fitur elektoral.")

# ==============================================================================
# TAHAP 2: DATA UNDERSTANDING
# ==============================================================================
print("\n=== TAHAPAN CRISP-DM 2: DATA UNDERSTANDING ===")

# 1. LOAD DATASET
nama_file_input = 'data_kmeans_clustering.xlsx'
df = pd.read_excel(nama_file_input)

# 2. AUDIT KELENGKAPAN DATA
summary_und = df[fitur_cols].isnull().sum().reset_index()
summary_und.columns = ['Nama Parameter', 'Jumlah Data Kosong']
summary_und['Total Baris'] = len(df)
summary_und['Status'] = 'Data Lengkap'

print("-" * 80)
print("RINGKASAN AUDIT KELENGKAPAN DATA")
print("-" * 80)
print(summary_und.to_string(index=False))
print("-" * 80)

# 3. EXPORT LAPORAN AUDIT
nama_file_t1 = "Kelengkapan_Data_Cleaning.xlsx"
summary_und.to_excel(nama_file_t1, index=False)
print(f"[INFO] Berkas Laporan Tahap 2 telah dihasilkan: {nama_file_t1}")

# ==============================================================================
# TAHAP 3: DATA PREPARATION
# ==============================================================================
print("\n=== TAHAPAN CRISP-DM 3: DATA PREPARATION ===")

# 1. PROSES NORMALISASI Z-SCORE
scaler = StandardScaler()
X_scaled = scaler.fit_transform(df[fitur_cols])

# 2. PENYUSUNAN KEMBALI DATAFRAME TERSTANDARISASI
df_final = pd.DataFrame(X_scaled, columns=fitur_cols)
df_final.insert(0, 'nama_kecamatan', df['nama_kecamatan'].values)
df_final.insert(0, 'kab_kota', df['kab_kota'].values)
df_final.insert(0, 'id_kec', df['id_kec'].values)

# 3. PENGECEKAN HASIL (SAMPEL 10 DATA)
sampel_10 = df_final.sample(n=10, random_state=42)
print("-" * 140)
print("TAMPILAN SAMPEL DATA HASIL STANDARISASI (Z-SCORE)")
print("-" * 140)
print(sampel_10.to_string(index=False))
print("-" * 140)

# 4. EXPORT DATA HASIL PREPARASI
nama_file_t2 = "Hasil_Normalisasi_ZScore.xlsx"
df_final.to_excel(nama_file_t2, index=False)
print(f"[INFO] Berkas Laporan Tahap 3 telah dihasilkan: {nama_file_t2}")

# ==============================================================================
# TAHAP 4: MODELING
# ==============================================================================
print("\n=== TAHAPAN CRISP-DM 4: MODELING ===")

# 1. PERHITUNGAN VALIDASI K-OPTIMAL (RANGE 2-10)
k_range = range(2, 11)
list_sse, list_silhouette, list_dbi = [], [], []

print("Sedang memproses perhitungan validasi otomatis...")
print("-" * 75)

for k in k_range:
    kmeans_val = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans_val.fit_predict(X_scaled)
    list_sse.append(kmeans_val.inertia_)
    list_silhouette.append(silhouette_score(X_scaled, labels))
    list_dbi.append(davies_bouldin_score(X_scaled, labels))
    
    # Tabel angka print di layar
    print(f"K={k:2d} | SSE:{list_sse[-1]:,.0f} | Silh:{list_silhouette[-1]:.3f} | DBI:{list_dbi[-1]:.3f}")

print("-" * 75)

# --- EXPORT HASIL PENGUJIAN KE EXCEL ---
df_val_excel = pd.DataFrame({
    'K': list(k_range), 'SSE': list_sse, 'Silhouette': list_silhouette, 'DBI': list_dbi
})
df_val_excel.to_excel("Hasil_Validasi_Modeling_K.xlsx", index=False)
print(f"[INFO] Laporan Validasi Tahap 4 (Angka) telah dicetak.")

# --- VISUALISASI GRAFIK VALIDASI ---

# Grafik 1: Elbow Method
plt.figure(figsize=(10, 5))
plt.plot(k_range, list_sse, marker='o', color='#1f77b4', linewidth=2)
plt.ylim(min(list_sse)*0.85, max(list_sse)*1.20) 
for i, val in enumerate(list_sse):
    plt.annotate(f'{val:,.0f}', (list(k_range)[i], list_sse[i]), 
                 ha='center', va='bottom', fontweight='bold', textcoords="offset points", xytext=(0,10))
plt.title('Grafik Elbow Method (SSE)', fontweight='bold', pad=25)
plt.xlabel('Jumlah Klaster (K)')
plt.grid(True, alpha=0.3)
plt.savefig("Grafik_Elbow_Method.png", dpi=100)
plt.close()

# Grafik 2: Silhouette Score
plt.figure(figsize=(10, 5))
plt.plot(k_range, list_silhouette, marker='s', color='#2ca02c', linewidth=2)
plt.ylim(min(list_silhouette)*0.85, max(list_silhouette)*1.25)
for i, val in enumerate(list_silhouette):
    plt.annotate(f'{val:.3f}', (list(k_range)[i], list_silhouette[i]), 
                 ha='center', va='bottom', fontweight='bold', textcoords="offset points", xytext=(0,10))
plt.title('Grafik Silhouette Score', fontweight='bold', pad=25)
plt.xlabel('Jumlah Klaster (K)')
plt.grid(True, alpha=0.3)
plt.savefig("Grafik_Silhouette_Score.png", dpi=100)
plt.close()

# Grafik 3: Davies-Bouldin Index
plt.figure(figsize=(10, 5))
plt.plot(k_range, list_dbi, marker='D', color='#d62728', linewidth=2)
plt.ylim(min(list_dbi)*0.85, max(list_dbi)*1.25)
for i, val in enumerate(list_dbi):
    plt.annotate(f'{val:.3f}', (list(k_range)[i], list_dbi[i]), 
                 ha='center', va='bottom', fontweight='bold', textcoords="offset points", xytext=(0,10))
plt.title('Grafik Davies-Bouldin Index', fontweight='bold', pad=25)
plt.xlabel('Jumlah Klaster (K)')
plt.grid(True, alpha=0.3)
plt.savefig("Grafik_DBI_Index.png", dpi=100)
plt.close()

print("[INFO] Tiga grafik validasi (Elbow, Silhouette, DBI) telah disimpan.")

# 2. EKSEKUSI K-MEANS FINAL
k_final = 4
print(f"\n[INFO] Menjalankan K-Means Final dengan K={k_final}...")
kmeans_final = KMeans(n_clusters=k_final, random_state=42, n_init=10)
df['Cluster_Label'] = kmeans_final.fit_predict(X_scaled)
print(f"[INFO] Proses Clustering selesai.")

# ==============================================================================
# TAHAP 5: EVALUATION
# ==============================================================================
print("\n=== TAHAPAN CRISP-DM 5: EVALUATION ===")

# 1. REKAPITULASI DISTRIBUSI WILAYAH
dist = df['Cluster_Label'].value_counts().sort_index().reset_index()
dist.columns = ['Label Klaster', 'Jumlah Kecamatan']
dist['Persentase (%)'] = (dist['Jumlah Kecamatan'] / len(df) * 100).round(2)

baris_total = pd.DataFrame({
    'Label Klaster': ['Total'],
    'Jumlah Kecamatan': [dist['Jumlah Kecamatan'].sum()],
    'Persentase (%)': [100.0]
})
tabel_distribusi_final = pd.concat([dist, baris_total], ignore_index=True)

print("=== REKAPITULASI DISTRIBUSI SEBARAN KLASTER ===")
print("-" * 65)
print(tabel_distribusi_final.to_string(index=False))
print("-" * 65)

# 2. ANALISIS KARAKTERISTIK (PROFILING CENTROID)
tabel_profiling = df.groupby('Cluster_Label')[fitur_cols].mean().round(2)
tabel_profiling.insert(0, 'Jumlah_Kecamatan', df['Cluster_Label'].value_counts().sort_index())

tabel_profiling = tabel_profiling.reset_index()
tabel_profiling.rename(columns={'Cluster_Label': 'Label_Klaster'}, inplace=True)

print("=== TABEL EVALUASI PROFIL KARAKTERISTIK (CENTROID TAHAP 5) ===")
print("-" * 155)
print(tabel_profiling.to_string(index=False))
print("-" * 155)

# 3. VISUALISASI SEBARAN KLASTER (PCA)
pca = PCA(n_components=2)
X_pca = pca.fit_transform(X_scaled)
acc_pca = np.sum(pca.explained_variance_ratio_) * 100

df_pca = pd.DataFrame(X_pca, columns=['PC1', 'PC2'])
df_pca['Cluster'] = df['Cluster_Label'].astype(str)

plt.figure(figsize=(10, 7))
sns.set_theme(style="whitegrid", palette="muted")
sns.scatterplot(x='PC1', y='PC2', hue='Cluster', data=df_pca,
                palette='tab10', s=100, alpha=0.9, edgecolor='white', linewidth=1)

plt.title(f'Visualisasi Sebaran 5 Klaster Wilayah (K={k_final})\n(Representasi Informasi Data: {acc_pca:.2f}%)',
          fontsize=14, fontweight='bold', pad=15)
plt.xlabel('Principal Component 1 (PC1)', fontweight='bold', fontsize=11)
plt.ylabel('Principal Component 2 (PC2)', fontweight='bold', fontsize=11)
plt.legend(title='Zona Klaster', bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=10)
plt.grid(True, linestyle='--', alpha=0.6)
plt.tight_layout()
plt.savefig(f"Visualisasi_Sebaran_K{k_final}.png", dpi=100)
plt.close()

# 4. VISUALISASI HEATMAP (UKURAN STANDAR / NORMAL)
prof_norm = (tabel_profiling[fitur_cols] - tabel_profiling[fitur_cols].min()) / \
            (tabel_profiling[fitur_cols].max() - tabel_profiling[fitur_cols].min())

plt.figure(figsize=(12, 6)) 
sns.heatmap(prof_norm, annot=tabel_profiling[fitur_cols], fmt=".2f", 
            cmap="YlGnBu", linewidths=.5, cbar=False, annot_kws={"size": 10, "weight": "bold"})

plt.title(f'Heatmap Karakteristik 12 Parameter per Klaster (K={k_final})', 
          fontsize=14, fontweight='bold', pad=20)
plt.xlabel('12 Parameter Penelitian', fontweight='bold', fontsize=11)
plt.ylabel('Nomor Klaster', fontweight='bold', fontsize=11)
plt.xticks(rotation=45, ha='right', fontsize=10)
plt.tight_layout()
plt.savefig(f"Heatmap_Karakteristik_K{k_final}.png", dpi=100)
plt.close()

print(f"[INFO] Visualisasi Sebaran & Heatmap telah disimpan sebagai file PNG.")

# ==============================================================================
# TAHAP 6: DEPLOYMENT
# ==============================================================================
print("\n=== TAHAPAN CRISP-DM 6: DEPLOYMENT ===")

# 1. EXPORT SELURUH LAPORAN AKHIR
nama_file_t4 = f"Hasil_Distribusi_Zonasi_K{k_final}.xlsx"
nama_file_profil = f"Evaluasi_Profiling_Centroid_K{k_final}.xlsx"
nama_file_master = f"Master_Data_Berlabel_Final_K{k_final}.xlsx"

tabel_distribusi_final.to_excel(nama_file_t4, index=False)
tabel_profiling.to_excel(nama_file_profil, index=False)
df.to_excel(nama_file_master, index=False)

# 2. IDENTIFIKASI KECAMATAN OUTLIER (BERDARKAN PC2 TERTINGGI)
idx_outlier = df_pca['PC2'].idxmax()
info_kecamatan = df.iloc[[idx_outlier]]

print("=== IDENTITAS KECAMATAN DENGAN PERFORMA EKSTRIM (OUTLIER) ===")
print("-" * 110)
print(info_kecamatan[['id_kec', 'kab_kota', 'nama_kecamatan', 'Cluster_Label']].to_string(index=False))
print("-" * 110)

# Bedah detail 12 parameter asli (Transpose secara vertikal)
print("\n=== DETAIL 12 PARAMETER PENELITIAN KECAMATAN INI ===")
print("-" * 75)
detail_param = info_kecamatan[fitur_cols].T.reset_index()
detail_param.columns = ['Nama Parameter', 'Nilai Persentase Asli (%)']
print(detail_param.to_string(index=False))
print("-" * 75)

# 3. EXPORT HASIL ANALISIS KHUSUS
nama_file_outlier = "Analisis_Khusus_Kecamatan_Ekstrem.xlsx"
info_kecamatan.to_excel(nama_file_outlier, index=False)

print(f"\n[INFO] Berkas Laporan Akhir Berhasil Dihasilkan:")
print(f"1. {nama_file_master} (Data Utama)")
print(f"2. {nama_file_outlier} (Studi Kasus Ekstrem)")
print(f"3. {nama_file_profil} (Profil Centroid)")
print(f"4. {nama_file_t4} (Rekap Distribusi)")

print("\n" + "="*80)
print("=== SELURUH TAHAPAN CRISP-DM TELAH SELESAI SECARA UTUH DAN LENGKAP ===")
print("="*80)
