import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium
import folium
import requests

# Configuración de página
st.set_page_config(page_title="GERIE Consulta Valor Inmueble", layout="wide")

st.title("🏠 GERIE: Consulta de Valor Inmueble")
st.markdown("Obtenga valuaciones estimadas y visualización geográfica en tiempo real.")

# --- 1. OBTENCIÓN DE TIPO DE CAMBIO (BNA) ---
@st.cache_data(ttl=3600)
def get_dolar_bna():
    try:
        # Usamos una API pública para obtener el valor del dólar oficial
        response = requests.get("https://dolarapi.com/v1/dolares/oficial")
        data = response.json()
        return data['venta']
    except:
        return 850.0  # Valor de respaldo

dolar_bna = get_dolar_bna()

# --- 2. LÓGICA DE VALORIZACIÓN (Simulada por zona) ---
# En un escenario real, aquí conectarías con tu base de datos de precios m2
def get_market_values(city):
    # Valores de ejemplo por m2 según zona
    data_mercado = {
        "CABA": {"min": 1800, "max": 3500, "avg": 2400},
        "Rosario": {"min": 900, "max": 1800, "avg": 1300},
        "Córdoba": {"min": 850, "max": 1700, "avg": 1200},
        "default": {"min": 1000, "max": 2000, "avg": 1500}
    }
    return data_mercado.get(city, data_mercado["default"])

# --- 3. INTERFAZ DE USUARIO ---
with st.sidebar:
    st.header("Carga de Datos")
    direccion = st.text_input("Dirección (Calle y Altura)", "Av. del Libertador 2000")
    ciudad = st.text_input("Ciudad / Localidad", "CABA")
    superficie = st.number_input("Superficie Total (m2)", min_value=10, value=50)
    
    buscar = st.button("Consultar Valuación")

if buscar:
    geolocator = Nominatim(user_agent="gerie_app")
    full_address = f"{direccion}, {ciudad}, Argentina"
    location = geolocator.geocode(full_address)

    if location:
        vals = get_market_values(ciudad)
        
        # Cálculos
        val_total_avg_usd = vals['avg'] * superficie
        val_total_min_usd = vals['min'] * superficie
        val_total_max_usd = vals['max'] * superficie

        # Layout de resultados
        col1, col2, col3 = st.columns(3)
        col1.metric("Valor Mínimo (USD)", f"US$ {vals['min']}")
        col2.metric("Valor Promedio (USD)", f"US$ {vals['avg']}", delta_color="normal")
        col3.metric("Valor Máximo (USD)", f"US$ {vals['max']}")

        st.divider()

        # Tabla Comparativa USD vs ARS
        st.subheader("Estimación Valor Total de la Propiedad")
        df_vals = pd.DataFrame({
            "Referencia": ["Mínimo", "Promedio", "Máximo"],
            "Dólares (USD)": [f"US$ {val_total_min_usd:,.0f}", f"US$ {val_total_avg_usd:,.0f}", f"US$ {val_total_max_usd:,.0f}"],
            "Pesos (ARS - BNA)": [f"$ {val_total_min_usd * dolar_bna:,.0f}", f"$ {val_total_avg_usd * dolar_bna:,.0f}", f"$ {val_total_max_usd * dolar_bna:,.0f}"]
        })
        st.table(df_vals)

        # --- 4. MAPAS ---
        st.subheader("Ubicación y Entorno")
        tab1, tab2 = st.tabs(["Mapa de Ubicación", "Vista de Calle (StreetView)"])
        
        with tab1:
            m = folium.Map(location=[location.latitude, location.longitude], zoom_start=17)
            folium.Marker([location.latitude, location.longitude], popup=direccion).add_to(m)
            st_folium(m, width=700, height=400)

        with tab2:
            # Embebido de StreetView (Requiere que el usuario vea el iframe)
            st.markdown(f'<iframe width="100%" height="400" src="https://maps.google.com/maps?q={location.latitude},{location.longitude}&layer=c&cbll={location.latitude},{location.longitude}&cbp=12,0,0,0,0&source=embed&output=svembed"></iframe>', unsafe_allow_html=True)
            
    else:
        st.error("No se pudo encontrar la dirección. Por favor, sea más específico.")

else:
    st.info("Ingrese la dirección a la izquierda para comenzar la consulta.")

# Footer
st.caption(f"Cotización Dólar BNA utilizada: $ {dolar_bna} | Datos con fines informativos.")
