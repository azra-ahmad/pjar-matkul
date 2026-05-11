"""
UDP Chat Server - Pemrograman Jaringan
Fitur:
  - Menerima pesan dari banyak client sekaligus
  - Logging pesan ke file (chat_log.txt)
  - Format pesan: [timestamp] username: pesan
  - Validasi input (username dan pesan tidak boleh kosong/spam)
  - Broadcast ke semua client yang aktif
"""

import socket
import datetime
import os

# ─── Konfigurasi ────────────────────────────────────────────────────────────
UDP_IP   = "0.0.0.0"
UDP_PORT = 8501
LOG_FILE = "chat_log_udp.txt"
BUFFER   = 2048

# Batas panjang username dan pesan
MAX_USERNAME_LEN = 20
MAX_MSG_LEN      = 300

# Simpan daftar client aktif: { addr: username }
active_clients = {}


# ─── Utilitas ───────────────────────────────────────────────────────────────
def timestamp():
    """Return timestamp string saat ini."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_message(line: str):
    """Simpan pesan ke file log."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def validate_username(username: str) -> tuple[bool, str]:
    """Validasi username: tidak kosong, tidak terlalu panjang, alphanumeric."""
    if not username or username.strip() == "":
        return False, "Username tidak boleh kosong."
    if len(username) > MAX_USERNAME_LEN:
        return False, f"Username maksimal {MAX_USERNAME_LEN} karakter."
    if not username.replace("_", "").isalnum():
        return False, "Username hanya boleh huruf, angka, dan underscore."
    return True, ""


def validate_message(msg: str) -> tuple[bool, str]:
    """Validasi isi pesan."""
    if not msg or msg.strip() == "":
        return False, "Pesan tidak boleh kosong."
    if len(msg) > MAX_MSG_LEN:
        return False, f"Pesan maksimal {MAX_MSG_LEN} karakter."
    return True, ""


def broadcast(sock: socket.socket, message: str, exclude_addr=None):
    """Kirim pesan ke semua client aktif (opsional: kecuali pengirim)."""
    encoded = message.encode("utf-8")
    for addr in list(active_clients.keys()):
        if addr != exclude_addr:
            try:
                sock.sendto(encoded, addr)
            except Exception as e:
                print(f"[WARN] Gagal kirim ke {addr}: {e}")


# ─── Handler Pesan Masuk ────────────────────────────────────────────────────
def handle_packet(sock: socket.socket, raw_data: bytes, addr: tuple):
    """
    Protokol paket dari client:
      REGISTER:<username>          → daftar client baru
      MSG:<username>:<pesan>       → kirim pesan ke semua
      LEAVE:<username>             → client keluar
    """
    try:
        data = raw_data.decode("utf-8").strip()
    except UnicodeDecodeError:
        sock.sendto(b"ERROR:Enkoding tidak valid.", addr)
        return

    # ── REGISTER ──
    if data.startswith("REGISTER:"):
        username = data[len("REGISTER:"):]
        valid, err = validate_username(username)
        if not valid:
            sock.sendto(f"ERROR:{err}".encode(), addr)
            return

        # Cek username sudah dipakai
        if username in active_clients.values():
            sock.sendto(b"ERROR:Username sudah dipakai.", addr)
            return

        active_clients[addr] = username
        joined = f"[{timestamp()}] *** {username} bergabung ke chat ***"
        print(joined)
        log_message(joined)

        sock.sendto(f"OK:Selamat datang, {username}!".encode(), addr)
        broadcast(sock, joined, exclude_addr=addr)

    # ── PESAN ──
    elif data.startswith("MSG:"):
        parts = data.split(":", 2)   # ["MSG", "username", "pesan"]
        if len(parts) < 3:
            sock.sendto(b"ERROR:Format pesan tidak valid.", addr)
            return

        username = parts[1]
        message  = parts[2]

        # Validasi: client harus sudah register
        if addr not in active_clients or active_clients[addr] != username:
            sock.sendto(b"ERROR:Anda belum terdaftar. Kirim REGISTER dulu.", addr)
            return

        valid, err = validate_message(message)
        if not valid:
            sock.sendto(f"ERROR:{err}".encode(), addr)
            return

        formatted = f"[{timestamp()}] {username}: {message}"
        print(formatted)
        log_message(formatted)

        # Broadcast ke semua (termasuk pengirim biar ada konfirmasi tampil)
        broadcast(sock, formatted)

    # ── LEAVE ──
    elif data.startswith("LEAVE:"):
        username = data[len("LEAVE:"):]
        if addr in active_clients:
            del active_clients[addr]
            left = f"[{timestamp()}] *** {username} meninggalkan chat ***"
            print(left)
            log_message(left)
            broadcast(sock, left)
            sock.sendto(b"OK:Sampai jumpa!", addr)

    else:
        sock.sendto(b"ERROR:Perintah tidak dikenal.", addr)


# ─── Main ───────────────────────────────────────────────────────────────────
def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))

    print("=" * 55)
    print("  UDP Chat Server - Pemrograman Jaringan")
    print("=" * 55)
    print(f"  Listening di {UDP_IP}:{UDP_PORT}")
    print(f"  Log disimpan ke: {os.path.abspath(LOG_FILE)}")
    print("  Tekan Ctrl+C untuk menghentikan server.")
    print("=" * 55)

    log_message(f"\n{'='*40}\nServer dimulai: {timestamp()}\n{'='*40}")

    try:
        while True:
            data, addr = sock.recvfrom(BUFFER)
            handle_packet(sock, data, addr)
    except KeyboardInterrupt:
        print("\n[INFO] Server dihentikan.")
        log_message(f"Server dihentikan: {timestamp()}")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
