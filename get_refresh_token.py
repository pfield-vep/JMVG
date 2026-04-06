"""
get_refresh_token.py
Run ONCE on your local machine to get a refresh token.
Stores it in refresh_token.txt — copy to GitHub Secrets then delete the file.
"""
import json, urllib.parse, urllib.request, webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler

CLIENT_ID     = "44f09a6a-eae4-43d6-bd80-3c806a3b2d1a"
TENANT_ID     = "8dc59d31-158a-4afd-855d-446c26c6adc7"
REDIRECT      = "http://localhost:8765"
SCOPES        = "https://graph.microsoft.com/Mail.Read offline_access"

auth_code = None

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
        auth_code = params.get("code")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<h2>Login successful! Close this tab.</h2>")
    def log_message(self, format, *args):
        pass

def run():
    auth_url = (
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={urllib.parse.quote(REDIRECT)}"
        f"&scope={urllib.parse.quote(SCOPES)}"
        f"&prompt=select_account"
    )
    print("\nOpening browser for Microsoft login...")
    webbrowser.open(auth_url)
    print("Waiting for login...")
    HTTPServer(("localhost", 8765), Handler).handle_request()

    if not auth_code:
        print("[ERROR] No auth code received.")
        return

    print("[OK] Got auth code. Exchanging for tokens...")

    token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = urllib.parse.urlencode({
        "grant_type":   "authorization_code",
        "client_id":    CLIENT_ID,
        "code":         auth_code,
        "redirect_uri": REDIRECT,
        "scope":        SCOPES,
    }).encode()

    req = urllib.request.Request(token_url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            tokens = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"[ERROR] {e.code}: {e.read().decode()}")
        return

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        print(f"[ERROR] No refresh token: {tokens}")
        return

    print("\n" + "="*60)
    print("SUCCESS! Refresh token:")
    print("="*60)
    print(refresh_token)
    print("="*60)
    print("\n1. Go to github.com/pfield-vep/JMVG/settings/secrets/actions")
    print("2. Update AZURE_REFRESH_TOKEN with the value above")
    print("3. Delete refresh_token.txt after copying!\n")

    with open("refresh_token.txt", "w") as f:
        f.write(refresh_token)
    print("Also saved to refresh_token.txt")

if __name__ == "__main__":
    run()
