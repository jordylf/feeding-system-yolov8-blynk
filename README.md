# Feeding System — Gestur Tangan YOLOv8 + Blynk + ESP32

Webcam laptop → model YOLOv8 custom → Blynk Cloud → ESP32/Wokwi → servo.
YOLO berjalan di laptop, bukan di ESP32. Aplikasi Blynk dapat mengontrol perangkat yang sama.

## Status hasil implementasi (21 Oktober 2026)

Model **sudah dilatih** menggunakan dataset ini: YOLOv8n, 30 epoch, ukuran 320px, CPU.
Bobot siap pakai: `runs/detect/gesture-model/weights/best.pt` (sekitar 6,5 MB).
Hasil test pada 15 gambar: precision 0,992; recall 1,000; mAP50 0,995;
mAP50–95 0,894. Ini metrik pada test split kecil, bukan jaminan performa webcam langsung.
Laporan: `verification/training-report.json`; contoh deteksi disimpan di folder `verification`.

Build ESP32 **lulus**, RAM 46.508 byte / flash 806.617 byte. **16 unit test lulus**.
Webcam langsung, simulator Wokwi, dan hardware fisik belum diuji.
Token Blynk lama ditolak server; perbarui `.env` dan `secrets.h` sebelum kontrol online.

Untuk langsung mencoba model yang sudah ada:

```powershell
.\.venv\Scripts\python.exe app.py --dry-run
```

Setelah konfigurasi Blynk selesai dan ESP32 online, jalankan tanpa `--dry-run`.
Langkah training di bawah hanya diperlukan jika ingin melatih ulang.

## Gestur

| Kelas dataset | Aksi |
|---|---|
| `palm open` | Tahan 1 detik untuk mengubah ON/OFF |
| `finger up` | Tahan 1 detik untuk memberi pakan satu kali, hanya jika ON |

Setelah aksi, hilangkan tangan dari kamera minimal 0,6 detik sebelum gestur berikutnya.
Satu gestur yang terus ditahan hanya memicu sekali. Lebih dari satu deteksi dianggap ambigu.
Cooldown aplikasi 5 detik; firmware menolak pakan yang berjarak kurang dari 10 detik sejak awal siklus terakhir.
Servo membuka 90° selama 2 detik kemudian menutup 0°. Durasi ini **belum berarti dosis gram tertentu**.

## Menjalankan di Windows PowerShell

