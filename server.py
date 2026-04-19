import http.server
import socketserver
import sqlite3
import json
import urllib.parse
import os

# Configuration
PORT = 8000
DB_FILE = "users.db"

# Initialize Database
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  email TEXT NOT NULL,
                  password TEXT,
                  source TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS consultations
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  email TEXT NOT NULL,
                  severity_score INTEGER,
                  severity_label TEXT,
                  symptoms_json TEXT,
                  conditions_json TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS drug_checks
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  email TEXT NOT NULL,
                  medicine1 TEXT NOT NULL,
                  medicine2 TEXT NOT NULL,
                  severity TEXT NOT NULL,
                  interaction TEXT NOT NULL,
                  precautions_json TEXT NOT NULL,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()
    print("Database initialized.")

class MyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/consultations':
            qs = urllib.parse.parse_qs(parsed.query)
            email = (qs.get('email') or [None])[0]
            if not email:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error":"Missing email"}')
                return
            data = self.get_consultations(email)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
        elif parsed.path in ('/api/drug-check', '/api/drug-checks'):
            qs = urllib.parse.parse_qs(parsed.query)
            email = (qs.get('email') or [None])[0]
            if not email:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error":"Missing email"}')
                return
            data = self.get_drug_checks(email)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
        else:
            try:
                super().do_GET()
            except (ConnectionAbortedError, BrokenPipeError):
                pass
    def do_POST(self):
        if self.path == '/api/login':
            self.handle_login()
        elif self.path == '/api/google-login':
            self.handle_google_login()
        elif self.path == '/api/consultations':
            self.handle_consultation()
        elif self.path in ('/api/drug-check', '/api/drug-checks'):
            self.handle_drug_check()
        else:
            self.send_error(404, "Endpoint not found")

    def handle_login(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
            email = data.get('email')
            password = data.get('password')

            if not email or not password:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error": "Missing email or password"}')
                return

            # Save to DB
            self.save_user(email, password, 'email_password')
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"message": "Login successful", "status": "success"}')
            
        except Exception as e:
            print(f"Error: {e}")
            self.send_error(500, str(e))

    def handle_google_login(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
            email = data.get('email') # In a real app, verify token. Here we simulate saving.

            if not email:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error": "Missing email"}')
                return

            # Save to DB
            self.save_user(email, None, 'google')
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"message": "Google login successful", "status": "success"}')

        except Exception as e:
            print(f"Error: {e}")
            self.send_error(500, str(e))

    def save_user(self, email, password, source):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        # Simple insertion - in production, check if user exists, hash passwords, etc.
        c.execute("INSERT INTO users (email, password, source) VALUES (?, ?, ?)", (email, password, source))
        conn.commit()
        conn.close()
        print(f"User saved: {email} via {source}")
    def handle_consultation(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        try:
            data = json.loads(post_data.decode('utf-8'))
            email = data.get('email')
            severity_score = int(data.get('severity_score', 0))
            severity_label = data.get('severity_label') or ''
            symptoms_json = json.dumps(data.get('symptoms') or [])
            conditions_json = json.dumps(data.get('conditions') or [])
            if not email:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error":"Missing email"}')
                return
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT INTO consultations (email, severity_score, severity_label, symptoms_json, conditions_json) VALUES (?, ?, ?, ?, ?)",
                      (email, severity_score, severity_label, symptoms_json, conditions_json))
            conn.commit()
            conn.close()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        except Exception as e:
            print(f"Error: {e}")
            self.send_error(500, str(e))
    def get_consultations(self, email):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id, email, severity_score, severity_label, symptoms_json, conditions_json, timestamp FROM consultations WHERE email=? ORDER BY timestamp DESC", (email,))
        rows = c.fetchall()
        conn.close()
        result = []
        for r in rows:
            result.append({
                "id": r[0],
                "email": r[1],
                "severity_score": r[2],
                "severity_label": r[3],
                "symptoms": json.loads(r[4] or "[]"),
                "conditions": json.loads(r[5] or "[]"),
                "timestamp": r[6],
            })
        return result
    def handle_drug_check(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        try:
            raw = post_data.decode('utf-8', errors='ignore').strip()
            start = raw.find('{')
            if start > 0:
                raw = raw[start:]
            data = json.loads(raw)
            email = data.get('email')
            medicine1 = data.get('medicine1')
            medicine2 = data.get('medicine2')
            severity = data.get('severity') or ''
            interaction = data.get('interaction') or ''
            precautions = data.get('precautions') or []
            if not (email and medicine1 and medicine2 and severity and interaction):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error":"Missing required fields"}')
                return
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT INTO drug_checks (email, medicine1, medicine2, severity, interaction, precautions_json) VALUES (?, ?, ?, ?, ?, ?)",
                      (email, medicine1, medicine2, severity, interaction, json.dumps(precautions)))
            conn.commit()
            conn.close()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        except Exception as e:
            print(f"Error: {e}")
            self.send_error(500, str(e))
    def get_drug_checks(self, email):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id, email, medicine1, medicine2, severity, interaction, precautions_json, timestamp FROM drug_checks WHERE email=? ORDER BY timestamp DESC", (email,))
        rows = c.fetchall()
        conn.close()
        result = []
        for r in rows:
            result.append({
                "id": r[0],
                "email": r[1],
                "medicine1": r[2],
                "medicine2": r[3],
                "severity": r[4],
                "interaction": r[5],
                "precautions": json.loads(r[6] or "[]"),
                "timestamp": r[7],
            })
        return result

if __name__ == "__main__":
    init_db()
    with socketserver.TCPServer(("", PORT), MyHandler) as httpd:
        print(f"Serving at port {PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
