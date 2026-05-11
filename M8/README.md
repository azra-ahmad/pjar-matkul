# Pemrograman Socket UDP & TCP
**Mata Kuliah:** Pemrograman Jaringan  
**Bahasa:** Python 3.14.3

---

## Struktur File

```
.
├── udp_server.py   # Server UDP (jalankan di VM)
├── udp_client.py   # Client UDP (jalankan di Windows lokal)
├── tcp_server.py   # Server TCP (jalankan di VM)
├── tcp_client.py   # Client TCP (jalankan di Windows lokal)
└── README.md
```

---

## 1. UDP Chat (Broadcast)

### Fitur
- Multi-client: server bisa terima pesan dari banyak client sekaligus
- Broadcast: pesan dari satu client dikirim ke semua yang online
- Logging: semua pesan disimpan ke `chat_log_udp.txt`
- Format pesan: `[timestamp] username: pesan`
- Validasi input: username (alphanumeric, maks 20 char), pesan (maks 300 char)

### Protokol Paket

| Perintah | Arah | Keterangan |
|---|---|---|
| `REGISTER:<username>` | Client → Server | Daftar ke chat |
| `MSG:<username>:<pesan>` | Client → Server | Kirim pesan |
| `LEAVE:<username>` | Client → Server | Keluar dari chat |
| `OK:<info>` | Server → Client | Respons sukses |
| `ERROR:<info>` | Server → Client | Respons error |

### Cara Menjalankan

**Di VM (SSH):**
```bash
python3 udp_server.py
```

**Di Windows (tiap client di terminal berbeda):**
```bash
# Edit SERVER_IP di udp_client.py dulu!
python udp_client.py
```

---

## 2. TCP Chat (Multi-Connection)

### Fitur
- Multi-client: tiap client ditangani oleh thread tersendiri
- Autentikasi: login username + password sebelum bisa chat
- Chat real-time: pesan broadcast ke semua user yang login
- Command-based system:
  - `/list` — lihat siapa yang online
  - `/send <file>` — upload file ke server
  - `/help` — tampilkan daftar perintah
  - `/quit` — keluar dari chat
- Logging ke `chat_log_tcp.txt`
- File upload: disimpan di folder `uploads/`

### Akun Default

| Username | Password |
|---|---|
| `azra` | `ahmad` |
| `dosen` | `1234` |
| `tamu` | `1234` |

> Edit dictionary `USER_DB` di `tcp_server.py` untuk menambah/mengubah akun.

### Cara Menjalankan

**Di VM (SSH):**
```bash
python3 tcp_server.py
```

**Di Windows:**
```bash
# Edit SERVER_IP di tcp_client.py dulu!
python tcp_client.py
```

---

## Konfigurasi IP

Ganti nilai `SERVER_IP` di file client sesuai IP VM:

```python
# udp_client.py & tcp_client.py
SERVER_IP = "192.168.100.237"  
```

## Port yang Digunakan

| Program | Port |
|---|---|
| UDP Server | 8501 |
| TCP Server | 8502 |

Pastikan port ini tidak diblokir firewall di VM.

```bash
# Kalau pakai UFW di Ubuntu:
sudo ufw allow 8501/udp
sudo ufw allow 8502/tcp
```
