import streamlit as st
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import json
import os

# Necessary scopes
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

REDIRECT_URI = os.getenv("REDIRECT_URI", "http://192.168.2.88.nip.io/calendar")

CREDENTIALS_FILE = "credentials.json"

# Function to create and return the Flow OAuth2
def get_flow():
    """
    Create and return the Flow OAuth2.
    """
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    return flow

# Function to initialize the authentication
def init_auth():
    """
    Initialize the authentication.
    """

    # Everything is already connected
    if "credentials" in st.session_state:
        creds = Credentials(**st.session_state["credentials"])

        # If the token is expired, refresh it
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            st.session_state["credentials"] = credentials_to_dict(creds)

        return True

    # Already connected with a code
    query_params = st.query_params
    if "code" in query_params:
        flow = get_flow()
        flow.fetch_token(code=query_params["code"])
        creds = flow.credentials
        st.session_state["credentials"] = credentials_to_dict(creds)

        # Clear the query params
        st.query_params.clear()
        st.rerun()

    # No credentials yet
    flow = get_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    st.title("📅 Google Calendar App")
    st.markdown("### Connecte-toi pour accéder à ton calendrier")
    st.link_button("🔐 Se connecter avec Google", auth_url)

    return False

# Function to get the credentials
def get_credentials():
    """
    Return the credentials.
    """
    if "credentials" not in st.session_state:
        return None
    return Credentials(**st.session_state["credentials"])

# Function to logout
def logout():
    """
    Delete the credentials.
    """
    if "credentials" in st.session_state:
        del st.session_state["credentials"]
    st.query_params.clear()
    st.rerun()

# Function to convert credentials
def credentials_to_dict(creds):
    """
    Convert credentials to a dictionary.
    """
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }
