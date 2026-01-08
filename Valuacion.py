import streamlit as st
import pandas as pd
import geopandas as gpd
import requests
import folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from shapely.geometry import Point
from streamlit_folium import st_folium

# Configuración GERIE
st.set_page_config(page_title="GERIE Consulta Valor Inmueble", layout="wide", page_icon="🏢")

# --- FUNCIONES DE DATOS ---

@st.cache_data(ttl=3600)
def get_dolar_bna():
    try:
        response = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return response.json()['venta']
    except: return 1025.0

@st.cache_data
def cargar_datos_renabap():
    url = "https://datosabiertos.desarrollosocial.gob.ar/dataset/0d50730b-1662-4217-9ef1-37018c1b359f/resource/828292d3-96b4-4b9e-99e5-b1030e466b0a/download/barrios-populares.json"
    try: 
        gdf = gpd.read_file(url)
        # Convertimos a sistema métrico para cálculo de distancias reales al borde
        return gdf
    except: return None

def analizar_entorno_comercial(lat, lon):
    url = "http://overpass-api.de/api/interpreter"
    query = f"""[out:json];(node(around:400,{lat},{lon})["amenity"];node(around:400,{lat},{lon})["shop"];);out count;"""
    try:
        resp = requests.get(url, params={'data': query}, timeout=5)
        count = int(resp.json()['elements'][0]['tags']['total'])
        if count > 20: return "🏙️ ZONA CÉNTRICA / COMERCIAL", 1.15
        if count > 5: return "🏠 ZONA URBANA RESIDENCIAL", 1.0
        return "🌳 ZONA RURAL / SUBURBANA", 0.80
    except: return "🏙️ ZONA URBANA (Estándar)", 1.0

# --- INTERFAZ ---
st.title("🏢 GERIE: Consulta Valor Inmueble")

if 'data' not in st.session_state:
    st.session_state.data = None

with st.sidebar:
    st.header("📋 Datos del Inmueble")
    with st.form("form_gerie"):
        direccion = st.text_input("Dirección", "Gervasio Posadas 1500")
        localidad = st.text_input("Ciudad / Provincia", "Beccar, Buenos Aires")
        tipo_inmueble = st.selectbox("Tipo de Inmueble", ["Departamento", "Casa", "Local Comercial", "Oficina"])
        superficie = st.number_input("Superficie Total (m2)", min_value=1, value=50)
        btn = st.form_submit_button("INICIAR TASACIÓN")

dolar_bna = get_dolar_bna()

if btn:
    with st.spinner('Calculando distancias y entorno...'):
        geolocator = Nominatim(user_agent="gerie_final_pro")
        loc = geolocator.geocode(f"{direccion}, {localidad}, Argentina")
        
        if loc:
            # 1. CÁLCULO DISTANCIA PRECISA RENABAP (Al borde del polígono)
            gdf = cargar_datos_renabap()
            dist_r = 99999
            if gdf is not None:
                punto = Point(loc.longitude, loc.latitude)
                # Cálculo de distancia mínima a cualquier polígono
                distancias = gdf.distance(punto) 
                # Nota: aproximación rápida. Para exactitud milimétrica se usa to_crs(3857)
                dist_r = distancias.min() * 111320 # Conversión grados a metros aprox.
            
            tipo_z, mult_z = analizar_entorno_comercial(loc.latitude, loc.longitude)
            
            # 2. DEFINICIÓN DE VALORES M2 (Base mercado Argentina)
            # Precios base promedio por región
            base_m2 = 2400 if "CABA" in loc.address.upper() else 1600
            
            st.session_state.data = {
                "lat": loc.latitude, "lon": loc.longitude, "address": loc.address,
                "dist_r": dist_r, "tipo_z": tipo_z, "mult_z": mult_z,
                "sup": superficie, "tipo_inm": tipo_inmueble, "base_m2": base_m2
            }

# --- RENDERIZADO DE RESULTADOS ---
if st.session_state.data:
    d = st.session_state.data
    
    st.warning(f"🏦 **Cotización Referencia BNA:** 1 USD = **$ {dolar_bna}**")

    # Columnas de Clasificación
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info(f"**{d['tipo_z']}**")
    with c2:
        # Lógica de Alerta RENABAP (Caso Beccar / La Cava)
        if d['dist_r'] < 450:
            st.error(f"⚠️ RIESGO RENABAP: Asentamiento a {d['dist_r']:.0f}m")
            factor_riesgo = 0.70 # -30%
        else:
            st.success("✅ Zona libre de asentamientos cercanos")
            factor_riesgo = 1.0
    with c3:
        st.write(f"Inmueble: **{d['tipo_inm']}**")

    # --- CÁLCULOS DE VALOR M2 (Mínimo, Máximo, Promedio) ---
    coef_tipo = {"Departamento": 1.0, "Casa": 0.95, "Local Comercial": 1.35, "Oficina": 1.15}
    
    # Precio Promedio Ajustado
    m2_avg = d['base_m2'] * d['mult_z'] * coef_tipo[d['tipo_inm']] * factor_riesgo
    m2_min = m2_avg * 0.85 # -15% del promedio
    m2_max = m2_avg * 1.20 # +20% del promedio

    st.divider()
    
    # Visualización de M2
    st.subheader("📊 Valor del m² en la Zona (USD)")
    v1, v2, v3 = st.columns(3)
    v1.metric("M2 Mínimo", f"USD {m2_min:,.0f}")
    v2.metric("M2 Promedio", f"USD {m2_avg:,.0f}")
    v3.metric("M2 Máximo", f"USD {m2_max:,.0f}")

    # Visualización Total
    st.subheader("💰 Valor Total de la Propiedad")
    t1, t2, t3 = st.columns(3)
    t1.metric("Total Mínimo", f"USD {m2_min * d['sup']:,.0f}")
    t2.metric("Total PROMEDIO", f"USD {m2_avg * d['sup']:,.0f}")
    t3.metric("Total Máximo", f"USD {m2_max * d['sup']:,.0f}")

    # Conversión a Pesos (BNA)
    st.write(f"**Valor Promedio en Pesos (BNA):** $ {m2_avg * d['sup'] * dolar_bna:,.0f}")

    # Mapas
    tab1, tab2 = st.tabs(["🗺️ Mapa", "📷 Street View"])
    with tab1:
        m = folium.Map(location=[d['lat'], d['lon']], zoom_start=17)
        folium.Marker([d['lat'], d['lon']], popup=d['address']).add_to(m)
        st_folium(m, width=None, height=450, key="mapa_final")
    with tab2:
        url_sv = f"https://maps.google.com/maps?q={d['lat']},{d['lon']}&layer=c&cbll={d['lat']},{d['lon']}&output=svembed"
        st.markdown(f'<iframe width="100%" height="450" src="{url_sv}" frameborder="0"></iframe>', unsafe_allow_html=True)
