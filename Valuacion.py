import streamlit as st
import pandas as pd
import geopandas as gpd
import requests
import folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import st_folium

# Configuración de página
st.set_page_config(page_title="GERIE Consulta Valor Inmueble", layout="wide", page_icon="🏢")

# --- FUNCIONES DE DATOS ---

@st.cache_data(ttl=3600)
def get_dolar_bna():
    try:
        # Consulta a API de Dólar Oficial (Referencia BNA)
        response = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return response.json()['venta']
    except:
        return 1050.0 # Valor manual si falla la API

@st.cache_data
def cargar_datos_renabap():
    url = "https://datosabiertos.desarrollosocial.gob.ar/dataset/0d50730b-1662-4217-9ef1-37018c1b359f/resource/828292d3-96b4-4b9e-99e5-b1030e466b0a/download/barrios-populares.json"
    try:
        return gpd.read_file(url)
    except: return None

def clasificar_zona(lat, lon, dist_renabap):
    # Lógica de clasificación de entorno
    if dist_renabap < 500:
        return "⚠️ ZONA DE RIESGO / ASENTAMIENTO", "Cercanía inmediata a barrio registrado en RENABAP. Impacto alto en valor."
    
    # Clasificación simple por distancia al "centro" (simulado para este ejemplo)
    # En una versión pro, aquí se usarían polígonos de zonificación urbana
    if dist_renabap > 5000:
        return "🌳 ZONA RURAL / SEMI-RURAL", "Baja densidad, alejado de centros urbanos consolidados."
    
    return "🏙️ ZONA URBANA / CÉNTRICA", "Zona consolidada con acceso a servicios y transporte."

# --- INTERFAZ ---
st.title("🏢 GERIE: Consulta Valor Inmueble")

# Inicializar estado para que no desaparezca
if 'data' not in st.session_state:
    st.session_state.data = None

with st.sidebar:
    st.header("📍 Datos de Tasación")
    with st.form("tasacion_form"):
        direccion = st.text_input("Dirección (Calle y Altura)", "Av. Rivadavia 2000")
        localidad = st.text_input("Localidad y Provincia", "CABA")
        superficie = st.number_input("Superficie Total (m2)", min_value=1, value=50)
        btn = st.form_submit_button("EJECUTAR CONSULTA")

dolar_bna = get_dolar_bna()

if btn:
    geolocator = Nominatim(user_agent="gerie_app_v4")
    loc = geolocator.geocode(f"{direccion}, {localidad}, Argentina")

    if loc:
        # Buscamos en RENABAP
        gdf = cargar_datos_renabap()
        dist_min = 99999
        if gdf is not None:
            for _, barrio in gdf.iterrows():
                d = geodesic((loc.latitude, loc.longitude), (barrio.geometry.centroid.y, barrio.geometry.centroid.x)).meters
                if d < dist_min: dist_min = d
        
        # Clasificamos la zona
        tipo_zona, desc_zona = clasificar_zona(loc.latitude, loc.longitude, dist_min)
        
        # Guardamos en estado
        st.session_state.data = {
            "lat": loc.latitude, "lon": loc.longitude, "address": loc.address,
            "dist": dist_min, "tipo": tipo_zona, "desc": desc_zona,
            "sup": superficie
        }
    else:
        st.error("Dirección no encontrada.")

# --- MOSTRAR RESULTADOS ---
if st.session_state.data:
    d = st.session_state.data
    
    # REFERENCIAS PRINCIPALES
    st.info(f"💵 **Cotización BNA del día:** $ {dolar_bna}")
    
    col_z1, col_z2 = st.columns(2)
    with col_z1:
        st.subheader("📍 Clasificación de la Zona")
        st.markdown(f"**{d['tipo']}**")
        st.caption(d['desc'])
    
    with col_z2:
        st.subheader("🛡️ Referencia RENABAP")
        if d['dist'] < 500:
            st.error(f"Asentamiento detectado a {d['dist']:.0f} metros.")
        else:
            st.success(f"Sin asentamientos cercanos (Distancia: {d['dist']/1000:.1f} km).")

    # VALORES (Simulación de m2 según zona)
    factor = 0.75 if d['dist'] < 500 else 1.0
    m2_avg = 2200 * factor # Base CABA/GBA ajustada
    
    st.divider()
    
    # Métrica de Valor Total
    c1, c2, c3 = st.columns(3)
    val_usd = m2_avg * d['sup']
    c1.metric("Valor Total (USD)", f"US$ {val_usd:,.0f}")
    c2.metric("Valor Total (ARS)", f"$ {val_usd * dolar_bna:,.0f}")
    c3.metric("M2 Promedio", f"USD {m2_avg:,.0f}")

    # MAPAS
    t1, t2 = st.tabs(["Ubicación", "Street View"])
    with t1:
        m = folium.Map(location=[d['lat'], d['lon']], zoom_start=16)
        folium.Marker([d['lat'], d['lon']], popup=d['address']).add_to(m)
        st_folium(m, height=400, width=800, key="mapa_final")
    with t2:
        st.markdown(f'<iframe width="100%" height="450" src="https://maps.google.com/maps?q={d["lat"]},{d["lon"]}&layer=c&cbll={d["lat"]},{d["lon"]}&output=svembed"></iframe>', unsafe_allow_html=True)
