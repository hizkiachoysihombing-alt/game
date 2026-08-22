# Source Library dan Question Review

ElectroQuest menyimpan metadata source di PostgreSQL dan isi file di penyimpanan privat. File tidak pernah diletakkan pada direktori publik frontend dan tidak dikirim ke Git.

## Alur source

1. Instruktur atau admin mengunggah PDF/DOCX di **Studio → Sources**.
2. File divalidasi, dihitung SHA-256, lalu disimpan sebagai blob immutable. Blob yang sama tidak disalin dua kali.
3. Pengunggah memilih mata kuliah, topik, jenis dokumen, atribusi, dan status hak penggunaan.
4. Source masuk `inbox`, dikirim ke `review_pending`, lalu diterbitkan oleh tindakan manusia.
5. Hanya source `published` yang terlihat oleh mahasiswa. Source tidak dihapus; versi baru ditambahkan dan versi lama tetap tersedia untuk menjaga sitasi soal.
6. Source yang tidak berlaku dipindahkan ke `archived` dan dapat dipulihkan ke Inbox.

## Alur soal

1. Soal manual maupun hasil AI selalu dibuat sebagai `draft`.
2. Soal baru menyimpan sitasi ke versi source yang tetap, beserta halaman atau bagian yang tepat.
3. Instruktur mengirim draft ke `pending_review`; reviewer menyetujui atau meminta perubahan.
4. Hanya soal `approved` yang dapat diterbitkan. Journey hanya menggunakan soal dengan status workflow `published` dan `is_published=true`.
5. Sesudah jawaban diperiksa, mahasiswa mendapat tautan kembali ke source dan halaman yang relevan.

Generator AI bersifat opsional. Isi `OPENAI_API_KEY` dan `OPENAI_MODEL` untuk mengaktifkannya. Tanpa kedua nilai itu, upload, draft manual, review, publikasi, Journey, dan seluruh Source Library tetap berfungsi.

## Penyimpanan

Mode lokal untuk development:

```env
SOURCE_STORAGE_BACKEND=local
SOURCE_LOCAL_ROOT=./source_storage
SOURCE_MAX_UPLOAD_BYTES=52428800
```

`source_storage/` dan `source_materials/` diabaikan Git. Docker memakai volume privat yang writable untuk upload baru serta mount read-only untuk kumpulan legacy.

Mode S3-compatible untuk production (AWS S3, Cloudflare R2, atau MinIO):

```env
SOURCE_STORAGE_BACKEND=s3
S3_ENDPOINT_URL=https://example.r2.cloudflarestorage.com
S3_REGION=auto
S3_BUCKET=electroquest-private
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
```

Bucket harus private. Backend memeriksa autentikasi dan mem-proxy file; jangan membuat bucket atau object URL menjadi publik.

## Menambah source kemudian

Cara utama adalah melalui **Studio → Sources → Upload source**. Ini tidak memerlukan perubahan kode atau restart aplikasi. Pilih **Tambah versi** jika file baru menggantikan dokumen lama; pilih upload source baru jika dokumennya berbeda.

Manifest lama dapat diimpor berulang kali dengan aman:

```bash
cd backend
python -m alembic upgrade head
python -m app.commands.import_legacy_sources
```

Import menggunakan hash dan identitas manifest sehingga file yang sudah ada dilewati. Untuk menjaga tampilan yang sebelumnya sudah digunakan, source legacy pertama kali diimpor sebagai `published`; semua upload baru masuk `inbox`.

## Operasional

- Jalankan `alembic upgrade head` sebelum backend versi baru dimulai.
- Cadangkan PostgreSQL dan bucket/volume source bersama-sama.
- Jangan menyimpan API key atau credential storage di repository.
- Arsipkan dokumen; jangan menimpa blob atau menghapus versi yang sudah disitasi.
- Periksa laporan mahasiswa dari halaman detail source di Studio.
