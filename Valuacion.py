import streamlit as st
import pandas as pd
import geopandas as gpd
import requests
import folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import st_folium

# Configuración
st.set_page_config(page_title="GERIE Consulta Valor Inmueble", layout="wide", page_icon="🏢")

# --- FUNCIONES DE INTELIGENCIA DE DATOS ---

@st.cache_data(ttl=3600)
def get_dolar_bna():
    try:
        response = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return response.json()['venta']
    except: return 1050.0

@st.cache_data
def cargar_datos_renabap():
    url = "https://datosabiertos.desarrollosocial.gob.ar/dataset/0d50730b-1662-4217-9ef1-37018c1b359f/resource/828292d3-96b4-4b9e-99e5-b1030e466b0a/download/barrios-populares.json"
    try: return gpd.read_file(url)
    except: return None

def analizar_entorno_real(lat, lon):
    """Consulta OpenStreetMap para detectar densidad comercial"""
    overpass_url = "http://overpass-api.de/api/interpreter"
    # Buscamos comercios, bancos o paradas de transporte en un radio de 400m
    query = f"""
    [out:json];
    (node(around:400,{lat},{lon})["amenity"];
     node(around:400,{lat},{lon})["shop"];);
    out count;
    """
    try:
        response = requests.get(overpass_url, params={'data': query}, timeout=5)
        count = int(response.json()['elements'][0]['tags']['total'])
        
        if count > 20:
            return "🏙️ ZONA CÉNTRICA / COMERCIAL", "Alta densidad de servicios y comercios detectada (Nivel Once/Centro)."
        elif count > 5:
            return "🏠 ZONA URBANA RESIDENCIAL", "Zona consolidada con servicios de proximidad."
        else:
            return "🌳 ZONA RURAL / SUBURBANA", "Baja densidad de servicios detectada en el entorno inmediato."
    except:
        return "🏙️ ZONA URBANA (Estimada)", "No se pudo conectar con el sensor de densidad comercial."

# --- INTERFAZ ---
st.title("🏢 GERIE: Consulta Valor Inmueble")

if 'data' not in st.session_state:
    st.session_state.data = None

with st.sidebar:
    st.header("📍 Parámetros de Tasación")
    with st.form("tasacion_form"):
        direccion = st.text_input("Dirección", "Av. Rivadavia 2000")
        localidad = st.text_input("Localidad/Provincia", "CABA")
        superficie = st.number_input("Superficie m2", min_value=1, value=50)
        btn = st.form_submit_button("TASAR PROPIEDAD")

dolar_bna = get_dolar_bna()

if btn:
    geolocator = Nominatim(user_agent="gerie_final")
    loc = geolocator.geocode(f"{direccion}, {localidad}, Argentina")

    if loc:
        # 1. Distancia RENABAP
        gdf = cargar_datos_renabap()
        dist_min = 99999
        if gdf is not None:
            for _, barrio in gdf.iterrows():
                d = geodesic((loc.latitude, loc.longitude), (barrio.geometry.centroid.y, barrio.geometry.centroid.x)).meters
                if d < dist_min: dist_min = d
        
        # 2. Análisis de Entorno Real (Nuevo)
        tipo_zona, desc_zona = analizar_entorno_real(loc.latitude, loc.longitude)
        
        st.session_state.data = {
            "lat": loc.latitude, "lon": loc.longitude, "address": loc.address,
            "dist_r": dist_min, "tipo": tipo_zona, "desc": desc_zona, "sup": superficie
        }

# --- RESULTADOS ---
if st.session_state.data:
    d = st.session_state.data
    
    st.info(f"💵 **Referencia Dólar BNA:** $ {dolar_bna}")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📊 Clasificación de Zona")
        st.markdown(f"**{d['tipo']}**")
        st.write(d['desc'])
    with col2:
        st.subheader("🛡️ Reporte RENABAP")
        if d['dist_r'] < 500:
            st.error(f"¡Alerta! Asentamiento detectado a {d['dist_r']:.0f}m.")
        else:
            st.success(f"Zona libre de asentamientos (Radio 500m).")

    # Lógica de Precios sugeridos (Basada en CABA por defecto para el ejemplo)
    m2_base = 2400 if "CABA" in d['address'].upper() else 1500
    if "CÉNTRICA" in d['tipo']: m2_base *= 1.1 # Bonus por zona comercial
    if d['dist_r'] < 500: m2_base *= 0.75 # Penalidad por riesgo

    st.divider()
    c1, c2, c3 = st.columns(3)
    val_usd = m2_base * d['sup']
    c1.metric("Valor Total USD", f"US$ {val_usd:,.0f}")
    c2.metric("Valor Total ARS", f"$ {val_usd * dolar_bna:,.0f}")
    c3.metric("M2 Sugerido", f"USD {m2_base:,.0f}")

    # Mapas
    t1, t2 = st.tabs(["Mapa de Ubicación", "Street View"])
    with t1:
        m = folium.Map(location=[d['lat'], d['lon']], zoom_start=17)
        folium.Marker([d['lat'], d['lon']], popup=d['address']).add_to(m)
        st_folium(m, height=400, width=None, key="mapa_v5")
    with t2:
        st.markdown(f'<iframe width="100%" height="450" src="https://maps.google.com/maps?q={d["lat"]},{d["lon"]}&layer=c&cbll={d["lat"]},{d["lon"]}&
