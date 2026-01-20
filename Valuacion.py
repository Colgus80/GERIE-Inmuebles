import streamlit as st
import folium
import requests
from geopy.distance import geodesic
from streamlit_folium import st_folium

# 1. CONFIGURACIÓN
st.set_page_config(page_title="GERIE - Valuador de Precisión", layout="wide")

# 2. MOTORES DE DATOS
@st.cache_data(ttl=3600)
def obtener_cotizacion_bna():
    try:
        r = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return r.json()['venta']
    except: return 1100.0 

def calcular_riesgo_entorno(lat, lon):
    focos = [
        {"nombre": "La Cava", "lat": -34.4720, "lon": -58.5422},
        {"nombre": "Barrio Itatí / San Jorge", "lat": -34.4600, "lon": -58.5445}
    ]
    dist_min = 99999
    nombre_f = ""
    for f in focos:
        d = geodesic((lat, lon), (f['lat'], f['lon'])).meters
        if d < dist_min:
            dist_min = d
            nombre_f = f['nombre']
    return dist_min, nombre_f

# 3. INTERFAZ LATERAL
with st.sidebar:
    st.title("🏦 Control de Garantías")
    st.warning("Si el buscador falla, hacé CLIC en el mapa para ubicar el pin exactamente.")
    
    with st.form("config_analisis"):
        tipo = st.selectbox("Tipo de Inmueble", ["Casa", "Departamento", "Local Comercial", "Depósito/Galpón", "Campo Agrícola", "Campo Ganadero"])
        superficie = st.number_input("Superficie (m2 o Ha)", value=1.0, min_value=0.1)
        direccion_buscada = st.text_input("Buscador rápido", value="Av. Rolón 1300, Beccar")
        st.form_submit_button("1. BUSCAR / REINICIAR")

# 4. LÓGICA DE GEOLOCALIZACIÓN INICIAL
if 'lat' not in st.session_state or st.session_state.get('last_search') != direccion_buscada:
    try:
        from geopy.geocoders import Nominatim
        geo = Nominatim(user_agent="gerie_final_v7")
        res = geo.geocode(f"{direccion_buscada}, Buenos Aires, Argentina")
        if res:
            st.session_state.lat, st.session_state.lon = res.latitude, res.longitude
        else:
            st.session_state.lat, st.session_state.lon = -34.6037, -58.3816 # Obelisco fallback
        st.session_state.last_search = direccion_buscada
    except: pass

# 5. MAPA INTERACTIVO (LA CLAVE DE LA PRECISIÓN)
st.subheader("📍 Validar Ubicación Exacta")
st.info("Hacé clic en el lugar correcto del mapa para actualizar la tasación si el buscador falló.")

m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=16)
folium.Marker([st.session_state.lat, st.session_state.lon], draggable=False).add_to(m)
# Círculo de riesgo dinámico
folium.Circle([st.session_state.lat, st.session_state.lon], radius=500, color="red", fill=True, opacity=0.1).add_to(m)

# Capturar el clic del usuario
mapa_data = st_folium(m, height=450, width=None)

# Si el usuario hace clic, actualizamos las coordenadas globales
if mapa_data.get("last_clicked"):
    st.session_state.lat = mapa_data["last_clicked"]["lat"]
    st.session_state.lon = mapa_data["last_clicked"]["lng"]
    st.rerun()

# 6. CÁLCULOS Y RESULTADOS BASADOS EN EL PIN (Donde sea que esté)
dist_f, nombre_f = calcular_riesgo_entorno(st.session_state.lat, st.session_state.lon)
dolar = obtener_cotizacion_bna()

config_valuacion = {
    "Casa": 1500, "Departamento": 1850, "Local Comercial": 2200, 
    "Depósito/Galpón": 850, "Campo Agrícola": 12000, "Campo Ganadero": 4500
}

es_ha = "Campo" in tipo
factor_riesgo = 0.65 if (not es_ha and dist_f < 500) else 1.0
val_unitario = config_valuacion[tipo] * factor_riesgo
total_usd = val_unitario * superficie
total_ars = total_usd * dolar

# 7. REPORTE FINAL
st.markdown("---")
col1, col2, col3 = st.columns(3)
col1.metric("Ubicación Actual (GPS)", f"{st.session_state.lat:.5f}, {st.session_state.lon:.5f}")
col2.metric("Distancia a Riesgo", f"{dist_f:.0f} metros")
col3.metric("Valor Metro/Ha", f"USD {val_unitario:,.0f}")

if not es_ha and dist_f < 500:
    st.error(f"🚨 ALERTA: Propiedad dentro de zona de riesgo ({nombre_f}). Valor castigado un 35%.")

st.markdown(f"""
    <div style="background-color:#f0f2f6; padding:20px; border-radius:15px; text-align:center; border: 2px solid #1f77b4;">
        <h2 style="margin:0;">VALUACIÓN FINAL EN PESOS</h2>
        <h1 style="color:#1f77b4; font-size:50px; margin:10px 0;">$ {total_ars:,.0f}</h1>
        <p>Calculado sobre {superficie} {'Ha' if es_ha else 'm²'} a una cotización de $ {dolar}</p>
    </div>
""", unsafe_allow_html=True)
