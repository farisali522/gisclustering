import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, davies_bouldin_score

# ==============================================================================
# KONSTANTA GLOBAL (Visual & Config)
# ==============================================================================

CLUSTER_COLORS = {
    0: '#6366f1', 1: '#ef4444', 2: '#10b981', 3: '#3b82f6', 4: '#eab308',
    5: '#8b5cf6', 6: '#f472b6', 7: '#0ea5e9', 8: '#f97316', 9: '#14b8a6'
}

# ==============================================================================
# MESIN ANALITIK CLUSTERING (Clustering Analytical Engine)
# ==============================================================================

class ClusteringEngine:
    """
    Kapsul untuk semua logika matematika dan evaluasi clustering.
    Disusun sesuai urutan alur dokumentasi sistem.
    """

    # --------------------------------------------------------------------------
    # BAGIAN 1: Z-SCORE NORMALIZATION (Standarisasi Data)
    # --------------------------------------------------------------------------
    @staticmethod
    def scale_data(df, attributes):
        """
        Melakukan Normalisasi Z-Score: z = (x - mu) / sigma.
        Agar semua parameter pemilu berada dalam rentang skala yang seragam.
        """
        if df.empty: return None
        X = df[attributes]
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        return np.round(X_scaled, 3)

    # --------------------------------------------------------------------------
    # BAGIAN 2: ELBOW METHOD (SSE / Inersi)
    # --------------------------------------------------------------------------
    @staticmethod
    def calculate_inertia(X_scaled, k_min=2, k_max=10):
        """
        Menghitung SSE (Sum of Squared Errors) untuk rentang K tertentu.
        Hasilnya digunakan untuk menentukan 'Siku' (Elbow) sebagai K-Optimal.
        """
        if X_scaled is None: return []
        distortions = []
        for k in range(k_min, k_max + 1):
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            kmeans.fit(X_scaled)
            distortions.append({'k': k, 'sse': float(kmeans.inertia_)})
        return distortions

    # --------------------------------------------------------------------------
    # BAGIAN 3: SILHOUETTE SCORE (Kerapatan Cluster)
    # --------------------------------------------------------------------------
    @staticmethod
    def calculate_silhouette(X_scaled, labels):
        """
        Menghitung skor Silhouette (s = (b - a) / max(a, b)).
        Menilai seberapa dekat data dengan clusternya dibanding cluster lain.
        """
        if X_scaled is None or len(np.unique(labels)) < 2: return 0.0
        return float(silhouette_score(X_scaled, labels))

    # --------------------------------------------------------------------------
    # BAGIAN 4: DAVIES-BOULDIN INDEX (Pemisahan Cluster)
    # --------------------------------------------------------------------------
    @staticmethod
    def calculate_dbi(X_scaled, labels):
        """
        Menghitung Davies-Bouldin Index (R = (s_i + s_j) / d_ij).
        Menilai tingkat keterpisahan antar cluster (Semakin kecil semakin baik).
        """
        if X_scaled is None or len(np.unique(labels)) < 2: return 0.0
        return float(davies_bouldin_score(X_scaled, labels))

    # --------------------------------------------------------------------------
    # BAGIAN 5: K-MEANS ALGORITHM (Pengelompokan Data)
    # --------------------------------------------------------------------------
    @staticmethod
    def run_kmeans(X_scaled, k_clusters=5):
        """
        Eksekusi inti Algoritma K-Means Clustering.
        Mengelompokkan data ke dalam K cluster berdasarkan centroid terdekat.
        """
        if X_scaled is None: return None
        kmeans = KMeans(n_clusters=k_clusters, random_state=42, n_init=10)
        return kmeans.fit_predict(X_scaled)

    # --------------------------------------------------------------------------
    # BAGIAN 6: PCA PROJECTION (Visualisasi 2D)
    # --------------------------------------------------------------------------
    @staticmethod
    def get_pca_projection(X_scaled, labels, df_meta, cluster_info=None):
        """
        Reduksi dimensi fitur menjadi 2D (X & Y) menggunakan PCA.
        Digunakan untuk visualisasi Scatter Plot di Dashboard.
        """
        if X_scaled is None: return [], 0
        pca = PCA(n_components=2)
        X_pca = pca.fit_transform(X_scaled)
        acc_pca = float(np.sum(pca.explained_variance_ratio_) * 100)
        pca_data = []
        for i in range(len(X_pca)):
            cid = int(labels[i])
            c_style = (cluster_info or {}).get(cid, {'name': f'Klaster {cid}', 'color': '#94a3b8'})
            pca_data.append({
                'x': round(float(X_pca[i, 0]), 4),
                'y': round(float(X_pca[i, 1]), 4),
                'label': cid,
                'name': df_meta.iloc[i]['kecamatan'],
                'kab': df_meta.iloc[i]['kab_kota'],
                'cluster_name': c_style.get('name', f'Klaster {cid}'),
                'color': c_style.get('color', '#94a3b8')
            })
        return pca_data, acc_pca

    # --------------------------------------------------------------------------
    # BAGIAN 7: HEAT MAP DATA (Centroid Profiling)
    # --------------------------------------------------------------------------
    @staticmethod
    def get_centroid_data(df, attributes, labels):
        """
        Menghitung rata-rata (mean) tiap atribut per cluster.
        Hasilnya digunakan untuk visualisasi Peta Panas (Heat Map) Karakteristik.
        """
        if df.empty: return []
        df_labeled = df.copy()
        df_labeled['cluster_label'] = labels
        centroids = []
        for cid in sorted(df_labeled['cluster_label'].unique()):
            cluster_df = df_labeled[df_labeled['cluster_label'] == cid]
            means = cluster_df[attributes].mean().round(3).to_dict()
            centroids.append({'cluster': int(cid), 'means': means})
        return centroids

    # --------------------------------------------------------------------------
    # BAGIAN TAMBAHAN: ORKESTRASI VALIDASI (Untuk UI)
    # --------------------------------------------------------------------------
    @staticmethod
    def run_clustering_validation(X_scaled, k_min=2, k_max=10):
        """
        Fungsi orkestrasi untuk menjalankan seluruh metrik validasi sekaligus.
        """
        if X_scaled is None: return []
        results = []
        for k in range(k_min, k_max + 1):
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(X_scaled)
            results.append({
                'k': k,
                'sse': float(kmeans.inertia_),
                'silhouette': ClusteringEngine.calculate_silhouette(X_scaled, labels),
                'dbi': ClusteringEngine.calculate_dbi(X_scaled, labels)
            })
        return results
