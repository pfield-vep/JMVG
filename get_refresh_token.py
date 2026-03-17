"""
get_refresh_token.py
Run this ONCE on your local machine to get a refresh token.
The refresh token gets stored in GitHub Secrets and used by the automation.

Usage:
    py get_refresh_token.py
"""

import json
import urllib.parse
import urllib.request
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler

CLIENT_ID  = "44f09a6a-eae4-43d6-bd80-3c806a3b2d1a"
TENANT_ID  = "8dc59d31-158a-4afd-855d-446c26c6adc7"
REDIRECT   = "http://localhost:8765"
SCOPES     = "Mail.Read offline_access"

auth_code = None

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
        auth_code = params.get("code")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<h2>Login successful! You can close this tab.</h2>")

    def log_message(self, format, *args):
        pass  # suppress server logs

def run():
    # Build auth URL
    auth_url = (
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={urllib.parse.quote(REDIRECT)}"
        f"&scope={urllib.parse.quote(SCOPES)}"
        f"&prompt=select_account"
    )

    print("\n" + "="*60)
    print("JERSEY MIKE'S — ONE-TIME LOGIN")
    print("="*60)
    print("\nOpening browser for Microsoft login...")
    print("Sign in with your VantEdge email account.")
    print("\nIf browser doesn't open, visit this URL manually:")
    print(auth_url)
    print()

    webbrowser.open(auth_url)

    # Start local server to catch the redirect
    server = HTTPServer(("localhost", 8765), Handler)
    print("Waiting for login...")
    server.handle_request()

    if not auth_code:
        print("[ERROR] No auth code received. Try again.")
        return

    print("[OK] Login successful. Exchanging code for tokens...")

    # Exchange code for tokens
    token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = urllib.parse.urlencode({
        "grant_type":    "authorization_code",
        "client_id":     CLIENT_ID,
        "code":          auth_code,
        "redirect_uri":  REDIRECT,
        "scope":         SCOPES,
    }).encode()

    req = urllib.request.Request(token_url, data=data, method="POST")
    with urllib.request.urlopen(req) as resp:
        tokens = json.loads(resp.read())

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        print(f"[ERROR] No refresh token received: {tokens}")
        return

    print("\n" + "="*60)
    print("SUCCESS! Here is your refresh token:")
    print("="*60)
    print(f"\n{refresh_token}\n")
    print("="*60)
    print("\nNEXT STEPS:")
    print("1. Go to github.com/pfield-vep/JMVG/settings/secrets/actions")
    print("2. Click 'New repository secret'")
    print("3. Name:  AZURE_REFRESH_TOKEN")
    print("4. Value: paste the token above")
    print("5. Click 'Add secret'")
    print("\nThe token is also saved to refresh_token.txt in this folder.")
    print("DELETE that file after copying the token to GitHub!\n")

    with open("refresh_token.txt", "w") as f:
        f.write(refresh_token)

if __name__ == "__main__":
    run()
