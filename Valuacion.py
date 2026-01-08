import streamlit as st
import pandas as pd
import geopandas as gpd
import requests
import folium
from geopy.geocoders import Nominatim
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
    except: return 1050.0

@st.cache_data
def cargar_y_procesar_renabap(lat, lon):
    url = "https://datosabiertos.desarrollosocial.gob.ar/dataset/0d50730b-1662-4217-9ef1-37018c1b359f/resource/828292d3-96b4-4b9e-99e5-b1030e466b0a/download/barrios-populares.json"
    try: 
        gdf = gpd.read_file(url)
        # Creamos un punto de consulta
        punto_consulta = Point(lon, lat)
        
        # Filtramos primero por una caja pequeña para ganar velocidad (Bounding Box)
        # Esto asegura que nos enfoquemos en los barrios cercanos a la consulta
        distancia_grados = 0.01 # Aprox 1km
        caja = gdf.cx[lon-distancia_grados:lon+distancia_grados, lat-distancia_grados:lat+distancia_grados]
        
        # Si la caja tiene datos, buscamos la distancia real al borde del polígono
        if not caja.empty:
            # Convertimos a metros (proyección local Argentina) para precisión
            caja_m = caja.to_crs(epsg=3395)
            punto_m = gpd.GeoSeries([punto_consulta], crs="EPSG:4326").to_crs(epsg=3395)[0]
            dist_minima = caja_m.distance(punto_m).min()
            return dist_minima
        return 99999
    except Exception as e:
        return 99999

def analizar_densidad_comercial(lat, lon):
    url = "http://overpass-api.de/api/interpreter"
    query = f"""[out:json];(node(around:450,{lat},{lon})["amenity"];node(around:450,{lat},{lon})["shop"];);out count;"""
    try:
        resp = requests.get(url, params={'data': query}, timeout=5)
        count = int(resp.json()['elements'][0]['tags']['total'])
        if count > 20: return "🏙️ ZONA CÉNTRICA / COMERCIAL", 1.15
        if count > 5: return "🏠 ZONA URBANA RESIDENCIAL", 1.0
        return "🌳 ZONA RURAL / SUBURBANA", 0.80
    except: return "🏙️ ZONA URBANA", 1.0

# --- INTERFAZ ---
st.title("🏢 GERIE: Consulta Valor Inmueble")

if 'data' not in st.session_state:
    st.session_state.data = None

with st.sidebar:
    st.header("📋 Datos de Tasación")
    with st.form("form_gerie"):
        direccion = st.text_input("Dirección", "Gervasio Posadas 1500")
        localidad = st.text_input("Ciudad / Provincia", "Beccar, Buenos Aires")
        tipo_inmueble = st.selectbox("Tipo de Inmueble", ["Departamento", "Casa", "Local Comercial", "Oficina"])
        superficie = st.number_input("Superficie Total (m2)", min_value=1, value=50)
        btn = st.form_submit_button("INICIAR TASACIÓN")

dolar_bna = get_dolar_bna()

if btn:
    with st.spinner('Analizando capas cartográficas y RENABAP...'):
        geolocator = Nominatim(user_agent="gerie_v7_final")
        loc = geolocator.geocode(f"{direccion}, {localidad}, Argentina")
        
        if loc:
            # 1. ANALISIS DE RIESGO PRECISO
            dist_real = cargar_y_procesar_renabap(loc.latitude, loc.longitude)
            tipo_z, mult_z = analizar_densidad_comercial(loc.latitude, loc.longitude)
            
            st.session_state.data = {
                "lat": loc.latitude, "lon": loc.longitude, "address": loc.address,
                "dist_r": dist_real, "tipo_z": tipo_z, "mult_z": mult_z,
                "sup": superficie, "tipo_inm": tipo_inmueble
            }

# --- RESULTADOS ---
if st.session_state.data:
    d = st.session_state.data
    
    st.info(f"💵 **Referencia Dólar BNA:** $ {dolar_bna}")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**{d['tipo_z']}**")
    with c2:
        # LÓGICA DE DETECCIÓN CRÍTICA (Caso La Cava)
        if d['dist_r'] < 500:
            st.error(f"⚠️ RIESGO DETECTADO: Asentamiento a {d['dist_r']:.0f} metros.")
            ajuste_riesgo = 0.70 # -30%
        else:
            st.success("✅ Zona libre de asentamientos (Radio 500m)")
            ajuste_riesgo = 1.0
    with c3:
        st.write(f"Inmueble: **{d['tipo_inm']}**")

    # VALORES M2
    base_m2 = 2300 if "CABA" in d['address'].upper() else 1500
    coef_tipo = {"Departamento": 1.0, "Casa": 0.95, "Local Comercial": 1.40, "Oficina": 1.10}
    
    m2_avg = base_m2 * d['mult_z'] * coef_tipo[d['tipo_inm']] * ajuste_riesgo
    m2_min, m2_max = m2_avg * 0.80, m2_avg * 1.20

    st.divider()
    
    # Métricas de Valor m2
    st.subheader("📊 Valor del m² (USD)")
    v1, v2, v3 = st.columns(3)
    v1.metric("Mínimo", f"USD {m2_min:,.0f}")
    v2.metric("Promedio", f"USD {m2_avg:,.0f}")
    v3.metric("Máximo", f"USD {m2_max:,.0f}")

    # Valores Totales
    st.subheader("💰 Valor Total Estimado")
    t1, t2, t3 = st.columns(3)
    t1.metric("Total Mínimo", f"USD {m2_min * d['sup']:,.0f}")
    t2.metric("Total PROMEDIO", f"USD {m2_avg * d['sup']:,.0f}")
    t3.metric("Total Máximo", f"USD {m2_max * d['sup']:,.0f}")

    st.write(f"**Valor en Pesos (BNA):** $ {m2_avg * d['sup'] * dolar_bna:,.0f}")

    # Mapas
    tab1, tab2 = st.tabs(["🗺️ Mapa", "📷 Street View"])
    with tab1:
        m = folium.Map(location=[d['lat'], d['lon']], zoom_start=17)
        folium.Marker([d['lat'], d['lon']]).add_to(m)
        st_folium(m, width=None, height=450, key="map_final")
    with tab2:
        url_sv = f"https://maps.google.com/maps?q={d['lat']},{d['lon']}&layer=c&cbll={d['lat']},{d['lon']}&output=svembed"
        st.markdown(f'<iframe width="100%" height="450" src="{url_sv}" frameborder="0"></iframe>', unsafe_allow_html=True)
