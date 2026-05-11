"""
UDP Chat Client - Pemrograman Jaringan
Fitur:
  - Register username ke server sebelum chat
  - Kirim dan terima pesan secara real-time (thread terpisah)
  - Validasi input di sisi client
  - Graceful exit dengan perintah /quit
"""

import socket
import threading
import sys

# ─── Konfigurasi ────────────────────────────────────────────────────────────
SERVER_IP   = "192.168.100.237"   
SERVER_PORT = 8501
BUFFER      = 2048
TIMEOUT     = 5   # detik tunggu respons server


# ─── Thread: Menerima Pesan ─────────────────────────────────────────────────
def receive_messages(sock: socket.socket, stop_event: threading.Event):
    """
    Berjalan di thread terpisah.
    Terus-menerus mendengarkan pesan dari server dan mencetaknya.
    """
    sock.settimeout(1.0)   # biar bisa cek stop_event secara periodik
    while not stop_event.is_set():
        try:
            data, _ = sock.recvfrom(BUFFER)
            message = data.decode("utf-8")

            # Hindari tumpang tindih dengan input prompt
            print(f"\r{message}")
            print("Pesan > ", end="", flush=True)
        except socket.timeout:
            continue
        except Exception:
            if not stop_event.is_set():
                print("\n[ERROR] Koneksi ke server terputus.")
            break


# ─── Register Username ───────────────────────────────────────────────────────
def register(sock: socket.socket, username: str) -> bool:
    """
    Kirim permintaan REGISTER ke server.
    Return True jika berhasil, False jika gagal.
    """
    sock.settimeout(TIMEOUT)
    packet = f"REGISTER:{username}".encode("utf-8")

    try:
        sock.sendto(packet, (SERVER_IP, SERVER_PORT))
        response, _ = sock.recvfrom(BUFFER)
        resp = response.decode("utf-8")

        if resp.startswith("OK:"):
            print(f"[SERVER] {resp[3:]}")
            return True
        elif resp.startswith("ERROR:"):
            print(f"[ERROR] {resp[6:]}")
            return False
        else:
            print(f"[WARN] Respons tidak dikenal: {resp}")
            return False

    except socket.timeout:
        print("[ERROR] Server tidak merespons. Cek IP/port atau jaringan.")
        return False


# ─── Main ───────────────────────────────────────────────────────────────────
def main():
    print("=" * 50)
    print("  UDP Chat Client - Pemrograman Jaringan")
    print("=" * 50)
    print(f"  Terhubung ke {SERVER_IP}:{SERVER_PORT}")
    print("  Ketik /quit untuk keluar.")
    print("=" * 50)

    # ── Minta username ──
    while True:
        username = input("Masukkan username: ").strip()
        if not username:
            print("[WARN] Username tidak boleh kosong.")
            continue
        if len(username) > 20:
            print("[WARN] Username maksimal 20 karakter.")
            continue
        if not username.replace("_", "").isalnum():
            print("[WARN] Username hanya boleh huruf, angka, dan underscore.")
            continue
        break

    # ── Buat socket & register ──
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    if not register(sock, username):
        print("[INFO] Registrasi gagal. Keluar.")
        sock.close()
        sys.exit(1)

    # ── Mulai thread penerima ──
    stop_event = threading.Event()
    recv_thread = threading.Thread(
        target=receive_messages,
        args=(sock, stop_event),
        daemon=True
    )
    recv_thread.start()

    print("\n[INFO] Siap chat! Ketik pesan dan tekan Enter.\n")

    # ── Loop input pengguna ──
    try:
        while True:
            try:
                text = input("Pesan > ").strip()
            except EOFError:
                break

            if text == "":
                continue

            if text.lower() == "/quit":
                leave_packet = f"LEAVE:{username}".encode("utf-8")
                sock.sendto(leave_packet, (SERVER_IP, SERVER_PORT))
                print("[INFO] Keluar dari chat. Sampai jumpa!")
                break

            # Validasi panjang pesan
            if len(text) > 300:
                print("[WARN] Pesan terlalu panjang (maks 300 karakter).")
                continue

            # Kirim pesan
            packet = f"MSG:{username}:{text}".encode("utf-8")
            try:
                sock.sendto(packet, (SERVER_IP, SERVER_PORT))
            except Exception as e:
                print(f"[ERROR] Gagal mengirim: {e}")

    except KeyboardInterrupt:
        leave_packet = f"LEAVE:{username}".encode("utf-8")
        sock.sendto(leave_packet, (SERVER_IP, SERVER_PORT))
        print("\n[INFO] Keluar paksa. Sampai jumpa!")

    finally:
        stop_event.set()
        sock.close()


if __name__ == "__main__":
    main()
