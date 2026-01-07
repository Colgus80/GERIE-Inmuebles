import streamlit as st
import pandas as pd
import geopandas as gpd
import requests
import folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from shapely.geometry import Point
from streamlit_folium import st_folium

# Configuración inicial
st.set_page_config(page_title="GERIE Consulta Valor Inmueble", layout="wide", page_icon="🏠")

# Estilo personalizado
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES DE DATOS ---

@st.cache_data(ttl=3600)
def get_dolar_bna():
    try:
        response = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return response.json()['venta']
    except:
        return 950.0  # Valor de respaldo actualizado

@st.cache_data
def cargar_datos_renabap():
    # URL oficial de Barrios Populares de Argentina
    url = "https://datosabiertos.desarrollosocial.gob.ar/dataset/0d50730b-1662-4217-9ef1-37018c1b359f/resource/828292d3-96b4-4b9e-99e5-b1030e466b0a/download/barrios-populares.json"
    try:
        gdf = gpd.read_file(url)
        return gdf
    except:
        return None

def get_market_values(city):
    # Valores base por m2 (Dólares)
    data_mercado = {
        "CABA": {"min": 1800, "max": 3500, "avg": 2400},
        "GBA NORTE": {"min": 1500, "max": 4500, "avg": 2200},
        "ROSARIO": {"min": 900, "max": 1900, "avg": 1300},
        "CORDOBA": {"min": 850, "max": 1800, "avg": 1250},
        "default": {"min": 1000, "max": 2200, "avg": 1500}
    }
    return data_mercado.get(city.upper(), data_mercado["default"])

def calcular_ajuste_entorno(distancia_m):
    if distancia_m < 150: return 0.70, "Crítico (-30%)"
    if distancia_m < 350: return 0.85, "Alto (-15%)"
    if distancia_m < 550: return 0.93, "Moderado (-7%)"
    return 1.0, "Nulo (0%)"

# --- INTERFAZ PRINCIPAL ---

st.title("🏢 GERIE: Consulta Valor Inmueble")
st.markdown("### Sistema de Tasación Referencial con Análisis de Entorno")

with st.sidebar:
    st.header("📍 Parámetros de Consulta")
    direccion = st.text_input("Dirección y Altura", "Av. del Libertador 2000")
    ciudad = st.selectbox("Región / Ciudad", ["CABA", "GBA Norte", "Rosario", "Córdoba", "Otros"])
    superficie = st.number_input("Superficie Total (m2)", min_value=1, value=50)
    btn_consultar = st.button("CALCULAR VALUACIÓN", use_container_width=True)

dolar_bna = get_dolar_bna()

if btn_consultar:
    with st.spinner('Analizando datos de mercado y entorno...'):
        geolocator = Nominatim(user_agent="gerie_app_v1")
        full_address = f"{direccion}, {ciudad}, Argentina"
        location = geolocator.geocode(full_address)

        if location:
            lat, lon = location.latitude, location.longitude
            
            # 1. Análisis de Riesgo (RENABAP)
            gdf_barrios = cargar_datos_renabap()
            dist_min = 99999
            if gdf_barrios is not None:
                # Cálculo de distancia al asentamiento más cercano
                for _, barrio in gdf_barrios.iterrows():
                    d = geodesic((lat, lon), (barrio.geometry.centroid.y, barrio.geometry.centroid.x)).meters
                    if d < dist_min: dist_min = d
            
            factor_ajuste, impacto_txt = calcular_ajuste_entorno(dist_min)
            
            # 2. Cálculos Inmobiliarios
            base_vals = get_market_values(ciudad)
            m2_min = base_vals['min'] * factor_ajuste
            m2_avg = base_vals['avg'] * factor_ajuste
            m2_max = base_vals['max'] * factor_ajuste # Ajuste global por entorno
            
            # 3. Métricas Principales
            st.subheader("📊 Valores de Mercado por m² (USD)")
            c1, c2, c3 = st.columns(3)
            c1.metric("Mínimo", f"USD {m2_min:,.0f}")
            c2.metric("Promedio", f"USD {m2_avg:,.0f}", delta=f"-{impacto_txt}" if factor_ajuste < 1 else None, delta_color="inverse")
            c3.metric("Máximo", f"USD {m2_max:,.0f}")

            # 4. Valor Total de la Propiedad
            st.divider()
            st.subheader("💰 Valor Total Estimado")
            
            data_total = {
                "Moneda": ["Dólares (USD)", f"Pesos (ARS @ {dolar_bna})"],
                "Valor Mínimo": [f"US$ {m2_min*superficie:,.0f}", f"$ {m2_min*superficie*dolar_bna:,.0f}"],
                "Valor Promedio": [f"US$ {m2_avg*superficie:,.0f}", f"$ {m2_avg*superficie*dolar_bna:,.0f}"],
                "Valor Máximo": [f"US$ {m2_max*superficie:,.0f}", f"$ {m2_max*superficie*dolar_bna:,.0f}"]
            }
            st.table(pd.DataFrame(data_total))

            # 5. Mapas y Entorno
            st.divider()
            col_map, col_info = st.columns([2, 1])
            
            with col_map:
                st.subheader("📍 Ubicación")
                m = folium.Map(location=[lat, lon], zoom_start=16)
                folium.Marker([lat, lon], popup=direccion, icon=folium.Icon(color='blue')).add_to(m)
                st_folium(m, height=400, width=None)

            with col_info:
                st.subheader("🕵️ Análisis de Zona")
                if dist_min < 550:
                    st.error(f"**Alerta de Entorno:** Proximidad a barrio popular ({dist_min:.0f}m).")
                else:
                    st.success("**Zona Validada:** No se detectan asentamientos críticos en el radio inmediato.")
                
                st.info(f"**Tipo de Suelo:** Urbano Consolidad ({ciudad})")
                
            # 6. Street View
            st.subheader("📷 Visualización de Entorno (Street View)")
            st.markdown(f'<iframe width="100%" height="450" src="https://www.google.com/maps/embed/v1/streetview?key=YOUR_API_KEY_HERE&location={lat},{lon}&heading=210&pitch=10&fov=35" frameborder="0"></iframe>', unsafe_allow_html=True)
            st.caption("Nota: Si la imagen no carga, es posible que Street View no esté disponible para esta altura exacta.")

        else:
            st.error("❌ No se encontró la dirección. Intenta agregar la altura o corregir la ciudad.")

else:
    st.info("👋 Bienvenida/o a GERIE. Ingresa una dirección en el panel izquierdo para comenzar el análisis.")

st.caption(f"Cotización Dólar BNA: $ {dolar_bna} | Fuente Datos: RENABAP & DolarAPI | © 2024 GERIE Inmuebles")
