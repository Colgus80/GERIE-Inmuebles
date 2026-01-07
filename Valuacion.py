import streamlit as st
import pandas as pd
import geopandas as gpd
import requests
import folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from shapely.geometry import Point
from streamlit_folium import st_folium

# Configuración de página
st.set_page_config(page_title="GERIE Consulta Valor Inmueble", layout="wide", page_icon="🏢")

# --- INICIALIZACIÓN DE MEMORIA (Session State) ---
if 'resultado' not in st.session_state:
    st.session_state.resultado = None

# --- FUNCIONES DE DATOS ---

@st.cache_data(ttl=3600)
def get_dolar_bna():
    try:
        response = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return response.json()['venta']
    except:
        return 1020.0 # Ajustado a valores actuales aproximados

@st.cache_data
def cargar_datos_renabap():
    url = "https://datosabiertos.desarrollosocial.gob.ar/dataset/0d50730b-1662-4217-9ef1-37018c1b359f/resource/828292d3-96b4-4b9e-99e5-b1030e466b0a/download/barrios-populares.json"
    try:
        return gpd.read_file(url)
    except:
        return None

def get_market_values(texto_busqueda):
    data_mercado = {
        "CABA": {"min": 1800, "max": 3500, "avg": 2400},
        "BUENOS AIRES": {"min": 1300, "max": 2800, "avg": 1800},
        "SANTA FE": {"min": 950, "max": 1900, "avg": 1350},
        "CORDOBA": {"min": 900, "max": 1850, "avg": 1250},
        "default": {"min": 1000, "max": 2000, "avg": 1400}
    }
    for key in data_mercado:
        if key in texto_busqueda.upper():
            return data_mercado[key]
    return data_mercado["default"]

def calcular_ajuste_entorno(distancia_m):
    if distancia_m < 200: return 0.70, "Crítico (-30%)"
    if distancia_m < 400: return 0.85, "Alto (-15%)"
    if distancia_m < 600: return 0.93, "Moderado (-7%)"
    return 1.0, "Nulo (0%)"

# --- INTERFAZ ---
st.title("🏢 GERIE: Consulta Valor Inmueble")

with st.sidebar:
    st.header("📍 Nueva Consulta")
    with st.form("input_form"):
        direccion = st.text_input("Calle y Altura", placeholder="Ej: Av. Rivadavia 5000")
        localidad = st.text_input("Localidad y Provincia", placeholder="Ej: Caballito, CABA")
        superficie = st.number_input("Superficie m2", min_value=1, value=50)
        submit = st.form_submit_button("CALCULAR")

    if submit:
        with st.spinner('Procesando...'):
            geolocator = Nominatim(user_agent="gerie_v3")
            query = f"{direccion}, {localidad}, Argentina"
            location = geolocator.geocode(query)

            if location:
                # Análisis de Riesgo
                gdf_barrios = cargar_datos_renabap()
                dist_min = 99999
                if gdf_barrios is not None:
                    lat, lon = location.latitude, location.longitude
                    for _, barrio in gdf_barrios.iterrows():
                        d = geodesic((lat, lon), (barrio.geometry.centroid.y, barrio.geometry.centroid.x)).meters
                        if d < dist_min: dist_min = d
                
                factor, impacto = calcular_ajuste_entorno(dist_min)
                base_vals = get_market_values(localidad)
                dolar = get_dolar_bna()

                # Guardamos TODO en el estado de la sesión
                st.session_state.resultado = {
                    "lat": location.latitude,
                    "lon": location.longitude,
                    "address": location.address,
                    "m2_min": base_vals['min'] * factor,
                    "m2_avg": base_vals['avg'] * factor,
                    "m2_max": base_vals['max'] * factor,
                    "superficie": superficie,
                    "dolar": dolar,
                    "dist_min": dist_min,
                    "factor": factor,
                    "impacto": impacto
                }
            else:
                st.error("No se encontró la dirección. Intenta ser más específico.")

# --- RENDERIZADO DE RESULTADOS (Se mantienen fijos) ---
if st.session_state.resultado:
    res = st.session_state.resultado
    
    st.success(f"📍 **Dirección detectada:** {res['address']}")
    
    # Métricas
    c1, c2, c3 = st.columns(3)
    c1.metric("M2 Mínimo", f"USD {res['m2_min']:,.0f}")
    c2.metric("M2 Promedio", f"USD {res['m2_avg']:,.0f}", delta=f"-{res['impacto']}" if res['factor'] < 1 else None, delta_color="inverse")
    c3.metric("M2 Máximo", f"USD {res['m2_max']:,.0f}")

    # Tabla
    st.divider()
    val_usd = res['m2_avg'] * res['superficie']
    df_res = pd.DataFrame({
        "Escenario": ["Mínimo", "Promedio (Sugerido)", "Máximo"],
        "USD Total": [f"US$ {res['m2_min']*res['superficie']:,.0f}", f"US$ {val_usd:,.0f}", f"US$ {res['m2_max']*res['superficie']:,.0f}"],
        "ARS Total (BNA)": [f"$ {res['m2_min']*res['superficie']*res['dolar']:,.0f}", f"$ {val_usd*res['dolar']:,.0f}", f"$ {res['m2_max']*res['superficie']*res['dolar']:,.0f}"]
    })
    st.table(df_res)

    # Visualización
    col_mapa, col_sv = st.columns(2)
    with col_mapa:
        st.subheader("🗺️ Mapa")
        m = folium.Map(location=[res['lat'], res['lon']], zoom_start=16)
        folium.Marker([res['lat'], res['lon']]).add_to(m)
        st_folium(m, height=400, width=500, key="mapa_fijo")

    with col_sv:
        st.subheader("📸 Street View")
        st.markdown(f'<iframe width="100%" height="400" src="https://maps.google.com/maps?q={res["lat"]},{res["lon"]}&layer=c&cbll={res["lat"]},{res["lon"]}&output=svembed"></iframe>', unsafe_allow_html=True)

    if res['factor'] < 1:
        st.warning(f"⚠️ El valor refleja un ajuste del {res['impacto']} por proximidad a un barrio popular (Distancia: {res['dist_min']:.0f}m).")

else:
    st.info("👈 Ingresa los datos en el panel de la izquierda y presiona 'CALCULAR'.")
