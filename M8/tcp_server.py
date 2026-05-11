"""
TCP Chat Server - Pemrograman Jaringan
Fitur:
  - Multi-client dengan threading (tiap client = 1 thread)
  - Autentikasi sederhana (username + password)
  - Chat real-time antar user
  - Command-based: /list, /send <file>, /help, /quit
  - Penerimaan file dari client (upload ke server)
  - Logging semua aktivitas ke file
"""

import socket
import threading
import datetime
import os
import json

# ─── Konfigurasi ────────────────────────────────────────────────────────────
TCP_IP    = "0.0.0.0"
TCP_PORT  = 8502
LOG_FILE  = "chat_log_tcp.txt"
UPLOAD_DIR = "uploads"          # folder penyimpanan file dari client
BUFFER    = 4096

# Database user sederhana (username: password)
# Di produksi: pakai hashing & DB asli
USER_DB = {
    "azra"   : "ahmad",
    "lupiwo" : "cantip",
    "tamu"   : "1234",
}

# Daftar client yang sedang online: { username: conn }
online_clients: dict[str, socket.socket] = {}
clients_lock = threading.Lock()


# ─── Utilitas ───────────────────────────────────────────────────────────────
def timestamp() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(line: str):
    """Print ke terminal server dan simpan ke file."""
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def send_msg(conn: socket.socket, message: str):
    """Kirim pesan teks ke satu client (dengan newline)."""
    try:
        conn.sendall((message + "\n").encode("utf-8"))
    except Exception:
        pass


def broadcast(message: str, exclude: str = None):
    """Kirim pesan ke semua client online, kecuali `exclude`."""
    with clients_lock:
        for uname, conn in list(online_clients.items()):
            if uname != exclude:
                send_msg(conn, message)


# ─── Autentikasi ────────────────────────────────────────────────────────────
def authenticate(conn: socket.socket) -> str | None:
    """
    Lakukan handshake login dengan client.
    Return username jika sukses, None jika gagal.
    """
    send_msg(conn, "=== TCP Chat Server ===")
    send_msg(conn, "Masukkan username dan password untuk login.")

    for attempt in range(3):
        send_msg(conn, "USERNAME:")
        try:
            username = conn.recv(BUFFER).decode("utf-8").strip()
            send_msg(conn, "PASSWORD:")
            password = conn.recv(BUFFER).decode("utf-8").strip()
        except Exception:
            return None

        if username in USER_DB and USER_DB[username] == password:
            with clients_lock:
                if username in online_clients:
                    send_msg(conn, "ERROR: User sudah login di perangkat lain.")
                    return None
            send_msg(conn, f"LOGIN_OK:Selamat datang, {username}!")
            return username
        else:
            remaining = 2 - attempt
            send_msg(conn, f"LOGIN_FAIL:Username/password salah. Sisa percobaan: {remaining}.")

    send_msg(conn, "ERROR:Terlalu banyak percobaan. Koneksi ditutup.")
    return None


# ─── Handler File Transfer ───────────────────────────────────────────────────
def handle_file_upload(conn: socket.socket, username: str, header: str):
    """
    Protokol upload file:
      Client kirim: /send <namafile> <ukuran_bytes>
      Server terima byte sejumlah ukuran_bytes dan simpan ke UPLOAD_DIR
    """
    parts = header.split()
    if len(parts) < 3:
        send_msg(conn, "[SERVER] Format: /send <namafile> <ukuran_bytes>")
        return

    filename  = os.path.basename(parts[1])   # sanitasi path traversal
    file_size = int(parts[2])

    # Batasi ukuran: maks 10 MB
    MAX_FILE = 10 * 1024 * 1024
    if file_size > MAX_FILE:
        send_msg(conn, f"[SERVER] File terlalu besar (maks 10 MB).")
        return

    send_msg(conn, f"READY:{filename}")   # sinyal server siap terima

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    save_path = os.path.join(UPLOAD_DIR, f"{username}_{filename}")

    received = 0
    with open(save_path, "wb") as f:
        while received < file_size:
            chunk = conn.recv(min(BUFFER, file_size - received))
            if not chunk:
                break
            f.write(chunk)
            received += len(chunk)

    if received == file_size:
        msg = f"[{timestamp()}] {username} mengunggah file: {filename} ({file_size} bytes)"
        log(msg)
        send_msg(conn, f"[SERVER] File '{filename}' berhasil diterima ({file_size} bytes).")
        broadcast(f"[INFO] {username} membagikan file: {filename}", exclude=username)
    else:
        send_msg(conn, "[SERVER] Upload gagal: data tidak lengkap.")


