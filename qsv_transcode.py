#!/usr/bin/env python3
import sys
import time
import subprocess
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs


# --- KONFIGURATION ---
LISTEN_HOST = '0.0.0.0'          # Auf welcher IP soll der Proxy lauschen?
LISTEN_PORT = 8080               # Port des Proxys für den Client (z.B. VLC)
VDR_SERVER_HOST = '192.168.241.10' # IP deines VDR streamdev-servers
VDR_SERVER_PORT = 3000           # Port des VDR streamdev-servers (Standard: 3000)
DEFAULT_BITRATE = 'Original'           # Standard-Bitrate, falls keine angegeben
DEFAULT_SIZE = 'Original'        # Standard-Auflösung, falls keine angegeben
STREAMDEV_CHUNK_SIZE = 65536               # Puffergröße für das Streamen (64 KB)
# ---------------------

class ThreadingVDRServer(ThreadingMixIn, HTTPServer):
    """Erlaubt dem HTTP-Server, mehrere Verbindungen parallel in Threads zu bedienen."""
    daemon_threads = True

class VDRTranscodeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # URL und Query-Parameter parsen
        parsed_url = urlparse(self.path)
        path = parsed_url.path  # z.B. /TS/3
        query_params = parse_qs(parsed_url.query)
        
        # Bitrate und Auflösung aus den Parametern auslesen
        bitrate = query_params.get('bitrate', [DEFAULT_BITRATE])[0]
        size = query_params.get('size', [DEFAULT_SIZE])[0]
        
        # Ziel-URL auf dem VDR-Server (ohne Query-Parameter für VDR)
        vdr_url = f"http://{VDR_SERVER_HOST}:{VDR_SERVER_PORT}{path}"
        
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Client {self.client_address[0]} fordert Stream an: {path}")
        #print(f" -> Einstellungen: Bitrate={bitrate}, Auflösung={size if size else 'Original'}")
        print(f" -> Einstellungen: Bitrate={bitrate}, Auflösung={size}")

        if bitrate != DEFAULT_BITRATE or size != DEFAULT_SIZE:
            print(f" -> Transkodierung mit Intel QSV wird durchgeführt...")
            # FFmpeg Basis-Befehl zusammenstellen
            cmd = [
                'ffmpeg',
                '-hide_banner',
                '-loglevel', 'warning',
                '-i', vdr_url,
            ]

            # Wenn eine Zielauflösung angegeben wurde, FFmpeg Skalierungsfilter hinzufügen
            scale_filter = parse_size(size)
            if scale_filter:
                # Nutzt den Skalierungsfilter (skaliert vor dem Enkodieren auf Intel QSV)
                cmd.extend(['-vf', f'scale={scale_filter}'])

            # Intel QSV Encoder und restliche Parameter anhängen
            cmd.extend([
                '-c:v', 'h264_qsv',
                '-b:v', bitrate,
                '-maxrate', bitrate,
                '-bufsize', parse_bitrate_multiplier(bitrate),
                '-c:a', 'aac',
                '-b:a', '128k',
                '-f', 'mpegts',
                'pipe:1'
            ])

            process = None
            try:
                # FFmpeg-Prozess starten
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=10**8
                )

                # HTTP Header an den Client senden
                self.send_response(200)
                self.send_header('Content-Type', 'video/mpeg')
                self.send_header('Connection', 'close')
                self.end_headers()

                # Stream-Daten von FFmpeg an den Client weiterleiten
                while True:
                    chunk = process.stdout.read(STREAMDEV_CHUNK_SIZE)
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    except (ConnectionResetError, BrokenPipeError):
                        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Client {self.client_address[0]} hat die Verbindung getrennt.")
                        break

            except Exception as e:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Fehler beim Transkodieren: {e}")
            
            finally:
                # Sauberer Cleanup: FFmpeg-Prozess beenden, falls er noch läuft
                if process and process.poll() is None:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Beende FFmpeg-Prozess...")
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Stream-Session für {self.client_address[0]} beendet.")
        else:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Connecting upstream to VDR for full stream: {vdr_url}")

            req_headers = {}
            # Forward relevant headers if needed (like User-Agent)
            if 'User-Agent' in self.headers:
                req_headers['User-Agent'] = self.headers['User-Agent']

            req = urllib.request.Request(vdr_url, headers=req_headers)

            try:
                # Open connection to VDR streamdev server
                with urllib.request.urlopen(req, timeout=10) as vdr_response:
                    # Send HTTP status code back to client
                    self.send_response(vdr_response.status)
                    
                    # Forward response headers (Content-Type: video/mpeg, etc.)
                    for header, value in vdr_response.headers.items():
                        # Skip hop-by-hop or conflicting headers if necessary
                        if header.lower() in ['transfer-encoding', 'connection']:
                            continue
                        self.send_header(header, value)
                    
                    # Use chunked transfer or standard stream streaming
                    self.send_header('Connection', 'close')
                    self.end_headers()

                    # Stream data chunk by chunk from VDR to the client
                    while True:
                        chunk = vdr_response.read(STREAMDEV_CHUNK_SIZE)
                        if not chunk:
                            break
                        try:
                            self.wfile.write(chunk)
                            self.wfile.flush()
                        except (ConnectionResetError, BrokenPipeError):
                            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Client {self.client_address[0]} disconnected.")
                            break

            except urllib.error.HTTPError as e:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] VDR Server returned HTTP Error: {e.code} {e.reason}")
                try:
                    self.send_error(e.code, e.reason)
                except Exception:
                    pass
            except urllib.error.URLError as e:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Failed to connect to VDR server: {e.reason}")
                try:
                    self.send_error(502, f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Bad Gateway: Could not connect to VDR server ({e.reason})")
                except Exception:
                    pass
            except Exception as e:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Proxy error: {e}")
            
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Finished full stream session for {self.client_address[0]}")


    # Override to suppress all default HTTP server logging.
    # Note: Disabling logging may hinder debugging of HTTP requests and errors.
    def log_message(self, format, *args):
        return

def parse_bitrate_multiplier(bitrate_str):
    """Berechnet einen sinnvollen -bufsize Wert basierend auf dem String und gibt ihn mit Einheit zurück."""
    try:
        val = float(bitrate_str[:-1])
        unit = bitrate_str[-1].lower()
        if unit == 'm':
            return f"{int(val * 2)}M"
        elif unit == 'k':
            return f"{int(val * 2)}k"
    except Exception:
        pass
    return "4M"

def parse_size(res_str):
    """Wandelt Angaben wie '720p', '1080p' oder '1280x720' in FFmpeg-taugliche Skalierungswerte um."""
    if not res_str:
        return None
    
    res_str = res_str.lower().strip()
    
    # Gängige Shortcuts mappen
    presets = {
        '1080p': '1920:1080',
        '720p': '1280:720',
        '480p': '854:480',
        '576p': '720:576',
        '360p': '640:360',
        '240p': '426:240',
        '144p': '256:144'
    }
    
    if res_str in presets:
        return presets[res_str]
    
    # Manuelle Auflösungen im Format WxH (z.B. 1280x720) unterstützen
    if 'x' in res_str:
        parts = res_str.split('x')
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return f"{parts[0]}:{parts[1]}"
            
    return None

def run():
    server_address = (LISTEN_HOST, LISTEN_PORT)
    httpd = ThreadingVDRServer(server_address, VDRTranscodeHandler)
    print(f"VDR QSV Transcode-Proxy gestartet auf {LISTEN_HOST}:{LISTEN_PORT}")
    print(f"Leite zu VDR-Server weiter: {VDR_SERVER_HOST}:{VDR_SERVER_PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer wird heruntergefahren...")
        httpd.server_close()

if __name__ == '__main__':
    run()