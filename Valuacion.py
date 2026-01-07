import streamlit as st
import pandas as pd
import geopandas as gpd
import requests
import folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import st_folium

# Configuración GERIE
st.set_page_config(page_title="GERIE Consulta Valor Inmueble", layout="wide", page_icon="🏢")

# --- FUNCIONES ---
@st.cache_data(ttl=3600)
def get_dolar_bna():
    try:
        response = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return response.json()['venta']
    except: return 1025.0

@st.cache_data
def cargar_datos_renabap():
    url = "https://datosabiertos.desarrollosocial.gob.ar/dataset/0d50730b-1662-4217-9ef1-37018c1b359f/resource/828292d3-96b4-4b9e-99e5-b1030e466b0a/download/barrios-populares.json"
    try: return gpd.read_file(url)
    except: return None

def analizar_entorno_dinamico(lat, lon):
    url = "http://overpass-api.de/api/interpreter"
    query = f"""[out:json];(node(around:400,{lat},{lon})["amenity"];node(around:400,{lat},{lon})["shop"];);out count;"""
    try:
        resp = requests.get(url, params={'data': query}, timeout=5)
        count = int(resp.json()['elements'][0]['tags']['total'])
        if count > 25: return "🏙️ ZONA CÉNTRICA / COMERCIAL", 1.15
        if count > 8: return "🏠 ZONA URBANA RESIDENCIAL", 1.0
        return "🌳 ZONA RURAL / SUBURBANA", 0.85
    except: return "🏙️ ZONA URBANA (Estándar)", 1.0

# --- INTERFAZ ---
st.title("🏢 GERIE: Consulta Valor Inmueble")

if 'data' not in st.session_state:
    st.session_state.data = None

with st.sidebar:
    st.header("📋 Datos del Inmueble")
    with st.form("form_gerie"):
        direccion = st.text_input("Calle y Altura", "Av. Rivadavia 2000")
        localidad = st.text_input("Ciudad / Provincia", "CABA")
        tipo_inmueble = st.selectbox("Tipo de Inmueble", ["Departamento", "Casa", "Local Comercial", "Oficina"])
        superficie = st.number_input("Superficie Total (m2)", min_value=1, value=50)
        btn = st.form_submit_button("INICIAR TASACIÓN")

dolar_bna = get_dolar_bna()

if btn:
    with st.spinner('Analizando...'):
        geolocator = Nominatim(user_agent="gerie_v5")
        loc = geolocator.geocode(f"{direccion}, {localidad}, Argentina")
        if loc:
            gdf = cargar_datos_renabap()
            dist_r = 99999
            if gdf is not None:
                for _, b in gdf.iterrows():
                    d = geodesic((loc.latitude, loc.longitude), (b.geometry.centroid.y, b.geometry.centroid.x)).meters
                    if d < dist_r: dist_r = d
            
            tipo_z, mult_z = analizar_entorno_dinamico(loc.latitude, loc.longitude)
            coef_tipo = {"Departamento": 1.0, "Casa": 0.9, "Local Comercial": 1.4, "Oficina": 1.1}
            
            st.session_state.data = {
                "lat": loc.latitude, "lon": loc.longitude, "address": loc.address,
                "dist_r": dist_r, "tipo_z": tipo_z, "mult_z": mult_z,
                "sup": superficie, "tipo_inm": tipo_inmueble, "coef_t": coef_tipo[tipo_inmueble]
            }

# --- RESULTADOS ---
if st.session_state.data:
    res = st.session_state.data
    st.info(f"🏦 **Cotización Referencia BNA:** 1 USD = **$ {dolar_bna}**")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.info(f"**{res['tipo_z']}**")
    with col_b:
        if res['dist_r'] < 500: st.error(f"RIESGO: Asentamiento a {res['dist_r']:.0f}m")
        else: st.success("Zona libre de asentamientos (RENABAP)")
    with col_c:
        st.write(f"Inmueble: **{res['tipo_inm']}**")

    precio_base = 2300 if "CABA" in res['address'].upper() else 1400
    riesgo_mult = 0.75 if res['dist_r'] < 500 else 1.0
    m2_final = precio_base * res['mult_z'] * res['coef_t'] * riesgo_mult
    val_total_usd = m2_final * res['sup']
    
    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("VALOR TOTAL USD", f"US$ {val_total_usd:,.0f}")
    m2.metric("TOTAL ARS (BNA)", f"$ {val_total_usd * dolar_bna:,.0f}")
    m3.metric("VALOR M2", f"USD {m2_final:,.0f}")

    tab_map, tab_sv = st.tabs(["🗺️ Mapa", "📷 Street View"])
    with tab_map:
        m = folium.Map(location=[res['lat'], res['lon']], zoom_start=17)
        folium.Marker([res['lat'], res['lon']]).add_to(m)
        st_folium(m, width=None, height=450, key="mapa_ok")
    with tab_sv:
        # LÍNEA CORREGIDA:
        url_sv = f"https://maps.google.com/maps?q={res['lat']},{res['lon']}&layer=c&cbll={res['lat']},{res['lon']}&output=svembed"
        st.markdown(f'<iframe width="100%" height="450" src="{url_sv}" frameborder="0"></iframe>', unsafe_allow_html=True)
