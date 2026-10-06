from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HOST = "0.0.0.0"
PORT = 8000

server = ThreadingHTTPServer((HOST, PORT), SimpleHTTPRequestHandler)
print(f"Serving on {HOST}:{PORT}", flush=True)
server.serve_forever()
