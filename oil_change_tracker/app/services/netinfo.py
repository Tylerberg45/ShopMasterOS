import socket

def get_host_info(port: int = 8000):
    hostname = socket.gethostname()
    try:
        ip = socket.gethostbyname(hostname)
    except Exception:
        ip = "127.0.0.1"
    return {
        "hostname": hostname,
        "ip": ip,
        "urls": [
            f"http://{hostname}:{port}",
            f"http://{ip}:{port}",
            "http://127.0.0.1:{port}".format(port=port),
        ],
    }
