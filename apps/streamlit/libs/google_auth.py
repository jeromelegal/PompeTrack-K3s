import streamlit as st
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import json
import os

# Scopes nécessaires pour lire/écrire le calendrier
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

REDIRECT_URI = os.getenv("REDIRECT_URI", "http://192.168.2.88.nip.io:8501/calendar")

CREDENTIALS_FILE = "credentials.json"


def get_flow():
    """Crée et retourne le Flow OAuth2."""
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    return flow


def init_auth():
    """
    Gère le cycle complet d'authentification OAuth2.
    Retourne True si l'utilisateur est connecté, False sinon.
    """

    # Déjà authentifié en session
    if "credentials" in st.session_state:
        creds = Credentials(**st.session_state["credentials"])

        # Rafraîchit le token si expiré
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            st.session_state["credentials"] = credentials_to_dict(creds)

        return True

    # Récupère le code OAuth depuis l'URL après redirection Google
    query_params = st.query_params
    if "code" in query_params:
        flow = get_flow()
        flow.fetch_token(code=query_params["code"])
        creds = flow.credentials
        st.session_state["credentials"] = credentials_to_dict(creds)

        # Nettoie l'URL
        st.query_params.clear()
        st.rerun()

    # Pas encore connecté : affiche le bouton de login
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


def get_credentials():
    """Retourne les credentials Google depuis la session."""
    if "credentials" not in st.session_state:
        return None
    return Credentials(**st.session_state["credentials"])


def logout():
    """Supprime les credentials de la session."""
    if "credentials" in st.session_state:
        del st.session_state["credentials"]
    st.query_params.clear()
    st.rerun()


def credentials_to_dict(creds):
    """Convertit les credentials en dictionnaire sérialisable."""
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }
