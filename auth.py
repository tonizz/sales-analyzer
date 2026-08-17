"""
auth.py — Modul autentikasi terpusat untuk semua halaman Streamlit.

Menggantikan ~20 baris duplikasi auth di setiap halaman:
    - bundle_analyzer_web.py
    - pages/1_Stock_Sales_Analyzer.py
    - pages/2_YoY_Forecast.py
    - pages/3_Stock_Card.py
    - pages/4_Stock_Opname.py

Pakai:
    from auth import login_gate, render_logout

    login_gate(subtitle="Stock Card")   # tampilkan login, st.stop() jika belum
    ...
    render_logout()                     # caption user + tombol Logout di sidebar

Sumber kredensial (prioritas):
    1. st.secrets["users"]  -> dict {username: bcrypt_hash}
       (set via Streamlit Cloud: Settings -> Secrets, format TOML:
           [users]
           admin = "$2b$12$..." )
    2. Fallback DEV (bcrypt hash di source code, username: admin & tonizz).
       HANYA dipakai kalau secrets belum diset. Password default TIDAK
       pernah ditampilkan di UI.

KEAMANAN:
    - Tidak ada hint password plaintext di UI (dipakai di repo & app live).
    - Untuk production WAJIB isi Streamlit Cloud Secrets.
    - Session state di-share antar halaman (login sekali untuk semua page).
"""
from __future__ import annotations

import hmac
import uuid

import bcrypt
import streamlit as st

# ---------------------------------------------------------------------------
# Fallback dev-only (bcrypt). Tidak dipajang di UI; ganti via Secrets.
# ---------------------------------------------------------------------------
_FALLBACK_USERS = {
    "admin": "$2b$12$38P/ATKNv3p/d2kKebfxouS8TPeFZgSs9837E2oUSsewRe5uA7klq",
    "tonizz": "$2b$12$FKS3raeR9UZtbeNsqwvfAe5hKc6oC6LhP2Rkok6LZCjsj2BZFHVw.",
}


def get_users() -> tuple[dict, bool]:
    """Return (users_dict, from_secrets). secrets diprioritaskan."""
    try:
        if "users" in st.secrets:
            return dict(st.secrets["users"]), True
    except Exception:
        pass
    return dict(_FALLBACK_USERS), False


def _verify(password: str, stored: str) -> bool:
    """Verifikasi password. Support bcrypt hash dan (legacy) plaintext,
    keduanya constant-time."""
    if not stored:
        return False
    if stored.startswith(("$2b$", "$2a$", "$2y$")):
        try:
            return bcrypt.checkpw(password.encode(), stored.encode())
        except Exception:
            return False
    return hmac.compare_digest(password, stored)


def login_gate(subtitle: str = "", form_key: str | None = None) -> bool:
    """Tampilkan login form; stop eksekusi kalau belum login.

    Set dua flag session state sekaligus agar kompatibel dengan semua
    halaman lama: ``logged_in`` (pages 1-3 & app utama) dan
    ``authenticated`` (page Stock Opname).
    """
    if st.session_state.get("logged_in") or st.session_state.get("authenticated"):
        return True

    key = form_key or f"login_{uuid.uuid4().hex[:8]}"
    users, from_secrets = get_users()

    st.markdown(
        f"""
<div style="max-width: 420px; margin: 4rem auto; padding: 2.5rem;
            background: white; border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);">
    <h2 style="text-align: center; color: #1f77b4; margin: 0 0 0.5rem 0;">🔐 Login</h2>
    <p style="text-align: center; color: #666; margin: 0 0 1.5rem 0;">
        {subtitle or "Sales Analyzer"} — Akses Terbatas
    </p>
</div>
""",
        unsafe_allow_html=True,
    )

    with st.form(key, clear_on_submit=True):
        u = st.text_input("Username", key=f"{key}_user")
        p = st.text_input("Password", type="password", key=f"{key}_pw")
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            submit = st.form_submit_button("Masuk", use_container_width=True, type="primary")
        if submit:
            stored = users.get(u)
            if stored and _verify(p, stored):
                st.session_state.logged_in = True
                st.session_state.authenticated = True
                st.session_state.user = u
                st.rerun()
            else:
                st.error("❌ Username atau password salah.")

    if not from_secrets:
        st.caption(
            "⚠️ Credentials default (dev) sedang dipakai. Untuk production, "
            "set `[users]` di Streamlit Cloud > Settings > Secrets."
        )
    st.stop()
    return False


def logout() -> None:
    """Clear semua flag login."""
    st.session_state.logged_in = False
    st.session_state.authenticated = False
    st.session_state.user = None


def render_logout(key: str | None = None) -> None:
    """Caption user + tombol Logout (untuk dipasang di sidebar)."""
    st.caption(f"👤 Login sebagai: **{st.session_state.get('user', '?')}**")
    if st.button("🚪 Logout", use_container_width=True, key=key or "logout_shared"):
        logout()
        st.rerun()
