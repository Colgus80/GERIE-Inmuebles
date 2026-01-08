import streamlit as st
import pandas as pd
import geopandas as gpd
import requests
import folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from shapely.geometry import Point
from streamlit_folium import st_folium

# Configuración GERIE - Herramienta de Riesgo Crediticio
st.set_page_config(page_title="GERIE - Verificación de Garantías", layout="wide")

# --- MOTORES DE RIESGO Y DATOS ---

@st.cache_data(ttl=3600)
def get_dolar_bna():
    try:
        # Referencia obligatoria para valuaciones bancarias en Argentina
        r = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return r.json()['venta']
    except: return 1050.0

@st.cache_data
def cargar_renabap_nacional():
    url = "https://datosabiertos.desarrollosocial.gob.ar/dataset/0d50730b-1662-4217-9ef1-37018c1b359f/resource/828292d3-96b4-4b9e-99e5-b1030e466b0a/download/barrios-populares.json"
    try: return gpd.read_file(url)
    except: return None

def obtener_valor_referencial_m2(provincia):
    # Valores promedio de mercado por provincia (ajustables según manual de tasación del banco)
    valores = {
        "CABA": 2200, "BUENOS AIRES": 1500, "SANTA FE": 1300, "CORDOBA": 1250,
        "MENDOZA": 1200, "NEUQUEN": 1700, "TUCUMAN": 1100, "SALTA": 1050, "DEFAULT": 1000
    }
    return valores.get(provincia.upper(), valores["DEFAULT"])

# --- INTERFAZ DE CARGA ---
st.title("🏦 GERIE: Verificación de Garantías Inmobiliarias")
st.caption("Herramienta de soporte para calificación crediticia y cumplimiento de política de garantías.")
st.markdown("---")

with st.sidebar:
    st.header("🔍 Datos del Fiador/Garante")
    with st.form("form_riesgo"):
        direccion = st.text_input("Calle y Altura", placeholder="Ej: Uruguay 1565")
        localidad = st.text_input("Localidad", placeholder="Ej: Beccar")
        provincia = st.selectbox("Provincia", [
            "CABA", "Buenos Aires", "Catamarca", "Chaco", "Chubut", "Cordoba", 
            "Corrientes", "Entre Rios", "Formosa", "Jujuy", "La Pampa", "La Rioja", 
            "Mendoza", "Misiones", "Neuquen", "Rio Negro", "Salta", "San Juan", 
            "San Luis", "Santa Cruz", "Santa Fe", "Santiago del Estero", "Tierra del Fuego", "Tucuman"
        ])
        tipo = st.selectbox("Tipo de Inmueble", ["Casa", "Departamento", "Local", "Terreno"])
        m2 = st.number_input("Superficie Declarada (m2)", min_value=1, value=50)
        btn = st.form_submit_button("VERIFICAR COLATERAL")

if btn:
    with st.spinner('Analizando geolocalización y entorno de riesgo...'):
        geo = Nominatim(user_agent="gerie_banking_risk_v12", timeout=15)
        # Búsqueda estructurada para evitar errores en calles límite
        query = f"{direccion}, {localidad}, {provincia}, Argentina"
        loc = geo.geocode(query, addressdetails=True)

        if loc:
            # Análisis RENABAP (Afectación de Valor)
            gdf_r = cargar_renabap_nacional()
            dist_min = 99999
            nombre_b = ""
            if gdf_r is not None:
                p = Point(loc.longitude, loc.latitude)
                caja = gdf_r.cx[loc.longitude-0.01:loc.longitude+0.01, loc.latitude-0.01:loc.latitude+0.01]
                for _, fila in caja.iterrows():
                    d = geodesic((loc.latitude, loc.longitude), (fila.geometry.centroid.y, fila.geometry.centroid.x)).meters
                    if d < dist_min:
                        dist_min = d
                        nombre_b = fila['nombre']

            st.session_state.data = {
                "lat": loc.latitude, "lon": loc.longitude, "address": loc.address,
                "dist": dist_min, "barrio": nombre_b, "m2": m2, "tipo": tipo, "prov": provincia
            }
        else:
            st.error("⚠️ Error de localización: No se pudo verificar la dirección declarada.")

# --- INFORME DE RIESGO ---
if 'data' in st.session_state and st.session_state.data:
    d = st.session_state.data
    dolar_bna = get_dolar_bna()

    # Cálculo de Tasación Técnica
    v_base = obtener_valor_referencial_m2(d['prov'])
    
    # Penalización por riesgo de entorno (RENABAP)
    # Si está a menos de 500m, el banco suele aplicar un castigo fuerte a la valuación
    factor_riesgo = 0.65 if d['dist'] < 500 else 1.0 
    
    # Coeficiente por tipo de bien (Liquidez)
    coef_liq = {"Casa": 0.9, "Departamento": 1.0, "Local": 1.2, "Terreno": 0.7}
    
    m2_avg = v_base * factor_riesgo * coef_liq[d['tipo']]
    m2_min, m2_max = m2_avg * 0.85, m2_avg * 1.15

    # Alertas de Cumplimiento (Compliance)
    if d['dist'] < 500:
        st.error(f"🚨 ALERTA DE RIESGO: Garantía afectada por cercanía a '{d['barrio']}' ({d['dist']:.0f}m).")
    else:
        st.success("✅ Verificación RENABAP: Sin afectación detectada en radio de 500m.")

    # Panel de Resultados de Valuación
    st.subheader("📋 Resumen de Valuación Técnica")
    st.info(f"📍 Dirección Verificada: {d['address']}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("M2 Promedio (USD)", f"USD {m2_avg:,.0f}")
    col2.metric("Valor Total (USD)", f"USD {m2_avg * d['m2']:,.0f}")
    col3.metric("Valor Total (ARS BNA)", f"$ {m2_avg * d['m2'] * dolar_bna:,.0f}")

    # Rango de Seguridad para el Banco
    st.markdown("### 🛡️ Escenarios de Garantía")
    s1, s2, s3 = st.columns(3)
    s1.write(f"**Escenario Conservador (-15%):** USD {(m2_min * d['m2']):,.0f}")
    s2.write(f"**Escenario Base:** USD {(m2_avg * d['m2']):,.0f}")
    s3.write(f"**Escenario Optimista (+15%):** USD {(m2_max * d['m2']):,.0f}")

    # Análisis Visual
    t_map, t_sv = st.tabs(["🗺️ Mapa de Garantía", "📷 Registro Fotográfico (Street View)"])
    with t_map:
        m = folium.Map(location=[d['lat'], d['lon']], zoom_start=16)
        folium.Marker([d['lat'], d['lon']], popup="Garantía Analizada").add_to(m)
        # Radio de exclusión/alerta
        folium.Circle([d['lat'], d['lon']], radius=500, color="red", fill=True, opacity=0.1).add_to(m)
        st_folium(m, height=400, width=None)
    with t_sv:
        st.markdown(f'<iframe width="100%" height="450" src="https://maps.google.com/maps?q={d["lat"]},{d["lon"]}&layer=c&cbll={d["lat"]},{d["lon"]}&output=svembed"></iframe>', unsafe_allow_html=True)
