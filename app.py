import streamlit as st
import pandas as pd
import numpy as np
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
from geopy.geocoders import Nominatim
import time
import os

# ── Konfiguracja strony ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="dataplace.ai — Whitespot Analysis",
    page_icon="📍",
    layout="wide"
)

# ── Wczytanie danych ────────────────────────────────────────────────────────
PROCESSED_DIR = "01_data/procced"
DATA_DIR      = "01_data/raw"

@st.cache_data
def load_data():
    df_scores      = pd.read_csv(os.path.join(PROCESSED_DIR, 'whitespot_scores.csv'))
    df_locations   = pd.read_csv(os.path.join(DATA_DIR, 'ds_locations.csv'))
    df_competitors = pd.read_csv(os.path.join(DATA_DIR, 'ds_competitors.csv'))
    return df_scores, df_locations, df_competitors

df_scores, df_locations, df_competitors = load_data()

# ── Nagłówek ────────────────────────────────────────────────────────────────
st.title("📍 Whitespot Analysis — dataplace.ai")
st.markdown("Interaktywna analiza potencjalnych lokalizacji dla nowych sklepów spożywczych w regionie Śląsk/Kraków.")

# ── Sidebar — filtry ────────────────────────────────────────────────────────
st.sidebar.header("🔧 Filtry")

max_score = float(df_scores['score'].max())
max_pop   = int(df_scores['pop_total'].max())

min_score = st.sidebar.slider(
    "Minimalny score lokalizacji",
    min_value=0.0, max_value=max_score, value=10.0, step=0.1
)

min_pop = st.sidebar.slider(
    "Minimalna populacja w buforze 500m",
    min_value=0, max_value=max_pop, value=500, step=100
)

min_dist_comp = st.sidebar.slider(
    "Minimalna odległość od konkurencji (m)",
    min_value=0, max_value=2000, value=150, step=50
)

min_dist_client = st.sidebar.slider(
    "Minimalna odległość od własnej sieci (m)",
    min_value=0, max_value=5000, value=800, step=100
)

show_clients     = st.sidebar.checkbox("Pokaż sklepy klienta", value=True)
show_competitors = st.sidebar.checkbox("Pokaż konkurencję", value=True)
show_top10       = st.sidebar.checkbox("Pokaż TOP 10 whitespotów", value=True)

brand_filter = st.sidebar.multiselect(
    "Filtruj konkurencję po brandzie",
    options=sorted(df_competitors['brand'].unique()),
    default=sorted(df_competitors['brand'].unique())
)

# ── Filtrowanie ──────────────────────────────────────────────────────────────
df_filtered = df_scores[
    (df_scores['score']                     >= min_score) &
    (df_scores['pop_total']                 >= min_pop) &
    (df_scores['dist_nearest_competitor_m'] >= min_dist_comp) &
    (df_scores['dist_nearest_client_m']     >= min_dist_client)
].copy()

df_comp_filtered = df_competitors[df_competitors['brand'].isin(brand_filter)]

# ── Metryki ──────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric("Lokalizacji po filtrach",  f"{len(df_filtered):,}")
col2.metric("Najwyższy score",          f"{df_filtered['score'].max():.1f}"                  if len(df_filtered) > 0 else "—")
col3.metric("Max pred. przychód",       f"{df_filtered['predicted_revenue'].max():,.0f} PLN" if len(df_filtered) > 0 else "—")
col4.metric("Średnia populacja",        f"{df_filtered['pop_total'].mean():.0f}"             if len(df_filtered) > 0 else "—")

# ── Mapa ─────────────────────────────────────────────────────────────────────
st.subheader("🗺️ Mapa whitespotów")

BOUNDS = [[49.96, 18.54], [50.48, 20.12]]

m = folium.Map(
    location=[50.2, 19.0],
    zoom_start=10,
    tiles='CartoDB positron',
    min_zoom=9,
    max_zoom=16,
    max_bounds=True,
)
m.fit_bounds(BOUNDS)

# Heatmapa — wszystkie whitespoty
if len(df_filtered) > 0:
    heat_data = df_filtered[['lat', 'lng', 'score']].values.tolist()
    HeatMap(
        heat_data,
        radius=15,
        blur=10,
        min_opacity=0.3,
        gradient={0.4: 'blue', 0.65: 'lime', 1: 'red'}
    ).add_to(m)

# CircleMarker — tylko TOP 50
top50 = df_filtered.nlargest(50, 'score')
for _, row in top50.iterrows():
    color  = '#2ecc71' if row['score'] >= 25 else '#f39c12' if row['score'] >= 15 else '#3498db'
    radius = 3 + (row['score'] / max_score) * 6
    folium.CircleMarker(
        location=[row['lat'], row['lng']],
        radius=radius,
        color=color,
        fill=True,
        fill_opacity=0.8,
        tooltip=f"Score: {row['score']:.1f} | Pop: {row['pop_total']:.0f} | Pred: {row['predicted_revenue']:,.0f} PLN"
    ).add_to(m)

# Sklepy klienta
if show_clients:
    for _, row in df_locations.iterrows():
        folium.CircleMarker(
            location=[row['lat'], row['lng']],
            radius=8, color='#1a6bc9', fill=True, fill_opacity=0.9,
            tooltip=f"Klient: {row['location_id']}<br>Przychód: {row['monthly_revenue']:,.0f} PLN"
        ).add_to(m)

# Konkurencja
if show_competitors:
    for _, row in df_comp_filtered.iterrows():
        folium.CircleMarker(
            location=[row['lat'], row['lng']],
            radius=4, color='#e74c3c', fill=True, fill_opacity=0.7,
            tooltip=f"{row['brand']}"
        ).add_to(m)

# TOP 10
if show_top10 and len(df_filtered) > 0:
    top10 = df_filtered.nlargest(10, 'score')
    for rank, (_, row) in enumerate(top10.iterrows(), 1):
        folium.Marker(
            location=[row['lat'], row['lng']],
            icon=folium.DivIcon(
                html=f'<div style="background:#2ecc71;color:white;border-radius:50%;'
                     f'width:26px;height:26px;text-align:center;line-height:26px;'
                     f'font-weight:bold;font-size:12px;border:2px solid white">{rank}</div>',
                icon_size=(26, 26), icon_anchor=(13, 13)
            ),
            tooltip=f"TOP {rank} | Score: {row['score']:.1f} | Pred: {row['predicted_revenue']:,.0f} PLN"
        ).add_to(m)

st_folium(m, width=1200, height=600)

# ── Legenda ───────────────────────────────────────────────────────────────────
st.markdown("""
**Legenda mapy:**
🔵 Sklep klienta &nbsp;&nbsp;|&nbsp;&nbsp;
🔴 Konkurencja &nbsp;&nbsp;|&nbsp;&nbsp;
🟢 Whitespot score ≥ 25 &nbsp;&nbsp;|&nbsp;&nbsp;
🟠 Whitespot score 15–25 &nbsp;&nbsp;|&nbsp;&nbsp;
🔷 Whitespot score < 15 &nbsp;&nbsp;|&nbsp;&nbsp;
🟩 TOP 10 lokalizacja
""")

# ── Tabela TOP 10 ─────────────────────────────────────────────────────────────
st.subheader("🏆 TOP 10 lokalizacji")
if len(df_filtered) > 0:
    top10_table = df_filtered.nlargest(10, 'score')[
        ['lat', 'lng', 'score', 'predicted_revenue', 'pop_total',
         'building_count', 'competitor_count', 'dist_nearest_competitor_m',
         'dist_nearest_client_m']
    ].round(1).reset_index(drop=True)
    top10_table.index += 1

    @st.cache_data
    def get_addresses(coords):
        geolocator = Nominatim(user_agent="dataplace_whitespot")
        addresses = []
        for lat, lng in coords:
            try:
                loc = geolocator.reverse(f"{lat}, {lng}", language='pl')
                parts = loc.address.split(',')[:3]
                addresses.append(', '.join(parts))
                time.sleep(1)
            except:
                addresses.append('brak danych')
        return addresses

    coords = tuple(zip(top10_table['lat'], top10_table['lng']))
    top10_table.insert(0, 'adres', get_addresses(coords))

    st.dataframe(top10_table, use_container_width=True)

    csv = top10_table.to_csv(index=True).encode('utf-8')
    st.download_button(
        label="⬇️ Pobierz TOP 10 jako CSV",
        data=csv,
        file_name='top10_whitespots.csv',
        mime='text/csv'
    )
