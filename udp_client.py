import socket

UDP_IP = "192.168.100.237" 
UDP_PORT = 8501
MESSAGE = b"Halo Azra, ini paket UDP dari Windows!"

print(f"Nembak paket ke {UDP_IP}:{UDP_PORT}...")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto(MESSAGE, (UDP_IP, UDP_PORT))

print("Pesan terkirim!")

