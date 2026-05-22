"""
FTP-like File Transfer Client - Pemrograman Jaringan (Tugas Akhir Pre-UTS)
Fitur:
  - Login dengan username dan password
  - Upload file ke server (/upload)
  - Download file dari server (/download)
  - List file di server (/list)
  - Command: /help, /quit
"""

import socket
import sys
import os

# ─── Konfigurasi ────────────────────────────────────────────────────────────
SERVER_IP   = "192.168.100.237"   # ← ganti dengan IP VM
SERVER_PORT = 8503
BUFFER      = 4096
DOWNLOAD_DIR = "downloads"        # folder simpan file hasil download


# ─── Utilitas ───────────────────────────────────────────────────────────────
def recv_line(conn: socket.socket) -> str:
    """Terima satu baris pesan dari server (sampai newline)."""
    data = b""
    while True:
        chunk = conn.recv(1)
        if not chunk:
            break
        if chunk == b"\n":
            break
        data += chunk
    return data.decode("utf-8").strip()


def recv_all_lines(conn: socket.socket) -> str:
    """Terima semua data yang tersedia (non-blocking setelah timeout)."""
    conn.settimeout(0.5)
    data = b""
    try:
        while True:
            chunk = conn.recv(BUFFER)
            if not chunk:
                break
            data += chunk
    except socket.timeout:
        pass
    finally:
        conn.settimeout(None)
    return data.decode("utf-8").strip()


# ─── Proses Login ────────────────────────────────────────────────────────────
def do_login(conn: socket.socket) -> bool:
    buffer = ""
    while True:
        chunk = conn.recv(BUFFER).decode("utf-8")
        buffer += chunk

        lines = buffer.split("\n")
        buffer = lines[-1]

        for line in lines[:-1]:
            line = line.strip()
            if not line:
                continue

            if line == "USERNAME:":
                username = input("Username: ").strip()
                conn.sendall(username.encode("utf-8"))

            elif line == "PASSWORD:":
                password = input("Password: ").strip()
                conn.sendall(password.encode("utf-8"))

            elif line.startswith("LOGIN_OK:"):
                print(f"\n{line[9:]}")
                return True

            elif line.startswith("LOGIN_FAIL:") or line.startswith("ERROR:"):
                print(f"[!] {line.split(':', 1)[1]}")
                if "ditutup" in line or "banyak" in line:
                    return False
            else:
                print(line)


# ─── Upload File ─────────────────────────────────────────────────────────────
def upload_file(conn: socket.socket, args: str):
    filepath = args.strip()
    if not filepath:
        print("[!] Format: /upload <path_file>")
        return

    if not os.path.isfile(filepath):
        print(f"[!] File tidak ditemukan: {filepath}")
        return

    filename = os.path.basename(filepath)
    file_size = os.path.getsize(filepath)

    if file_size > 10 * 1024 * 1024:
        print("[!] File terlalu besar (maks 10 MB).")
        return

    # Kirim command upload dengan metadata
    header = f"/upload {filename} {file_size}"
    conn.sendall(header.encode("utf-8"))

    # Tunggu READY dari server
    response = recv_line(conn)
    if not response.startswith("READY:"):
        print(f"[SERVER] {response}")
        return

    print(f"[INFO] Mengirim '{filename}' ({file_size} bytes)...")

    sent = 0
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(BUFFER)
            if not chunk:
                break
            conn.sendall(chunk)
            sent += len(chunk)

    # Tunggu konfirmasi
    result = recv_line(conn)
    if result.startswith("UPLOAD_OK:"):
        print(f"[OK] {result[10:]}")
    else:
        print(f"[!] {result}")


# ─── Download File ───────────────────────────────────────────────────────────
def download_file(conn: socket.socket, args: str):
    filename = args.strip()
    if not filename:
        print("[!] Format: /download <filename>")
        return

    conn.sendall(f"/download {filename}".encode("utf-8"))

    # Tunggu response: FILE:<name>:<size> atau ERROR:...
    response = recv_line(conn)

    if response.startswith("ERROR:"):
        print(f"[!] {response[6:]}")
        return

    if not response.startswith("FILE:"):
        print(f"[SERVER] {response}")
        return

    parts = response.split(":")
    fname = parts[1]
    fsize = int(parts[2])

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    save_path = os.path.join(DOWNLOAD_DIR, fname)

    # Kirim ACK
    conn.sendall("READY".encode("utf-8"))

    print(f"[INFO] Downloading '{fname}' ({fsize} bytes)...")

    received = 0
    with open(save_path, "wb") as f:
        while received < fsize:
            chunk = conn.recv(min(BUFFER, fsize - received))
            if not chunk:
                break
            f.write(chunk)
            received += len(chunk)

    if received == fsize:
        print(f"[OK] File disimpan di: {save_path}")
    else:
        print("[!] Download gagal: data tidak lengkap.")


# ─── List Files ──────────────────────────────────────────────────────────────
def list_files(conn: socket.socket):
    conn.sendall("/list".encode("utf-8"))
    response = recv_all_lines(conn)
    if response:
        print(response)


# ─── Main ───────────────────────────────────────────────────────────────────
def main():
    print("=" * 50)
    print("  FTP File Transfer Client - Pemrograman Jaringan")
    print("=" * 50)
    print(f"  Server: {SERVER_IP}:{SERVER_PORT}")
    print("=" * 50 + "\n")

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

    if not do_login(conn):
        print("[INFO] Login gagal. Keluar.")
        conn.close()
        sys.exit(1)

    # Terima pesan awal (help hint)
    hint = recv_all_lines(conn)
    if hint:
        print(hint)

    print()

    try:
        while True:
            try:
                text = input("ftp>> ").strip()
            except EOFError:
                break

            if not text:
                continue

            cmd_lower = text.lower()

            if cmd_lower == "/help":
                conn.sendall("/help".encode("utf-8"))
                response = recv_all_lines(conn)
                if response:
                    print(response)

            elif cmd_lower == "/list":
                list_files(conn)

            elif cmd_lower.startswith("/upload "):
                upload_file(conn, text[8:])

            elif cmd_lower.startswith("/download "):
                download_file(conn, text[10:])

            elif cmd_lower == "/quit":
                conn.sendall("/quit".encode("utf-8"))
                response = recv_all_lines(conn)
                if response:
                    print(response)
                break

            else:
                conn.sendall(text.encode("utf-8"))
                response = recv_all_lines(conn)
                if response:
                    print(response)

    except KeyboardInterrupt:
        print("\n[INFO] Keluar paksa.")
        try:
            conn.sendall("/quit".encode("utf-8"))
        except Exception:
            pass

    finally:
        conn.close()
        print("[INFO] Koneksi ditutup.")


if __name__ == "__main__":
    main()
