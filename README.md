# WebGIS Clustering Dashboard Pemilu

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2+-green.svg)](https://www.djangoproject.com/)
[![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-Latest-orange.svg)](https://scikit-learn.org/)

## 📌 Ikhtisar Proyek
Proyek ini merupakan sistem **Dashboard WebGIS** terintegrasi yang dirancang untuk melakukan segmentasi wilayah (Kecamatan) berdasarkan performa elektoral dan tingkat partisipasi pemilih. Menggunakan pendekatan **Machine Learning (K-Means Clustering)**, sistem ini membantu pemangku kepentingan dalam memetakan zonasi strategis wilayah secara objektif dan berbasis data.

---

## 🔬 Metodologi Penelitian (CRISP-DM)
Penelitian ini mengikuti kerangka kerja standar industri **CRISP-DM** (*Cross-Industry Standard Process for Data Mining*):

1.  **Business & Data Understanding**: Identifikasi 13 parameter utama (6 Perolehan Suara & 7 Partisipasi Pemilih).
2.  **Data Preparation**: Normalisasi data menggunakan *Z-Score Scaling* untuk menyamakan skala antar fitur.
3.  **Modeling**: Eksperimen penentuan nilai K optimal menggunakan *Elbow Method*, *Silhouette Score*, dan *Davies-Bouldin Index*.
4.  **Evaluation**: Analisis profil karakteristik klaster, visualisasi *Heatmap*, dan reduksi dimensi menggunakan **PCA (Principal Component Analysis)** untuk identifikasi **Titik Terluar (Boundary Indicators)**.

---

## 🚀 Fitur Utama
-   **Geospatial Dashboard**: Visualisasi sebaran klaster wilayah menggunakan peta interaktif (GeoJSON & Leaflet).
-   **Advanced Clustering Logic**: Mesin cerdas berbasis Scikit-Learn untuk pengelompokan wilayah otomatis.
-   **Profiling & Heatmap**: Pemetaan karakteristik unik tiap klaster (Zonasi Menang vs Zonasi Partisipasi).
-   **PCA Boundary Analysis**: Identifikasi kecamatan rujukan yang menjadi indikator batas terluar setiap kuadran.
-   **Automated Reporting**: Ekspor seluruh hasil analisis ke format profesional Microsoft Excel.

---

## 🛠️ Stack Teknologi
-   **Backend**: Python 3.11, Django Framework.
-   **Data Science**: Scikit-Learn, Pandas, NumPy.
-   **Visualisasi**: Matplotlib, Seaborn (Heatmap), Leaflet.js (GIS).
-   **Database**: SQLite (Development) / PostgreSQL.
-   **UI/UX**: Bootstrap, Jazzmin Admin Theme.

---

## 📂 Struktur Repositori
-   `/clustering/`: Modul penelitian utama (Notebook `.ipynb` & Script `.py`).
-   `/core/`: Pengaturan inti proyek Django.
-   `/geojson/`: Data spasial batas wilayah kecamatan.
-   `/templates/`: Halaman UI Dashboard & Visualisasi.
-   `apps/`: Berbagai aplikasi elektoral (`pilpres`, `pilgub`, `pileg`, dll).

---

## 💻 Cara Instalasi

1.  **Clone Repositori**:
    ```bash
    git clone https://github.com/farisali522/gisclustering.git
    cd gisclustering
    ```

2.  **Siapkan Environment**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # atau venv\Scripts\activate di Windows
    pip install -r requirements.txt
    ```

3.  **Migrasi Database**:
    ```bash
    python manage.py migrate
    python manage.py load_data_pemilu.py  # Jika ada skrip import data
    ```

4.  **Jalankan Server**:
    ```bash
    python manage.py runserver
    ```

---

## 📊 Hasil Analisis (Preview)
| Visualisasi PCA Terluar | Heatmap Karakteristik |
| :---: | :---: |
| ![PCA](./clustering/Visualisasi_PCA_Fokus_Indikator%20Batas.png) | ![Heatmap](./clustering/Visualisasi_PCA_K5.png) |

---

## 📝 Lisensi
Proyek ini dikembangkan untuk tujuan penelitian elektoral dan analisis data wilayah.

**Kontak Peneliti**: [Informasi Kontak Anda]
