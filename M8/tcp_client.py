"""
TCP Chat Client - Pemrograman Jaringan
Fitur:
  - Login dengan username dan password
  - Kirim dan terima pesan real-time (thread terpisah)
  - Upload file ke server dengan perintah /send
  - Command: /list, /help, /quit
"""

import socket
import threading
import sys
import os

# ─── Konfigurasi ────────────────────────────────────────────────────────────
SERVER_IP   = "192.168.100.237"
SERVER_PORT = 8502
BUFFER      = 4096


# ─── Thread: Menerima Pesan dari Server ─────────────────────────────────────
def receive_messages(conn: socket.socket, stop_event: threading.Event):
    """
    Berjalan di thread terpisah.
    Mendengarkan semua pesan dari server dan mencetak ke layar.
    """
    try:
        while not stop_event.is_set():
            data = conn.recv(BUFFER)
            if not data:
                print("\n[INFO] Server menutup koneksi.")
                stop_event.set()
                break
            message = data.decode("utf-8").strip()
            if message:
                print(f"\r{message}")
                print(">> ", end="", flush=True)
    except Exception:
        if not stop_event.is_set():
            print("\n[ERROR] Koneksi ke server terputus.")
        stop_event.set()


# ─── Proses Login ────────────────────────────────────────────────────────────
def do_login(conn: socket.socket) -> bool:
    """
    Lakukan proses login interaktif dengan server.
    Server akan mengirimkan prompt USERNAME: dan PASSWORD:
    Return True jika berhasil login.
    """
    buffer = ""
    while True:
        chunk = conn.recv(BUFFER).decode("utf-8")
        buffer += chunk

        lines = buffer.split("\n")
        buffer = lines[-1]   # simpan sisa yang belum newline

        for line in lines[:-1]:
            line = line.strip()
            if not line:
                continue

            print(line)

            if line == "USERNAME:":
                username = input("  Username: ").strip()
                conn.sendall(username.encode("utf-8"))

            elif line == "PASSWORD:":
                password = input("  Password: ").strip()
                conn.sendall(password.encode("utf-8"))

            elif line.startswith("LOGIN_OK:"):
                print(f"\n{line[9:]}")
                return True

            elif line.startswith("LOGIN_FAIL:") or line.startswith("ERROR:"):
                # Tampilkan pesan error tapi lanjut loop (server beri 3 kesempatan)
                print(f"[!] {line.split(':', 1)[1]}")
                # Jika server bilang koneksi ditutup, keluar
                if "ditutup" in line or "banyak" in line:
                    return False


# ─── Upload File ─────────────────────────────────────────────────────────────
def upload_file(conn: socket.socket, command: str):
    """
    Proses upload file setelah server merespons READY.
    Format perintah: /send <path_file_lokal>
    Client otomatis hitung ukuran dan kirim headernya.
    """
    parts = command.split(maxsplit=1)
    if len(parts) < 2:
        print("[!] Format: /send <path_file>")
        return

    filepath = parts[1].strip()
    if not os.path.isfile(filepath):
        print(f"[!] File tidak ditemukan: {filepath}")
        return

    filename  = os.path.basename(filepath)
    file_size = os.path.getsize(filepath)

    # Batasi 10 MB
    if file_size > 10 * 1024 * 1024:
        print("[!] File terlalu besar (maks 10 MB).")
        return

    # Kirim header ke server
    header = f"/send {filename} {file_size}"
    conn.sendall(header.encode("utf-8"))

    # Tunggu sinyal READY dari server
    response = conn.recv(BUFFER).decode("utf-8").strip()
    if not response.startswith("READY:"):
        print(f"[SERVER] {response}")
        return

    print(f"[INFO] Mengirim file '{filename}' ({file_size} bytes)...")

    # Kirim isi file
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(BUFFER)
            if not chunk:
                break
            conn.sendall(chunk)

    print("[INFO] File berhasil dikirim.")


# ─── Main ───────────────────────────────────────────────────────────────────
def main():
    print("=" * 50)
    print("  TCP Chat Client - Pemrograman Jaringan")
    print("=" * 50)
    print(f"  Terhubung ke {SERVER_IP}:{SERVER_PORT}")
    print("=" * 50 + "\n")

    # ── Buat koneksi TCP ──
    try:
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.connect((SERVER_IP, SERVER_PORT))
    except ConnectionRefusedError:
        print(f"[ERROR] Tidak bisa terhubung ke {SERVER_IP}:{SERVER_PORT}.")
        print("         Pastikan server sudah berjalan.")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    # ── Login ──
    if not do_login(conn):
        print("[INFO] Login gagal. Keluar.")
        conn.close()
        sys.exit(1)

    # ── Mulai thread penerima ──
    stop_event = threading.Event()
    recv_thread = threading.Thread(
        target=receive_messages,
        args=(conn, stop_event),
        daemon=True
    )
    recv_thread.start()

    print("\n[INFO] Chat dimulai! Ketik /help untuk daftar perintah.\n")

    # ── Loop input pengguna ──
    try:
        while not stop_event.is_set():
            try:
                text = input(">> ").strip()
            except EOFError:
                break

            if not text:
                continue

            # Perintah /send ditangani khusus (butuh transfer binary)
            if text.lower().startswith("/send "):
                upload_file(conn, text)
                continue

            # Perintah /quit
            if text.lower() == "/quit":
                conn.sendall("/quit".encode("utf-8"))
                break

            # Pesan biasa atau perintah lain
            try:
                conn.sendall(text.encode("utf-8"))
            except Exception as e:
                print(f"[ERROR] Gagal kirim: {e}")
                break

    except KeyboardInterrupt:
        print("\n[INFO] Keluar paksa.")
        try:
            conn.sendall("/quit".encode("utf-8"))
        except Exception:
            pass

    finally:
        stop_event.set()
        conn.close()
        print("[INFO] Koneksi ditutup.")


if __name__ == "__main__":
    main()