# ─── Handler Perintah (/command) ────────────────────────────────────────────
def handle_command(conn: socket.socket, username: str, command: str) -> bool:
    """
    Proses perintah dari client.
    Return False jika client minta keluar (/quit).
    """
    cmd = command.strip().lower()

    # /help — tampilkan daftar perintah
    if cmd == "/help":
        help_text = (
            "\n[SERVER] Daftar perintah:\n"
            "  /help              - Tampilkan perintah ini\n"
            "  /list              - Lihat siapa saja yang online\n"
            "  /send <file> <sz>  - Upload file ke server\n"
            "  /quit              - Keluar dari chat\n"
        )
        send_msg(conn, help_text)

    # /list — tampilkan user online
    elif cmd == "/list":
        with clients_lock:
            users = list(online_clients.keys())
        send_msg(conn, f"[SERVER] Online ({len(users)}): {', '.join(users)}")

    # /send — upload file
    elif command.lower().startswith("/send "):
        handle_file_upload(conn, username, command)

    # /quit — client minta keluar
    elif cmd == "/quit":
        send_msg(conn, "[SERVER] Sampai jumpa!")
        return False

    else:
        send_msg(conn, f"[SERVER] Perintah tidak dikenal: '{command}'. Ketik /help.")

    return True


# ─── Handler Client (1 Thread Per Client) ───────────────────────────────────
def handle_client(conn: socket.socket, addr: tuple):
    """Thread utama untuk satu client yang terkoneksi."""
    log(f"[{timestamp()}] Koneksi baru dari {addr}")

    # ── Autentikasi ──
    username = authenticate(conn)
    if not username:
        log(f"[{timestamp()}] Login gagal dari {addr}")
        conn.close()
        return

    # ── Daftarkan ke online_clients ──
    with clients_lock:
        online_clients[username] = conn

    joined = f"[{timestamp()}] *** {username} bergabung ke chat ***"
    log(joined)
    broadcast(joined, exclude=username)
    send_msg(conn, "[SERVER] Ketik /help untuk melihat daftar perintah.\n")

    # ── Loop utama: terima dan proses pesan ──
    try:
        while True:
            try:
                data = conn.recv(BUFFER)
            except Exception:
                break

            if not data:
                break

            text = data.decode("utf-8").strip()

            if not text:
                continue

            # Perintah khusus dimulai dengan /
            if text.startswith("/"):
                if not handle_command(conn, username, text):
                    break
            else:
                # Pesan biasa — broadcast ke semua
                if len(text) > 500:
                    send_msg(conn, "[SERVER] Pesan terlalu panjang (maks 500 karakter).")
                    continue
                formatted = f"[{timestamp()}] {username}: {text}"
                log(formatted)
                broadcast(formatted)

    except Exception as e:
        log(f"[{timestamp()}] Error dari {username}: {e}")

    finally:
        # ── Cleanup ──
        with clients_lock:
            online_clients.pop(username, None)

        left = f"[{timestamp()}] *** {username} meninggalkan chat ***"
        log(left)
        broadcast(left)
        conn.close()


# ─── Main ───────────────────────────────────────────────────────────────────
def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((TCP_IP, TCP_PORT))
    server.listen(10)

    print("=" * 55)
    print("  TCP Chat Server - Pemrograman Jaringan")
    print("=" * 55)
    print(f"  Listening di {TCP_IP}:{TCP_PORT}")
    print(f"  Log: {os.path.abspath(LOG_FILE)}")
    print(f"  Upload dir: {os.path.abspath(UPLOAD_DIR)}")
    print("  Tekan Ctrl+C untuk menghentikan server.")
    print("=" * 55)

    log(f"\n{'='*40}\nServer TCP dimulai: {timestamp()}\n{'='*40}")

    try:
        while True:
            conn, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
            log(f"[{timestamp()}] Thread baru untuk {addr} | Total aktif: {threading.active_count() - 1}")

    except KeyboardInterrupt:
        print("\n[INFO] Server dihentikan.")
        log(f"Server dihentikan: {timestamp()}")
    finally:
        server.close()


if __name__ == "__main__":
    main()