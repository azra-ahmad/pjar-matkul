"""
FTP-like File Transfer Server - Pemrograman Jaringan (Tugas Akhir Pre-UTS)
Fitur:
  - Multi-client dengan threading
  - Autentikasi sederhana (username + password)
  - Upload file dari client ke server
  - Download file dari server ke client
  - List file yang tersedia di server
  - Logging aktivitas ke file
"""

import socket
import threading
import datetime
import os

# ─── Konfigurasi ────────────────────────────────────────────────────────────
TCP_IP     = "0.0.0.0"
TCP_PORT   = 8503
BUFFER     = 4096
LOG_FILE   = "ftp_log.txt"
STORAGE_DIR = "storage"       # folder penyimpanan file

# Database user sederhana
USER_DB = {
    "azra"   : "ahmad",
    "lupiwo" : "cantip",
    "tamu"   : "1234",
}

# Client online: { username: conn }
online_clients: dict[str, socket.socket] = {}
clients_lock = threading.Lock()


# ─── Utilitas ───────────────────────────────────────────────────────────────
def timestamp() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(line: str):
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def send_msg(conn: socket.socket, message: str):
    try:
        conn.sendall((message + "\n").encode("utf-8"))
    except Exception:
        pass


# ─── Autentikasi ────────────────────────────────────────────────────────────
def authenticate(conn: socket.socket) -> str | None:
    send_msg(conn, "=== FTP Server - Pemrograman Jaringan ===")
    send_msg(conn, "Login untuk mengakses file server.")

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
                    send_msg(conn, "ERROR:User sudah login di perangkat lain.")
                    return None
            send_msg(conn, f"LOGIN_OK:Login berhasil. Selamat datang, {username}!")
            return username
        else:
            remaining = 2 - attempt
            send_msg(conn, f"LOGIN_FAIL:Username/password salah. Sisa percobaan: {remaining}.")

    send_msg(conn, "ERROR:Terlalu banyak percobaan. Koneksi ditutup.")
    return None


# ─── Handler: Upload File (Client → Server) ─────────────────────────────────
def handle_upload(conn: socket.socket, username: str, args: str):
    """
    Protokol upload:
      Client kirim: UPLOAD <filename> <filesize>
      Server reply:  READY:<filename>
      Client kirim:  <raw bytes sejumlah filesize>
      Server reply:  UPLOAD_OK atau UPLOAD_FAIL
    """
    parts = args.split()
    if len(parts) < 2:
        send_msg(conn, "[SERVER] Format: /upload <filename> <size>")
        return

    filename = os.path.basename(parts[0])
    try:
        file_size = int(parts[1])
    except ValueError:
        send_msg(conn, "[SERVER] Ukuran file tidak valid.")
        return

    MAX_FILE = 10 * 1024 * 1024
    if file_size > MAX_FILE:
        send_msg(conn, "[SERVER] File terlalu besar (maks 10 MB).")
        return

    # Buat folder user
    user_dir = os.path.join(STORAGE_DIR, username)
    os.makedirs(user_dir, exist_ok=True)
    save_path = os.path.join(user_dir, filename)

    send_msg(conn, f"READY:{filename}")

    received = 0
    with open(save_path, "wb") as f:
        while received < file_size:
            chunk = conn.recv(min(BUFFER, file_size - received))
            if not chunk:
                break
            f.write(chunk)
            received += len(chunk)

    if received == file_size:
        log(f"[{timestamp()}] {username} uploaded: {filename} ({file_size} bytes)")
        send_msg(conn, f"UPLOAD_OK:File '{filename}' berhasil diupload ({file_size} bytes).")
    else:
        send_msg(conn, "UPLOAD_FAIL:Upload gagal, data tidak lengkap.")
        if os.path.exists(save_path):
            os.remove(save_path)


# ─── Handler: Download File (Server → Client) ───────────────────────────────
def handle_download(conn: socket.socket, username: str, args: str):
    """
    Protokol download:
      Client kirim: DOWNLOAD <filename>
      Server reply:  FILE:<filename>:<filesize>  atau  ERROR:...
      Server kirim:  <raw bytes sejumlah filesize>
    """
    filename = args.strip()
    if not filename:
        send_msg(conn, "[SERVER] Format: /download <filename>")
        return

    filename = os.path.basename(filename)

    # Cari file di semua folder user
    file_path = None
    for user_folder in os.listdir(STORAGE_DIR):
        candidate = os.path.join(STORAGE_DIR, user_folder, filename)
        if os.path.isfile(candidate):
            file_path = candidate
            break

    if not file_path:
        send_msg(conn, f"ERROR:File '{filename}' tidak ditemukan di server.")
        return

    file_size = os.path.getsize(file_path)
    send_msg(conn, f"FILE:{filename}:{file_size}")

    # Tunggu client siap
    try:
        ack = conn.recv(BUFFER).decode("utf-8").strip()
    except Exception:
        return

    if ack != "READY":
        return

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(BUFFER)
            if not chunk:
                break
            conn.sendall(chunk)

    log(f"[{timestamp()}] {username} downloaded: {filename} ({file_size} bytes)")