Python 3.10+ (lingkungan pengembangan ini menggunakan 3.13).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe prepare_dataset.py
.\.venv\Scripts\python.exe train.py --epochs 80 --batch 8 --device cpu
```

Jika tersedia PyTorch dengan CUDA dan GPU NVIDIA, gunakan `--device 0`.
Training CPU dapat berlangsung lama. Skrip menggunakan **yolov8n.pt**, bukan YOLO generasi lain.
Download bobot awal membutuhkan internet. ZIP berisi dataset, bukan bobot model terlatih.
Jika mengambil proyek dari Git, unduh dataset format YOLOv8 dari
[Roboflow Feeding System versi 7](https://universe.roboflow.com/feeding-system/feeding-system-z0kwt/dataset/7)
dan simpan sebagai `feeding system.v7i.yolov8.zip` di folder proyek. Dataset ZIP,
bobot model, dan hasil training tidak disertakan dalam Git; jalankan training untuk menghasilkan `best.pt`.
ZIP asli memiliki 397 label bounding box dan 3 label polygon campuran. Skrip mengonversi
ketiga polygon menjadi enclosing bounding box agar konsisten untuk YOLOv8 detection;
ZIP asli tidak diubah. `prepare_dataset.py` memvalidasi label dan memperbaiki path Roboflow menjadi `train/images`,
`valid/images`, `test/images`. Metadata atribusi Roboflow CC BY 4.0 dipertahankan.
Training mengevaluasi bobot terbaik pada test split dan mencetak lokasi `best.pt`.
Jika folder output sebelumnya sudah ada, Ultralytics membuat nama baru; sesuaikan MODEL_PATH.
Untuk melanjutkan training yang terhenti: `python train.py --resume runs/detect/gesture-model/weights/last.pt`.

Konfigurasi (file lokal `.env` dan `secrets.h` sudah dibuat dari kredensial sketch awal):

```powershell
# Hanya untuk instalasi baru jika file lokal belum ada:
Copy-Item .env.example .env
Copy-Item secrets.example.h secrets.h
```

Isi token device yang sama di kedua file dan Template ID di `secrets.h`.
Gunakan server Blynk yang tercantum di Console; `.env` memakai URL HTTPS,
`secrets.h` memakai hostname saja. Jangan membagikan `.env`, `secrets.h`, atau file asli
`CODING BLYNK YOLO.txt` dan `wokwi.original.ino.bak` karena berisi kredensial lama.

Uji kamera tanpa mengirim perintah terlebih dahulu:

```powershell
.\.venv\Scripts\python.exe app.py --dry-run
# Setelah ESP32/Wokwi online dan datastream dibuat:
.\.venv\Scripts\python.exe app.py
```

Keluar dengan Q/Esc. Menutup aplikasi kamera tidak mematikan jadwal ESP32;
gunakan switch V0=0 di Blynk untuk mematikan sistem. Jika kamera tidak terbuka, coba `--camera 1`.
Jika model belum ada, aplikasi berhenti dengan petunjuk training. Tidak ada fallback model COCO.

## Konfigurasi Blynk Console

Gunakan template `Feeding System` yang sudah ada atau buat template hardware ESP32 / WiFi,
lalu buat device dari template tersebut. Tambahkan **semua** datastream berikut:

| Virtual pin | Tipe | Rentang/default | Widget dan fungsi |
|---|---|---|---|
| V0 | Integer | 0–1, default 0 | Switch ON/OFF, status yang diminta |
| V1 | Double | -127–125, default -127 | Suhu °C; -127 berarti sensor belum tersedia |
| V2 | Double | 0–14 | Gauge pH simulasi |
| V3 | Integer | 0–1, default 0 | Button **PUSH**, pakan manual; ESP32 mereset ke 0 |
| V4 | Double | -1–5000, default -1 | Berat gram; -1 berarti sensor belum tersedia |
| V5 | Double | 0–100 | Kekeruhan NTU simulasi |
| V6 | Integer | 0–1, default 0 | LED/status ON aktual, ditulis ESP32 |
| V7 | Integer | 0–1, default 0 | LED servo sedang memberi pakan, ditulis ESP32 |
| V8 | String | — | Label status/penolakan terakhir dari ESP32 |

Atur widget V6–V8 untuk monitoring. Aplikasi membaca V6 sebelum mengubah V0 dan menolak
perintah jika ESP32 offline atau V0 belum dikonfirmasi oleh V6. Respons HTTP sukses berarti
permintaan diterima Cloud; lihat V7/V8 untuk hasil aktual di perangkat.
Timeout perintah tidak diulang otomatis agar pakan tidak terpicu dua kali.
Event opsional: buat kode `pakan_diberikan`, lalu ubah `ENABLE_EVENTS` di firmware menjadi `true`.
Tidak perlu membuat event kekeruhan; firmware tidak mengirim notifikasi berulang setiap loop.

## Wokwi dan perangkat nyata

1. Buat proyek ESP32 di Wokwi.
2. Salin isi `wokwi.ino` ke tab `sketch.ino`; tambahkan tab `secrets.h`, `diagram.json`, `libraries.txt`.
3. Isi kredensial. Wokwi menggunakan SSID `Wokwi-GUEST` tanpa password.
4. Jalankan simulasi dan tunggu device online di Blynk. ON melalui V0 lalu tes V3 sebelum memakai kamera.
5. Putar dua potensiometer untuk pH dan kekeruhan; ubah suhu DS18B20 dan berat HX711 lewat komponen.

Untuk Wokwi for VS Code, build dengan PlatformIO lalu jalankan **Wokwi: Start Simulator**.
`wokwi.toml` sudah menunjuk firmware lokal sesuai
[konfigurasi resmi Wokwi](https://docs.wokwi.com/vscode/project-config).

| Komponen | GPIO ESP32 |
|---|---|
| Servo PWM | 18 |
| DS18B20 DATA | 14, pull-up 4,7 kΩ ke 3,3 V |
| HX711 DT / SCK | 26 / 25 |
| Pot pH / kekeruhan | 34 / 33 |
| LCD2004 + DS1307 SDA / SCL | 21 / 22 |

Untuk perangkat nyata, gunakan catu servo 5 V yang memadai dengan ground bersama,
dan pastikan level I2C/sinyal sensor aman untuk ESP32 (GPIO 3,3 V; modul 5 V dapat memerlukan level shifter).
Potensiometer dan rumus linear pH/NTU adalah **simulasi**, belum kalibrasi sensor air sungguhan.
HX711 ditare satu kali saat sampel pertama siap; kosongkan wadah saat boot dan kalibrasi SCALE_FACTOR.
Berat bersifat monitoring; belum ada penghentian servo berdasarkan target gram.

Jadwal asli dipertahankan: 23:42, 23:47, 17:14, 17:16. Ubah `FEED_TIMES` sesuai kebutuhan.
RTC menyimpan waktu lokal; setel ke WIB. `diagram.json` memakai tanggal tetap agar hasil simulasi
dapat diulang; ubah atribut `initTime` untuk waktu pengujian. Perangkat nyata dengan RTC baru perlu
disetel ke waktu lokal (fallback firmware memakai waktu kompilasi, bukan sinkronisasi NTP).
Jadwal hanya berjalan saat ON; slot yang terhalang cooldown tidak diantrekan. Tanggal slot disimpan
di NVS untuk mengurangi pemberian ulang setelah restart pada menit yang sama. Jika penyimpanan
NVS gagal atau memori simulasi direset, perlindungan antar-restart tersebut tidak tersedia.
Tanpa RTC, kontrol manual tetap tersedia. Mematikan V0 langsung menutup servo.
Ketika internet terputus, jadwal lokal yang sudah ON tetap berjalan.

## Build dan pengujian

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip install platformio
.\.venv\Scripts\pio.exe run
```

