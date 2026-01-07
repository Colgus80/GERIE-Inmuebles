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

# --- FUNCIONES DE DATOS ---

@st.cache_data(ttl=3600)
def get_dolar_bna():
    try:
        response = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return response.json()['venta']
    except:
        return 980.0

@st.cache_data
def cargar_datos_renabap():
    url = "https://datosabiertos.desarrollosocial.gob.ar/dataset/0d50730b-1662-4217-9ef1-37018c1b359f/resource/828292d3-96b4-4b9e-99e5-b1030e466b0a/download/barrios-populares.json"
    try:
        return gpd.read_file(url)
    except:
        return None

def get_market_values(provincia_localidad):
    # Diccionario ampliado de precios base
    data_mercado = {
        "CABA": {"min": 1800, "max": 3500, "avg": 2400},
        "BUENOS AIRES": {"min": 1300, "max": 2800, "avg": 1800},
        "SANTA FE": {"min": 950, "max": 1900, "avg": 1350},
        "CORDOBA": {"min": 900, "max": 1850, "avg": 1250},
        "MENDOZA": {"min": 850, "max": 1700, "avg": 1150},
        "default": {"min": 1000, "max": 2000, "avg": 1400}
    }
    # Busca coincidencias en el texto ingresado
    for key in data_mercado:
        if key in provincia_localidad.upper():
            return data_mercado[key]
    return data_mercado["default"]

def calcular_ajuste_entorno(distancia_m):
    if distancia_m < 200: return 0.70, "Crítico (-30%)"
    if distancia_m < 400: return 0.85, "Alto (-15%)"
    if distancia_m < 600: return 0.93, "Moderado (-7%)"
    return 1.0, "Nulo (0%)"

# --- INTERFAZ ---
st.title("🏢 GERIE: Consulta Valor Inmueble")
st.markdown("### Tasación Referencial y Análisis de Riesgo en toda Argentina")

# Uso de Formulario para evitar que los datos desaparezcan al interactuar
with st.sidebar:
    st.header("📍 Datos del Inmueble")
    with st.form("consulta_form"):
        direccion = st.text_input("Calle y Altura", placeholder="Ej: Av. Colón 1500")
        localidad = st.text_input("Localidad y Provincia", placeholder="Ej: Mar del Plata, Buenos Aires")
        superficie = st.number_input("Superficie m2", min_value=1, value=50)
        submitted = st.form_submit_button("CONSULTAR VALUACIÓN", use_container_width=True)

dolar_bna = get_dolar_bna()

if submitted:
    if not direccion or not localidad:
        st.warning("Por favor, complete la dirección y la localidad.")
    else:
        with st.spinner('Procesando ubicación y base de datos RENABAP...'):
            geolocator = Nominatim(user_agent="gerie_app_v2")
            # Buscador más abierto
            query_busqueda = f"{direccion}, {localidad}, Argentina"
            location = geolocator.geocode(query_busqueda)

            if location:
                lat, lon = location.latitude, location.longitude
                
                # Análisis RENABAP
                gdf_barrios = cargar_datos_renabap()
                dist_min = 99999
                if gdf_barrios is not None:
                    for _, barrio in gdf_barrios.iterrows():
                        centro = barrio.geometry.centroid
                        d = geodesic((lat, lon), (centro.y, centro.x)).meters
                        if d < dist_min: dist_min = d
                
                factor, impacto_txt = calcular_ajuste_entorno(dist_min)
                
                # Valores de mercado según el texto de localidad
                base_vals = get_market_values(localidad)
                m2_min, m2_avg, m2_max = base_vals['min']*factor, base_vals['avg']*factor, base_vals['max']*factor

                # --- RESULTADOS ---
                st.success(f"📍 Ubicación encontrada: {location.address}")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("M2 Mínimo", f"USD {m2_min:,.0f}")
                c2.metric("M2 Promedio", f"USD {m2_avg:,.0f}", delta=f"-{impacto_txt}" if factor < 1 else None, delta_color="inverse")
                c3.metric("M2 Máximo", f"USD {m2_max:,.0f}")

                st.divider()
                
                # Tabla Comparativa
                val_usd = m2_avg * superficie
                df_resumen = pd.DataFrame({
                    "Concepto": ["Valor Total (Promedio)", "Valor Total (Mínimo)", "Valor Total (Máximo)"],
                    "Dólares (USD)": [f"US$ {val_usd:,.0f}", f"US$ {m2_min*superficie:,.0f}", f"US$ {m2_max*superficie:,.0f}"],
                    "Pesos (BNA)": [f"$ {val_usd*dolar_bna:,.0f}", f"$ {m2_min*superficie*dolar_bna:,.0f}", f"$ {m2_max*superficie*dolar_bna:,.0f}"]
                })
                st.table(df_resumen)

                # Mapas
                col_m, col_s = st.columns(2)
                with col_m:
                    st.subheader("🗺️ Mapa de Zona")
                    m = folium.Map(location=[lat, lon], zoom_start=16)
                    folium.Marker([lat, lon], popup="Propiedad").add_to(m)
                    st_folium(m, height=400, width=500)
                
                with col_s:
                    st.subheader("📸 Street View")
                    # Iframe dinámico
                    sv_url = f"https://www.google.com/maps/embed/v1/streetview?key=TU_API_KEY_AQUI&location={lat},{lon}"
                    # Nota: Para StreetView real se requiere API Key, aquí usamos el truco del visualizador público:
                    st.markdown(f'<iframe width="100%" height="400" src="https://maps.google.com/maps?q={lat},{lon}&layer=c&cbll={lat},{lon}&output=svembed"></iframe>', unsafe_allow_html=True)

                if factor < 1:
                    st.error(f"⚠️ El valor ha sido ajustado debido a la proximidad ({dist_min:.0f}m) de un asentamiento registrado en RENABAP.")
                else:
                    st.info("✅ Zona analizada sin factores de riesgo detectados en el radio inmediato.")

            else:
                st.error("❌ No se encontró la dirección exacta. Intente con 'Calle Altura, Ciudad, Provincia'.")

# Footer
st.caption(f"Cotización BNA: ${dolar_bna} | GERIE Consulta Valor Inmueble | Datos RENABAP Actualizados")