else:
    st.warning("Brak lokalizacji spełniających kryteria — zmień filtry.")

# ── Rozkład score ─────────────────────────────────────────────────────────────
st.subheader("📊 Rozkład score whitespotów")

fig, ax = plt.subplots(figsize=(10, 3))
ax.hist(df_filtered['score'], bins=30, color='steelblue', edgecolor='white')
ax.axvline(df_filtered['score'].median(), color='red', linestyle='--',
           label=f"Mediana: {df_filtered['score'].median():.1f}")
ax.set_xlabel('Score')
ax.set_ylabel('Liczba lokalizacji')
ax.set_title('Rozkład score przefiltrowanych whitespotów')
ax.legend()
st.pyplot(fig)

# ── Korelacja cech z przychodem ───────────────────────────────────────────────
st.subheader("📈 Korelacja cech z przychodem")

@st.cache_data
def load_features():
    return pd.read_csv(os.path.join(PROCESSED_DIR, 'features_extended.csv'))

df_feat = load_features()

feature_cols = [c for c in df_feat.columns
                if c not in ['location_id', 'lat', 'lng', 'monthly_revenue']]

corr = df_feat[feature_cols + ['monthly_revenue']].corr()['monthly_revenue'].drop('monthly_revenue')
corr_sorted = corr.sort_values()

fig2, ax2 = plt.subplots(figsize=(8, 10))
colors = ['#e74c3c' if v < 0 else '#2ecc71' for v in corr_sorted.values]
corr_sorted.plot(kind='barh', ax=ax2, color=colors)
ax2.axvline(0, color='black', linewidth=0.8)
ax2.set_title('Korelacja cech z monthly_revenue')
ax2.set_xlabel('Korelacja Pearsona')
plt.tight_layout()
st.pyplot(fig2)

# ── Metodologia ───────────────────────────────────────────────────────────────
st.subheader("📖 Metodologia")

st.markdown("""
### Jak działa scoring whitespotów?

**1. Feature Engineering**
Dla każdego punktu siatki (co 500m) obliczamy 31 cech przestrzennych w buforze 500m:
- 🚶 **Ruch pieszy** — sygnały mobilne z Snowflake (lipiec 2020)
- 🏠 **Zabudowa** — liczba i typ budynków (AWS S3)
- 👥 **Demografia** — populacja i gospodarstwa domowe (AWS S3)
- 📍 **POI** — generatory ruchu: restauracje, szkoły, przystanki (bufor 1km)
- 🏪 **Konkurencja** — liczba i odległość od konkurentów

**2. Model ML**
Model **Ridge Regression** wytrenowany na 50 istniejących sklepach klienta.
- CV R² = 0.393 — model wyjaśnia ~39% wariancji przychodów
- Najważniejsze cechy: `nearest_client_revenue`, `dist_nearest_client_m`, `total_building_area`

**3. Scoring**
Predykowany przychód normalizowany do skali 0–32.2 (maksimum w obszarze analizy).

**4. Filtrowanie**
Wykluczamy lokalizacje zbyt blisko istniejących punktów sieci i konkurencji.

| Filtr | Domyślna wartość |
|---|---|
| Min. odległość od sieci klienta | 800m |
| Min. odległość od konkurencji | 150m |
| Min. populacja w buforze | 500 osób |
""")