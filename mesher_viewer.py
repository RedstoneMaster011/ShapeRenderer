import sys
import threading
import http.server
import socketserver
import functools
import socket
import webview

def find_free_port(start=19842):
    port = start
    while True:
        with socket.socket() as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
            port += 1

def start_server(dist_dir, port):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=dist_dir)
    handler.log_message = lambda *_: None
    httpd = socketserver.TCPServer(('localhost', port), handler)
    httpd.allow_reuse_address = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

def main():
    dist_dir = sys.argv[1]
    port = find_free_port()
    start_server(dist_dir, port)
    url = f'http://localhost:{port}/'
    window = webview.create_window(
        'Text Display Mesher',
        url,
        width=1200,
        height=850,
        resizable=True,
    )
    webview.start()

if __name__ == '__main__':
    main()