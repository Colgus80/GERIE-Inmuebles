import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium
import folium
import requests

# Configuración de página
st.set_page_config(page_title="GERIE Consulta Valor Inmueble", layout="wide")

st.title("🏠 GERIE: Consulta de Valor Inmueble")

# --- 1. INICIALIZACIÓN DE ESTADO (Para que no desaparezcan los datos) ---
if 'consulta_realizada' not in st.session_state:
    st.session_state.consulta_realizada = False
    st.session_state.datos_propiedad = {}

# --- 2. OBTENCIÓN DE TIPO DE CAMBIO ---
@st.cache_data(ttl=3600)
def get_dolar_bna():
    try:
        response = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return response.json()['venta']
    except:
        return 850.0

dolar_bna = get_dolar_bna()

def get_market_values(city):
    data_mercado = {
        "CABA": {"min": 1800, "max": 3500, "avg": 2400},
        "default": {"min": 1000, "max": 2000, "avg": 1500}
    }
    return data_mercado.get(city, data_mercado["default"])

# --- 3. BARRA LATERAL ---
with st.sidebar:
    st.header("Carga de Datos")
    direccion = st.text_input("Dirección (Calle y Altura)", "Av. del Libertador 2000")
    ciudad = st.text_input("Ciudad / Localidad", "CABA")
    superficie = st.number_input("Superficie Total (m2)", min_value=10, value=50)
    
    # Al hacer clic, activamos el estado
    if st.button("Consultar Valuación"):
        geolocator = Nominatim(user_agent="gerie_app")
        full_address = f"{direccion}, {ciudad}, Argentina"
        location = geolocator.geocode(full_address)
        
        if location:
            vals = get_market_values(ciudad)
            st.session_state.datos_propiedad = {
                "lat": location.latitude,
                "lon": location.longitude,
                "direccion": direccion,
                "vals": vals,
                "superficie": superficie
            }
            st.session_state.consulta_realizada = True
        else:
            st.error("No se encontró la dirección.")

# --- 4. VISUALIZACIÓN DE RESULTADOS ---
if st.session_state.consulta_realizada:
    d = st.session_state.datos_propiedad
    v = d['vals']
    sup = d['superficie']

    col1, col2, col3 = st.columns(3)
    col1.metric("Mínimo m2", f"US$ {v['min']}")
    col2.metric("Promedio m2", f"US$ {v['avg']}")
    col3.metric("Máximo m2", f"US$ {v['max']}")

    st.subheader("Valor Total Estimado")
    df_vals = pd.DataFrame({
        "Referencia": ["Mínimo", "Promedio", "Máximo"],
        "Dólares (USD)": [f"US$ {v['min']*sup:,.0f}", f"US$ {v['avg']*sup:,.0f}", f"US$ {v['max']*sup:,.0f}"],
        "Pesos (ARS)": [f"$ {v['min']*sup*dolar_bna:,.0f}", f"$ {v['avg']*sup*dolar_bna:,.0f}", f"$ {v['max']*sup*dolar_bna:,.0f}"]
    })
    st.table(df_vals)

    # Mapas
    m = folium.Map(location=[d['lat'], d['lon']], zoom_start=17)
    folium.Marker([d['lat'], d['lon']], popup=d['direccion']).add_to(m)
    st_folium(m, width=900, height=400, key="mapa_fijo")
    
    # Street View
    st.markdown(f'<iframe width="100%" height="400" src="https://maps.google.com/maps?q={d["lat"]},{d["lon"]}&layer=c&cbll={d["lat"]},{d["lon"]}&output=svembed"></iframe>', unsafe_allow_html=True)

else:
    st.info("Complete los datos en el panel izquierdo y presione 'Consultar Valuación'.")
