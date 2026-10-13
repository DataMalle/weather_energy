"""Visuellt tema: ljusgrå bas, vita kort med mjuk skugga, runda pills och teal/magenta som signalfärger.

Inspirerat av stilen hos moderna finansappar (t.ex. börssidor), men med grått som basfärg istället för svart.
"""
import streamlit as st

GRAY_900 = "#444444"  # primär text
GRAY_700 = "#4d4d4d"  # header-band
GRAY_500 = "#7a7a7a"  # sekundär text
GRAY_200 = "#e6e6e6"
GRAY_100 = "#f2f2f2"  # sidbakgrund
TEAL = "#157b93"
MAGENTA = "#d10e61"

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
html, body, .stApp, button, input, textarea {{ font-family: 'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif !important; }}
.stApp {{ background: {GRAY_100}; color: {GRAY_900}; }}
.block-container {{ padding-top: 1.5rem; max-width: 1180px; }}
header[data-testid="stHeader"] {{ background: transparent; }}
footer, #MainMenu {{ visibility: hidden; }}

h1, h2, h3 {{ color: {GRAY_900}; font-weight: 800; letter-spacing: -0.01em; }}
h3 {{ font-size: 1.15rem; }}

.hero {{ background: {GRAY_700}; border-radius: 8px; padding: 24px 28px; margin-bottom: 20px;
        box-shadow: 0 0 2px rgba(0,0,0,.12), 0 0 20px rgba(0,0,0,.06); }}
.hero h1 {{ color: #fff; font-size: 28px; margin: 0; padding: 0; }}
.hero p {{ color: #d6d6d6; margin: 6px 0 0; font-size: 15px; }}
.hero .live {{ display: inline-flex; align-items: center; gap: 8px; background: #666; color: #fff;
              border-radius: 100px; padding: 4px 12px; font-size: 13px; font-weight: 600; margin-bottom: 12px; }}
.hero .dot {{ width: 8px; height: 8px; border-radius: 50%; background: #5fd0e8; }}

[data-testid="stMetric"], [class*="st-key-card_"] {{
    background: #fff !important; border: none !important; border-radius: 8px;
    box-shadow: 0 0 2px rgba(0,0,0,.12), 0 0 20px rgba(0,0,0,.06); }}
[class*="st-key-card_"] {{ padding: 8px 12px; }}
[data-testid="stMetric"] {{ padding: 16px 18px; }}
[data-testid="stMetricLabel"] p {{ color: {GRAY_500}; font-weight: 600; font-size: 14px; }}
[data-testid="stMetricValue"] {{ color: {GRAY_900}; font-weight: 800; font-size: 1.7rem; }}
[data-testid="stMetricValue"] > div {{ text-overflow: clip; overflow: visible; white-space: nowrap; }}

button[data-baseweb="tab"] {{ font-weight: 700; color: {GRAY_500}; }}
button[data-baseweb="tab"][aria-selected="true"] {{ color: {GRAY_900}; }}
[data-baseweb="tab-highlight"] {{ background-color: {GRAY_900} !important; }}

.stButton > button, [data-testid="stButtonGroup"] button {{ border-radius: 100px; font-weight: 700; border: none; }}
[data-testid="stButtonGroup"] button {{ background: {GRAY_200} !important; color: {GRAY_900} !important; padding: 6px 16px; }}
[data-testid="stButtonGroup"] button[aria-checked="true"] {{ background: {GRAY_700} !important; color: #fff !important; }}
[data-testid="stButtonGroup"] button:hover {{ background: #d4d4d4 !important; }}
[data-testid="stButtonGroup"] button[aria-checked="true"]:hover {{ background: #5e5e5e !important; }}
.stButton > button {{ background: {GRAY_700}; color: #fff; }}

[data-testid="stCaptionContainer"] {{ color: {GRAY_500}; }}
</style>
"""


def inject_style() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str, badge: str) -> None:
    st.markdown(
        f'<div class="hero"><div class="live"><span class="dot"></span>{badge}</div><h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )
