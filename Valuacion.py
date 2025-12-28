import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium
import folium
import requests

# Configuración de página
st.set_page_config(page_title="GERIE Consulta Valor Inmueble", layout="wide")

st.title("🏠 GERIE: Consulta de Valor Inmueble")

# --- 1. ESTADO DE LA SESIÓN ---
if 'datos' not in st.session_state:
    st.session_state.datos = None

# --- 2. OBTENCIÓN DE DÓLAR BNA ---
@st.cache_data(ttl=3600)
def get_dolar_bna():
    try:
        # Buscamos el oficial venta del BNA
        r = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return r.json()['venta']
    except:
        return 950.0 # Valor de referencia si falla la API

dolar_act = get_dolar_bna()

# --- 3. LÓGICA DE PRECIOS POR ZONA ---
def estimar_precios(ciudad):
    zonas = {
        "CABA": {"min": 1950, "max": 3800, "avg": 2550},
        "GBA NORTE": {"min": 1500, "max": 4500, "avg": 2200},
        "ROSARIO": {"min": 950, "max": 1900, "avg": 1350},
    }
    return zonas.get(ciudad.upper(), {"min": 1100, "max": 2200, "avg": 1600})

# --- 4. BARRA LATERAL ---
with st.sidebar:
    st.header("Carga de Datos")
    calle = st.text_input("Dirección (Calle y Altura)", "Los Pirineos 1332")
    localidad = st.text_input("Ciudad / Localidad", "CABA")
    m2 = st.number_input("Superficie Total (m2)", min_value=1, value=150)
    
    if st.button("Consultar Valuación"):
        geolocator = Nominatim(user_agent="gerie_app_v2")
        query = f"{calle}, {localidad}, Argentina"
        location = geolocator.geocode(query)
        
        if location:
            st.session_state.datos = {
                "lat": location.latitude,
                "lon": location.longitude,
                "addr": calle,
                "precios": estimar_precios(localidad),
                "m2": m2
            }
        else:
            st.error("No se encontró la ubicación exacta.")

# --- 5. RESULTADOS ---
if st.session_state.datos:
    d = st.session_state.datos
    p = d['precios']
    
    # Métricas principales
    c1, c2, c3 = st.columns(3)
    c1.metric("Mínimo m2", f"US$ {p['min']}")
    c2.metric("Promedio m2", f"US$ {p['avg']}")
    c3.metric("Máximo m2", f"US$ {p['max']}")
    
    # Tabla de valores totales
    st.subheader("Valuación Total Estimada")
    v_avg = p['avg'] * d['m2']
    v_min = p['min'] * d['m2']
    v_max = p['max'] * d['m2']
    
    tabla = pd.DataFrame({
        "Escenario": ["Mínimo", "Promedio", "Máximo"],
        "Valor USD": [f"US$ {v_min:,.0f}", f"US$ {v_avg:,.0f}", f"US$ {v_max:,.0f}"],
        "Valor ARS (BNA)": [f"$ {v_min*dolar_act:,.0f}", f"$ {v_avg*dolar_act:,.0f}", f"$ {v_max*dolar_act:,.0f}"]
    })
    st.table(tabla)
    
    # --- VISUALIZACIÓN ---
    col_mapa, col_street = st.columns(2)
    
    with col_mapa:
        st.write("📍 **Ubicación en Mapa**")
        m = folium.Map(location=[d['lat'], d['lon']], zoom_start=17)
        folium.Marker([d['lat'], d['lon']]).add_to(m)
        st_folium(m, width="100%", height=400, key="mapa_final")
        
    with col_street:
        st.write("📷 **Vista de Calle (Street View)**")
        # Usamos el parámetro 'layer=c' y 'cbll' para forzar Street View
        sv_url = f"https://www.google.com/maps?q=&layer=c&cbll={d['lat']},{d['lon']}&cbp=11,0,0,0,0&output=svembed"
        st.markdown(f'<iframe width="100%" height="400" frameborder="0" src="{sv_url}" allowfullscreen></iframe>', unsafe_allow_html=True)

    st.caption(f"Tipo de cambio BNA aplicado: $ {dolar_act}")