`platformio.ini` membangun hanya `wokwi.ino`. Tidak ada port server lokal yang diperlukan.
Uji unit memakai Blynk palsu, sehingga tidak menggerakkan servo atau memanggil akun Blynk.
Versi dependensi lingkungan pengujian dicatat di `requirements-lock.txt` (Windows/Python 3.13).
Pemeriksaan baca-saja terhadap token awal mendapat HTTP 400 (`Invalid token.`)
di server global dan kelima region resmi. Ambil token device yang valid dari Blynk Console,
lalu perbarui `.env` dan `secrets.h` serta hostname region sebelum mencoba kontrol langsung.

Pengujian perangkat: OFF + V3 harus ditolak; ON + V3 harus membuka 2 detik; V0=0 ketika
servo terbuka harus segera menutupnya; putus/sambung jaringan tidak boleh mengulang V3.
Uji gestur ditahan, pergantian kelas, dua tangan, cahaya buruk, sensor terputus, dan jadwal melewati reboot.

Referensi: [YOLO training](https://docs.ultralytics.com/modes/train/),
[Blynk update](https://docs.blynk.io/en/blynk.cloud/device-https-api/update-datastream-value),
[Blynk read multiple](https://docs.blynk.io/en/blynk.cloud/device-https-api/get-multiple-datastream-values),
[Blynk virtual pins](https://docs.blynk.io/en/blynk-library-firmware-api/virtual-pins).
