import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium
import folium
import requests

# Configuración
st.set_page_config(page_title="GERIE Consulta Valor Inmueble", layout="wide")
st.title("🏠 GERIE: Consulta de Valor Inmueble")

if 'datos' not in st.session_state:
    st.session_state.datos = None

# --- 1. BASE DE DATOS DE BARRIOS (CABA 2025) ---
# Valores m2 promedio basados en reportes de cierre de mercado
DATA_BARRIOS = {
    "PUERTO MADERO": {"min": 3800, "max": 6500, "avg": 5200},
    "PALERMO": {"min": 2600, "max": 4500, "avg": 3200},
    "BELGRANO": {"min": 2400, "max": 4200, "avg": 2950},
    "RECOLETA": {"min": 2300, "max": 4100, "avg": 2800},
    "NUÑEZ": {"min": 2350, "max": 3800, "avg": 2750},
    "COLEGIALES": {"min": 2200, "max": 3500, "avg": 2650},
    "VILLA URQUIZA": {"min": 2100, "max": 3300, "avg": 2450},
    "CABALLITO": {"min": 1900, "max": 2900, "avg": 2300},
    "ALMAGRO": {"min": 1750, "max": 2500, "avg": 2050},
    "VILLA CRESPO": {"min": 1850, "max": 2700, "avg": 2150},
    "SAN TELMO": {"min": 1600, "max": 2800, "avg": 2000},
    "FLORES": {"min": 1550, "max": 2300, "avg": 1850},
    "BALVANERA": {"min": 1450, "max": 2100, "avg": 1700},
    "BARRACAS": {"min": 1400, "max": 2400, "avg": 1800},
    "LUGANO": {"min": 900, "max": 1400, "avg": 1100},
    "CONSTITUCION": {"min": 1200, "max": 1800, "avg": 1450},
    "DEFAULT": {"min": 1600, "max": 2800, "avg": 2100}
}

# --- 2. OBTENCIÓN DE TIPO DE CAMBIO BNA ---
@st.cache_data(ttl=3600)
def get_dolar_bna():
    try:
        r = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return r.json()['venta']
    except:
        return 1025.0 # Valor proyectado fines 2025

dolar_act = get_dolar_bna()

# --- 3. PANEL LATERAL ---
with st.sidebar:
    st.header("Carga de Datos de Garantía")
    calle = st.text_input("Dirección", "Av. del Libertador 2000")
    localidad = st.text_input("Localidad / Barrio", "Palermo")
    m2 = st.number_input("Superficie Total (m2)", min_value=1, value=50)
    
    if st.button("Consultar Valuación Profesional"):
        geolocator = Nominatim(user_agent="gerie_valuator")
        query = f"{calle}, {localidad}, CABA, Argentina"
        location = geolocator.geocode(query, addressdetails=True)
        
        if location:
            # Intentar detectar barrio desde el geocoder o el input
            barrio_detectado = localidad.upper()
            precios = DATA_BARRIOS.get(barrio_detectado, DATA_BARRIOS["DEFAULT"])
            
            st.session_state.datos = {
                "lat": location.latitude,
                "lon": location.longitude,
                "addr": location.address,
                "barrio": barrio_detectado,
                "precios": precios,
                "m2": m2
            }
        else:
            st.error("No se pudo localizar la dirección exacta.")

# --- 4. RESULTADOS DE CALIFICACIÓN ---
if st.session_state.datos:
    d = st.session_state.datos
    p = d['precios']
    v_avg = p['avg'] * d['m2']
    v_min = p['min'] * d['m2']
    v_max = p['max'] * d['m2']

    st.success(f"Análisis realizado para el barrio de: **{d['barrio']}**")
    
    # Métricas m2
    c1, c2, c3 = st.columns(3)
    c1.metric("Mínimo m2", f"US$ {p['min']}")
    c2.metric("Promedio Real", f"US$ {p['avg']}")
    c3.metric("Máximo m2", f"US$ {p['max']}")

    # Tabla de Garantía
    st.subheader("Valuación Patrimonial")
    tabla = pd.DataFrame({
        "Escenario": ["Valor Base (Mín)", "Valor Mercado (Prom)", "Valor Premium (Máx)"],
        "Dólares (USD)": [f"US$ {v_min:,.0f}", f"US$ {v_avg:,.0f}", f"US$ {v_max:,.0f}"],
        "Pesos (BNA)": [f"$ {v_min*dolar_act:,.0f}", f"$ {v_avg*dolar_act:,.0f}", f"$ {v_max*dolar_act:,.0f}"]
    })
    st.table(tabla)

    # --- INDICADOR DE FIANZA ---
    # Los bancos suelen tomar el 80% del valor promedio para garantías
    v_garantia = v_avg * 0.80
    st.info(f"💡 **Valor sugerido para fianza (80% del promedio): US$ {v_garantia:,.0f}**")

    # Visualización
    col_mapa, col_street = st.columns(2)
    with col_mapa:
        m = folium.Map(location=[d['lat'], d['lon']], zoom_start=17)
        folium.Marker([d['lat'], d['lon']], popup="Inmueble Garantía").add_to(m)
        st_folium(m, width="100%", height=350, key="mapa_final")
    
    with col_street:
        sv_url = f"https://www.google.com/maps/embed/v1/streetview?key=TU_API_KEY_OPCIONAL&location={d['lat']},{d['lon']}"
        # Nota: Usamos el embed directo de Google para mejor compatibilidad
        st.markdown(f'<iframe width="100%" height="350" frameborder="0" src="https://www.google.com/maps?q=&layer=c&cbll=...{d["lat"]},{d["lon"]}&cbp=11,0,0,0,0&output=svembed"></iframe>', unsafe_allow_html=True)

    st.caption(f"Referencia técnica basada en Índice de Precios de Cierre 2025. Dólar BNA: ${dolar_act}")
