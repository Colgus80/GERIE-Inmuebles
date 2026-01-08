import streamlit as st
import pandas as pd
import geopandas as gpd
import requests
import folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from shapely.geometry import Point
from streamlit_folium import st_folium

# Configuración GERIE - Visión Nacional
st.set_page_config(page_title="GERIE - Tasador Federal", layout="wide")

# --- MOTORES DE DATOS ---

@st.cache_data(ttl=3600)
def get_dolar_bna():
    try:
        r = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return r.json()['venta']
    except: return 1050.0

@st.cache_data
def cargar_renabap_nacional():
    """Carga la base completa de barrios populares de Argentina"""
    url = "https://datosabiertos.desarrollosocial.gob.ar/dataset/0d50730b-1662-4217-9ef1-37018c1b359f/resource/828292d3-96b4-4b9e-99e5-b1030e466b0a/download/barrios-populares.json"
    try:
        return gpd.read_file(url)
    except: return None

def tasacion_federal(provincia, localidad):
    """Diccionario de valores base m2 por zona (Referencial)"""
    valores = {
        "CABA": 2350,
        "BUENOS AIRES": 1600,
        "SANTA FE": 1400,
        "CORDOBA": 1350,
        "MENDOZA": 1250,
        "NEUQUEN": 1800, # Zona petrolera
        "CHUBUT": 1450,
        "DEFAULT": 1200
    }
    return valores.get(provincia.upper(), valores["DEFAULT"])

# --- INTERFAZ ---
st.title("🏢 GERIE: Sistema Nacional de Valuación")
st.markdown("---")

with st.sidebar:
    st.header("📍 Ubicación del Inmueble")
    with st.form("form_nacional"):
        direccion = st.text_input("Calle y Altura", placeholder="Ej: Av. Colon 100")
        localidad = st.text_input("Localidad", placeholder="Ej: Córdoba Capital")
        provincia = st.selectbox("Provincia", [
            "CABA", "Buenos Aires", "Catamarca", "Chaco", "Chubut", "Cordoba", 
            "Corrientes", "Entre Rios", "Formosa", "Jujuy", "La Pampa", "La Rioja", 
            "Mendoza", "Misiones", "Neuquen", "Rio Negro", "Salta", "San Juan", 
            "San Luis", "Santa Cruz", "Santa Fe", "Santiago del Estero", "Tierra del Fuego", "Tucuman"
        ])
        tipo = st.selectbox("Tipo", ["Departamento", "Casa", "Local", "Oficina"])
        m2 = st.number_input("Superficie m2", min_value=1, value=50)
        btn = st.form_submit_button("TASAR PROPIEDAD")

# --- LÓGICA DE PROCESAMIENTO ---
if btn:
    with st.spinner('Procesando datos geográficos y de mercado...'):
        # 1. Búsqueda con Motor Robusto
        geo = Nominatim(user_agent="gerie_federal_v11", timeout=15)
        # Formateamos la consulta para que el mapa no se pierda
        query = f"{direccion}, {localidad}, {provincia}, Argentina"
        loc = geo.geocode(query, addressdetails=True)

        if loc:
            # 2. Análisis RENABAP Nacional
            gdf_r = cargar_renabap_nacional()
            dist_min = 99999
            nombre_b = ""
            if gdf_r is not None:
                p = Point(loc.longitude, loc.latitude)
                # Filtro espacial rápido para no procesar todo el país
                caja = gdf_r.cx[loc.longitude-0.02:loc.longitude+0.02, loc.latitude-0.02:loc.latitude+0.02]
                if not caja.empty:
                    # Calculamos distancia real (aproximación en metros)
                    for _, fila in caja.iterrows():
                        d = geodesic((loc.latitude, loc.longitude), (fila.geometry.centroid.y, fila.geometry.centroid.x)).meters
                        if d < dist_min:
                            dist_min = d
                            nombre_b = fila['nombre']

            st.session_state.data = {
                "lat": loc.latitude, "lon": loc.longitude, "address": loc.address,
                "dist": dist_min, "barrio": nombre_b, "m2": m2, "tipo": tipo,
                "prov": provincia, "loc": localidad
            }
        else:
            st.error("No se pudo localizar la dirección. Intente abreviar menos (ej: usar 'Avenida' en vez de 'Av').")

# --- RESULTADOS ---
if 'data' in st.session_state and st.session_state.data:
    d = st.session_state.data
    dolar = get_dolar_bna()

    # Tasación Dinámica
    v_base = tasacion_federal(d['prov'], d['loc'])
    ajuste_riesgo = 0.70 if d['dist'] < 500 else 1.0
    coef_tipo = {"Departamento": 1.0, "Casa": 0.9, "Local": 1.4, "Oficina": 1.15}
    
    m2_avg = v_base * ajuste_riesgo * coef_tipo[d['tipo']]
    m2_min, m2_max = m2_avg * 0.85, m2_avg * 1.15

    # Alertas y Reporte
    if d['dist'] < 500:
        st.error(f"🚨 RIESGO DETECTADO: Cercanía a barrio '{d['barrio']}' ({d['dist']:.0f}m)")
    else:
        st.success("✅ Entorno analizado: Sin asentamientos críticos en el radio de 500m.")

    st.subheader(f"📍 {d['address']}")
    
    # Métricas de Valor
    c1, c2, c3 = st.columns(3)
    c1.metric("M2 Mínimo", f"USD {m2_min:,.0f}")
    c2.metric("M2 PROMEDIO", f"USD {m2_avg:,.0f}")
    c3.metric("M2 Máximo", f"USD {m2_max:,.0f}")

    t1, t2, t3 = st.columns(3)
    t1.metric("Total Mín", f"USD {m2_min * d['m2']:,.0f}")
    t2.metric("TOTAL PROMEDIO", f"USD {m2_avg * d['m2']:,.0f}")
    t3.metric("Total Máx", f"USD {m2_max * d['m2']:,.0f}")

    st.info(f"💵 Referencia Pesos (BNA): $ {m2_avg * d['m2'] * dolar:,.0f}")

    # Visualización
    col_map, col_sv = st.columns(2)
    with col_map:
        m = folium.Map(location=[d['lat'], d['lon']], zoom_start=16)
        folium.Marker([d['lat'], d['lon']]).add_to(m)
        st_folium(m, height=400, width=None, key="mapa_nacional")
    with col_sv:
        st.markdown(f'<iframe width="100%" height="400" src="https://maps.google.com/maps?q={d["lat"]},{d["lon"]}&layer=c&cbll={d["lat"]},{d["lon"]}&output=svembed"></iframe>', unsafe_allow_html=True)