# ─── Handler: List Files ────────────────────────────────────────────────────
def handle_list(conn: socket.socket):
    """Kirim daftar semua file yang tersedia di storage."""
    if not os.path.exists(STORAGE_DIR):
        send_msg(conn, "[SERVER] Belum ada file di server.")
        return

    files = []
    for user_folder in os.listdir(STORAGE_DIR):
        folder_path = os.path.join(STORAGE_DIR, user_folder)
        if os.path.isdir(folder_path):
            for f in os.listdir(folder_path):
                fpath = os.path.join(folder_path, f)
                size = os.path.getsize(fpath)
                files.append(f"  {f} ({size} bytes) [oleh {user_folder}]")

    if not files:
        send_msg(conn, "[SERVER] Belum ada file di server.")
    else:
        header = f"[SERVER] File tersedia ({len(files)}):"
        send_msg(conn, header + "\n" + "\n".join(files))


# ─── Handler Command ────────────────────────────────────────────────────────
def handle_command(conn: socket.socket, username: str, command: str) -> bool:
    cmd = command.strip()
    cmd_lower = cmd.lower()

    if cmd_lower == "/help":
        help_text = (
            "\n[SERVER] Daftar perintah:\n"
            "  /upload <file>     - Upload file ke server\n"
            "  /download <file>   - Download file dari server\n"
            "  /list              - Lihat daftar file di server\n"
            "  /quit              - Keluar\n"
        )
        send_msg(conn, help_text)

    elif cmd_lower == "/list":
        handle_list(conn)

    elif cmd_lower.startswith("/upload "):
        args = cmd[8:]  # setelah "/upload "
        handle_upload(conn, username, args)

    elif cmd_lower.startswith("/download "):
        args = cmd[10:]  # setelah "/download "
        handle_download(conn, username, args)

    elif cmd_lower == "/quit":
        send_msg(conn, "[SERVER] Sampai jumpa!")
        return False

    else:
        send_msg(conn, f"[SERVER] Perintah tidak dikenal: '{cmd}'. Ketik /help.")

    return True


# ─── Handler Client ─────────────────────────────────────────────────────────
def handle_client(conn: socket.socket, addr: tuple):
    log(f"[{timestamp()}] Koneksi baru dari {addr}")

    username = authenticate(conn)
    if not username:
        log(f"[{timestamp()}] Login gagal dari {addr}")
        conn.close()
        return

    with clients_lock:
        online_clients[username] = conn

    log(f"[{timestamp()}] {username} login dari {addr}")
    send_msg(conn, "[SERVER] Ketik /help untuk melihat daftar perintah.\n")

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

            if text.startswith("/"):
                if not handle_command(conn, username, text):
                    break
            else:
                send_msg(conn, "[SERVER] Gunakan perintah /help untuk melihat daftar perintah.")

    except Exception as e:
        log(f"[{timestamp()}] Error dari {username}: {e}")

    finally:
        with clients_lock:
            online_clients.pop(username, None)
        log(f"[{timestamp()}] {username} disconnected")
        conn.close()


# ─── Main ───────────────────────────────────────────────────────────────────
def main():
    os.makedirs(STORAGE_DIR, exist_ok=True)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((TCP_IP, TCP_PORT))
    server.listen(5)

    print("=" * 55)
    print("  FTP File Transfer Server - Pemrograman Jaringan")
    print("=" * 55)
    print(f"  Listening di {TCP_IP}:{TCP_PORT}")
    print(f"  Storage: {os.path.abspath(STORAGE_DIR)}")
    print(f"  Log: {os.path.abspath(LOG_FILE)}")
    print("  Tekan Ctrl+C untuk menghentikan server.")
    print("=" * 55)

    log(f"\n{'='*40}\nFTP Server dimulai: {timestamp()}\n{'='*40}")

    try:
        while True:
            conn, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\n[INFO] Server dihentikan.")
        log(f"Server dihentikan: {timestamp()}")
    finally:
        server.close()


if __name__ == "__main__":
    main()
