import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium
import folium
import requests

# Configuración de página
st.set_page_config(page_title="GERIE Consulta Valor Inmueble", layout="wide")
st.title("🏠 GERIE: Consulta de Valor Inmueble")

if 'datos' not in st.session_state:
    st.session_state.datos = None

# --- 1. BASE DE DATOS FEDERAL (Valores m2 2025) ---
DATA_ZONAS = {
    "CABA": {"min": 1850, "max": 3100, "avg": 2150},
    "GBA NORTE": {"min": 1600, "max": 4200, "avg": 2300},
    "GBA SUR": {"min": 1100, "max": 2000, "avg": 1450},
    "GBA OESTE": {"min": 1000, "max": 1800, "avg": 1350},
    "ROSARIO": {"min": 950, "max": 1900, "avg": 1300},
    "CORDOBA": {"min": 900, "max": 1800, "avg": 1250},
    "MENDOZA": {"min": 850, "max": 1700, "avg": 1200},
    "MAR DEL PLATA": {"min": 1100, "max": 2200, "avg": 1550},
    "BARILOCHE": {"min": 1800, "max": 3500, "avg": 2400},
    "SALTA": {"min": 800, "max": 1500, "avg": 1100},
    "DEFAULT": {"min": 1000, "max": 2000, "avg": 1400}
}

# --- 2. OBTENCIÓN DE TIPO DE CAMBIO BNA ---
@st.cache_data(ttl=3600)
def get_dolar_bna():
    try:
        r = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return r.json()['venta']
    except:
        return 1025.0

dolar_act = get_dolar_bna()

# --- 3. BARRA LATERAL ---
with st.sidebar:
    st.header("Carga de Datos Federal")
    calle = st.text_input("Calle y Altura", "Av. Colón 100")
    ciudad = st.text_input("Ciudad / Localidad", "Mar del Plata")
    provincia = st.text_input("Provincia", "Buenos Aires")
    m2 = st.number_input("Superficie Total (m2)", min_value=1, value=100)
    
    if st.button("Consultar Valuación"):
        geolocator = Nominatim(user_agent="gerie_federal_v3")
        # Búsqueda flexible en toda Argentina
        query = f"{calle}, {ciudad}, {provincia}, Argentina"
        location = geolocator.geocode(query, addressdetails=True)
        
        if location:
            # Lógica para asignar zona de precio
            nombre_ciudad = ciudad.upper()
            nombre_prov = provincia.upper()
            
            # Buscamos coincidencias en nuestra base de datos
            precios = DATA_ZONAS["DEFAULT"]
            for zona in DATA_ZONAS:
                if zona in nombre_ciudad or zona in nombre_prov:
                    precios = DATA_ZONAS[zona]
                    break
            
            st.session_state.datos = {
                "lat": location.latitude,
                "lon": location.longitude,
                "addr": location.address,
                "zona_detectada": ciudad if ciudad else "Referencia General",
                "precios": precios,
                "m2": m2
            }
        else:
            st.error("No se encontró la ubicación. Verifique los nombres de ciudad y provincia.")

# --- 4. RESULTADOS ---
if st.session_state.datos:
    d = st.session_state.datos
    p = d['precios']
    v_avg, v_min, v_max = p['avg']*d['m2'], p['min']*d['m2'], p['max']*d['m2']

    st.success(f"📍 Ubicación detectada: {d['addr']}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Mínimo m2", f"US$ {p['min']}")
    col2.metric("Promedio m2", f"US$ {p['avg']}")
    col3.metric("Máximo m2", f"US$ {p['max']}")

    st.subheader("Valuación Patrimonial para Fianza")
    df = pd.DataFrame({
        "Escenario": ["Base (Mínimo)", "Mercado (Promedio)", "Premium (Máximo)"],
        "Dólares (USD)": [f"US$ {v_min:,.0f}", f"US$ {v_avg:,.0f}", f"US$ {v_max:,.0f}"],
        "Pesos (BNA)": [f"$ {v_min*dolar_act:,.0f}", f"$ {v_avg*dolar_act:,.0f}", f"$ {v_max*dolar_act:,.0f}"]
    })
    st.table(df)

    # Indicador para analistas de riesgo
    st.info(f"💡 **Valor sugerido para fianza (80% del promedio): US$ {v_avg*0.80:,.0f}**")

    # --- MAPAS Y STREET VIEW ---
    c_mapa, c_street = st.columns(2)
    with c_mapa:
        st.write("**Mapa de Ubicación**")
        m = folium.Map(location=[d['lat'], d['lon']], zoom_start=16)
        folium.Marker([d['lat'], d['lon']]).add_to(m)
        st_folium(m, width="100%", height=350, key="mapa_federal")
    
    with c_street:
        st.write("**Street View (Vista de Calle)**")
        # URL HTTPS corregida para evitar pantalla negra
        sv_url = f"https://www.google.com/maps/embed/v1/streetview?key=TU_API_KEY&location={d['lat']},{d['lon']}&heading=210&pitch=10&fov=90"
        
        # Como no tenemos API Key oficial, usamos el método 'svembed' pero con HTTPS:
        sv_free = f"https://maps.google.com/maps?q=&layer=c&cbll={d['lat']},{d['lon']}&cbp=11,0,0,0,0&output=svembed"
        st.markdown(f'<iframe width="100%" height="350" frameborder="0" src="{sv_free}" allowfullscreen></iframe>', unsafe_allow_html=True)

    st.caption(f"Cotización Dólar BNA: ${dolar_act} | Valuación estimada según zona: {d['zona_detectada']}")
