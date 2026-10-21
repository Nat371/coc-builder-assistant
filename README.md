# coc-builder-assistant

Build APK Android melalui GitHub Actions:
1. Buka tab Actions.
2. Pilih workflow Build Android APK.
3. Tekan Run workflow pada branch main.
4. Unduh artifact CoCBuilderAssistant-APK setelah build berhasil.

Catatan: langkah ini membangun APK dari source ZIP yang sudah ada; belum menambahkan fitur Auto Attack.

## Auto Attack scaffold (tahap awal)

Branch `feature/auto-attack-accessibility` menambahkan kerangka layanan Android Accessibility dan panel Start/Stop untuk pengujian.

**Penting:** ini belum merupakan Auto Attack penuh. Fitur OCR/pengenalan base, pengenalan pasukan, perencanaan serangan, dan tap penempatan pasukan belum dibuat. Tombol Start saat ini hanya menguji perubahan status; jangan menganggapnya menjalankan serangan.

Untuk mencoba build tahap awal:
1. Buka tab **Actions**.
2. Pilih workflow **Build Android APK**.
3. Tekan **Run workflow** dan pilih branch `feature/auto-attack-accessibility`.
4. Jika build berhasil, unduh artifact `CoCBuilderAssistant-APK`.

Aktifkan layanan Accessibility hanya jika memahami izin yang diminta. Uji tahap ini di luar pertandingan langsung terlebih dahulu.
