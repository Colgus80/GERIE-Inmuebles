import streamlit as st
import pandas as pd
import folium
import requests
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import st_folium

# Configuración GERIE
st.set_page_config(page_title="GERIE Tasador Pro", layout="wide")

# --- FUNCIONES DE SEGURIDAD Y DATOS ---

def chequeo_renabap_extensible(lat, lon):
    """
    Capa de seguridad estática reforzada para zonas de Beccar/Victoria/San Fernando.
    """
    zonas_riesgo = [
        {"nombre": "La Cava (ID 397)", "lat": -34.4720, "lon": -58.5422},
        {"nombre": "San Jorge / Uruguay", "lat": -34.4635, "lon": -58.5520}, # Cerca de Uruguay 1500
        {"nombre": "Barrio Itatí", "lat": -34.4600, "lon": -58.5450}
    ]
    
    dist_min = 99999
    nombre_detectado = ""
    
    for zona in zonas_riesgo:
        d = geodesic((lat, lon), (zona['lat'], zona['lon'])).meters
        if d < dist_min:
            dist_min = d
            nombre_detectado = zona['nombre']
            
    return dist_min, nombre_detectado

@st.cache_data(ttl=3600)
def get_dolar_bna():
    try:
        r = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return r.json()['venta']
    except: return 1050.0

# --- INTERFAZ ---
st.title("🏢 GERIE: Valuación Inmobiliaria")

with st.sidebar:
    st.header("📍 Ubicación")
    with st.form("tasador_v9"):
        # Sugerimos formato para mejorar el éxito del geocodificador
        dir_input = st.text_input("Calle y Altura", "Uruguay 1565")
        loc_input = st.text_input("Localidad", "Beccar")
        prov_input = st.text_input("Provincia", "Buenos Aires")
        tipo = st.selectbox("Tipo de Propiedad", ["Casa", "Departamento", "Local"])
        m2 = st.number_input("Superficie m2", value=50, min_value=1)
        btn = st.form_submit_button("TASAR PROPIEDAD")

if btn:
    with st.spinner('Localizando con precisión...'):
        # MEJORA: User-agent más específico y búsqueda por componentes
        geo = Nominatim(user_agent="gerie_search_engine_2026_v9", timeout=15)
        
        # Intentamos una búsqueda combinada
        query_completa = f"{dir_input}, {loc_input}, {prov_input}, Argentina"
        loc = geo.geocode(query_completa, addressdetails=True)
        
        # Si falla, intentamos sin localidad (solo calle + provincia) para evitar errores de límites municipales
        if not loc:
            loc = geo.geocode(f"{dir_input}, {prov_input}, Argentina")

        if loc:
            dist_r, barrio_r = chequeo_renabap_extensible(loc.latitude, loc.longitude)
            st.session_state.data = {
                "lat": loc.latitude, "lon": loc.longitude, 
                "address": loc.address, "dist": dist_r, "barrio": barrio_r,
                "m2": m2, "tipo": tipo
            }
        else:
            st.error("❌ No se pudo ubicar la dirección. Verifique si la altura es correcta.")

# --- RESULTADOS ---
if 'data' in st.session_state and st.session_state.data:
    d = st.session_state.data
    dolar = get_dolar_bna()

    # Lógica de Tasación con Valores Mín/Máx/Promedio
    base_m2 = 1750 if "URUGUAY" in d['address'].upper() else 1600
    
    # Factor de Riesgo (Detección de Uruguay 1500)
    ajuste_riesgo = 1.0
    if d['dist'] < 600:
        st.error(f"🚨 ALERTA DE MERCADO: Proximidad a {d['barrio']} ({d['dist']:.0f}m)")
        ajuste_riesgo = 0.70 # Impacto del 30% en valor
    else:
        st.success("✅ Zona analizada sin riesgos de asentamientos cercanos.")

    m2_avg = base_m2 * ajuste_riesgo
    if d['tipo'] == "Local": m2_avg *= 1.35
    
    m2_min, m2_max = m2_avg * 0.85, m2_avg * 1.15

    # Visualización de Valores
    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Valor m² Mínimo", f"USD {m2_min:,.0f}")
    c2.metric("Valor m² PROMEDIO", f"USD {m2_avg:,.0f}")
    c3.metric("Valor m² Máximo", f"USD {m2_max:,.0f}")

    t1, t2, t3 = st.columns(3)
    t1.metric("Valor Total Mínimo", f"USD {m2_min * d['m2']:,.0f}")
    t2.metric("TOTAL PROMEDIO", f"USD {m2_avg * d['m2']:,.0f}")
    t3.metric("Valor Total Máximo", f"USD {m2_max * d['m2']:,.0f}")

    st.info(f"💰 Equivalente en Pesos (BNA): $ {m2_avg * d['m2'] * dolar:,.0f}")

    # Mapas y Vistas
    t_map, t_sv = st.tabs(["🗺️ Mapa de Ubicación", "📷 Street View"])
    with t_map:
        m = folium.Map(location=[d['lat'], d['lon']], zoom_start=17)
        folium.Marker([d['lat'], d['lon']], popup=d['address']).add_to(m)
        # Círculo de seguridad visual
        folium.Circle([d['lat'], d['lon']], radius=500, color="red", fill=True, opacity=0.15).add_to(m)
        st_folium(m, width=None, height=450)
    with t_sv:
        st.markdown(f'<iframe width="100%" height="450" src="https://maps.google.com/maps?q={d["lat"]},{d["lon"]}&layer=c&cbll={d["lat"]},{d["lon"]}&output=svembed"></iframe>', unsafe_allow_html=True)
