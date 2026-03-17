import msal
import requests
import json
import os

# Azure App Registration credentials
CLIENT_ID = "44f09a6a-eae4-43d6-bd80-3c806a3b2d1a"
TENANT_ID = "8dc59d31-158a-4afd-855d-446c26c6adc7"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["Mail.Read", "Mail.ReadBasic", "User.Read"]

# Token cache file — keeps you logged in between runs
TOKEN_CACHE_FILE = "token_cache.json"


def load_token_cache():
    cache = msal.SerializableTokenCache()
    if os.path.exists(TOKEN_CACHE_FILE):
        with open(TOKEN_CACHE_FILE, "r") as f:
            cache.deserialize(f.read())
    return cache


def save_token_cache(cache):
    if cache.has_state_changed:
        with open(TOKEN_CACHE_FILE, "w") as f:
            f.write(cache.serialize())


def get_access_token():
    cache = load_token_cache()

    app = msal.PublicClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        token_cache=cache
    )

    # Try to get token silently from cache first
    accounts = app.get_accounts()
    result = None

    if accounts:
        print(f"Found cached account: {accounts[0]['username']}")
        result = app.acquire_token_silent(SCOPES, account=accounts[0])

    # If no cached token, do interactive login (opens browser)
    if not result:
        print("No cached token found. Opening browser for login...")
        result = app.acquire_token_interactive(scopes=SCOPES)

    save_token_cache(cache)

    if "access_token" in result:
        print("✅ Authentication successful!")
        return result["access_token"]
    else:
        print("❌ Authentication failed.")
        print(result.get("error_description", "Unknown error"))
        return None


def verify_connection(token):
    """Quick test — fetches your profile to confirm the token works."""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers)

    if response.status_code == 200:
        profile = response.json()
        print(f"\n✅ Connected as: {profile.get('displayName')} ({profile.get('mail') or profile.get('userPrincipalName')})")
        return True
    else:
        print(f"❌ Graph API call failed: {response.status_code} - {response.text}")
        return False


if __name__ == "__main__":
    token = get_access_token()
    if token:
        verify_connection(token)
        print("\nToken acquired and saved. You're ready for the next step.")
