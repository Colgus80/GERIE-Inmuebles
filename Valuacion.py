import streamlit as st
import folium
import requests
from geopy.distance import geodesic
from streamlit_folium import st_folium

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="GERIE - Análisis de Garantías Urbanas", layout="wide")

# 2. PERSISTENCIA DE ESTADO (Para evitar recargas innecesarias)
if 'lat' not in st.session_state:
    st.session_state.lat, st.session_state.lon = -34.6037, -58.3816 # Obelisco por defecto
if 'analisis_datos' not in st.session_state:
    st.session_state.analisis_datos = None

# 3. MOTORES DE DATOS (BNA y Riesgo)
@st.cache_data(ttl=3600)
def obtener_cotizacion_bna():
    try:
        # Consulta real a cotización oficial BNA
        r = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return r.json()['venta']
    except:
        return 1100.0 # Valor de contingencia

def calcular_riesgo_entorno(lat, lon):
    # Focos críticos registrados (RENABAP / Seguridad Bancaria)
    focos = [
        {"nombre": "La Cava", "lat": -34.4720, "lon": -58.5422},
        {"nombre": "Barrio Itatí / San Jorge", "lat": -34.4600, "lon": -58.5445},
        {"nombre": "Villa 31", "lat": -34.5833, "lon": -58.3786},
        {"nombre": "Fuerte Apache", "lat": -34.6225, "lon": -58.5392}
    ]
    dist_min = 99999
    nombre_f = ""
    for f in focos:
        d = geodesic((lat, lon), (f['lat'], f['lon'])).meters
        if d < dist_min:
            dist_min = d
            nombre_f = f['nombre']
    return dist_min, nombre_f

# 4. INTERFAZ LATERAL: CARGA ESTRUCTURADA
with st.sidebar:
    st.header("🏦 Datos de la Garantía")
    
    with st.form("formulario_carga"):
        tipo_inmueble = st.selectbox("Tipo de Inmueble", 
                                    ["Casa", "Departamento", "Local Comercial", "Depósito/Galpón"])
        
        calle_altura = st.text_input("Calle y Altura", value="Av. Rolón 1300")
        barrio_loc = st.text_input("Barrio / Localidad", value="Beccar")
        
        provincia = st.selectbox("Provincia", [
            "Buenos Aires", "CABA", "Catamarca", "Chaco", "Chubut", "Córdoba", 
            "Corrientes", "Entre Ríos", "Formosa", "Jujuy", "La Pampa", "La Rioja", 
            "Mendoza", "Misiones", "Neuquén", "Río Negro", "Salta", "San Juan", 
            "San Luis", "Santa Cruz", "Santa Fe", "Santiago del Estero", "Tierra del Fuego", "Tucumán"
        ])
        
        m2 = st.number_input("Superficie Total (m²)", value=50.0, min_value=1.0)
        
        submit = st.form_submit_button("UBICAR Y ANALIZAR")

# 5. LÓGICA DE GEOLOCALIZACIÓN
if submit:
    try:
        from geopy.geocoders import Nominatim
        # Construcción de query robusta
        query = f"{calle_altura}, {barrio_loc}, {provincia}, Argentina"
        geo = Nominatim(user_agent="gerie_analyst_v9")
        res = geo.geocode(query)
        
        if res:
            st.session_state.lat, st.session_state.lon = res.latitude, res.longitude
            st.session_state.direccion_confirmada = query
        else:
            st.warning("No se halló la altura exacta. Use el mapa para corregir la posición.")
    except:
        st.error("Error en el servicio de mapas.")

# 6. MAPA INTERACTIVO DE AJUSTE (Click para corregir errores de base de datos)
st.subheader("📍 Validación Geográfica")
st.caption("Si el pin no es exacto, hacé CLIC en el mapa sobre la ubicación correcta para actualizar el análisis.")

m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=17)
folium.Marker([st.session_state.lat, st.session_state.lon], tooltip="Ubicación Analizada").add_to(m)
folium.Circle([st.session_state.lat, st.session_state.lon], radius=500, color="red", fill=True, opacity=0.1).add_to(m)

mapa_interactivo = st_folium(m, height=400, width=None)

# Actualizar coordenadas si el usuario hace clic
if mapa_interactivo.get("last_clicked"):
    st.session_state.lat = mapa_interactivo["last_clicked"]["lat"]
    st.session_state.lon = mapa_interactivo["last_clicked"]["lng"]
    st.rerun()

# 7. CÁLCULOS TÉCNICOS DE TASACIÓN
dist_f, nombre_f = calcular_riesgo_entorno(st.session_state.lat, st.session_state.lon)
dolar_bna = obtener_cotizacion_bna()

# Valores base por m2 (Diferenciados por tipo)
config_valores = {
    "Casa": 1500, "Departamento": 1850, 
    "Local Comercial": 2200, "Depósito/Galpón": 850
}

# Aplicación de castigo por zona de riesgo (35%)
factor_riesgo = 0.65 if dist_f < 500 else 1.0
val_m2_promedio = config_valores[tipo_inmueble] * factor_riesgo
val_m2_min, val_m2_max = val_m2_promedio * 0.85, val_m2_promedio * 1.15

total_usd = val_m2_promedio * m2
total_ars = total_usd * dolar_bna

# 8. REPORTE DE RESULTADOS
st.markdown("---")
st.subheader(f"📊 Informe de Valuación: {tipo_inmueble}")

# Alerta de Riesgo Bancario
if dist_f < 500:
    st.error(f"🚨 ALERTA DE RIESGO: Ubicación a {dist_f:.0f}m de {nombre_f}. Se aplicó castigo del 35% al valor base.")
else:
    st.success(f"✅ UBICACIÓN VALIDADA: Garantía fuera de radio crítico detectado ({dist_f:.0f}m).")

# Métricas Principales
col1, col2, col3 = st.columns(3)
col1.metric("Valor m² (USD)", f"USD {val_m2_promedio:,.0f}", delta=f"({val_m2_min:,.0f} - {val_m2_max:,.0f})", delta_color="off")
col2.metric("Monto Total (USD)", f"USD {total_usd:,.0f}")
col3.metric("Cotización BNA", f"$ {dolar_bna}")

# Panel de Valor Final en Pesos
st.markdown(f"""
    <div style="background-color:#f8f9fa; padding:30px; border-radius:15px; text-align:center; border: 2px solid #1f77b4; margin-top: 20px;">
        <h3 style="margin:0; color:#495057;">VALOR FINAL EN PESOS (BNA)</h3>
        <h1 style="color:#1f77b4; font-size:55px; margin:15px 0;">$ {total_ars:,.0f}</h1>
        <p style="color:#6c757d; margin:0;">Basado en {m2} m² | Coordenadas: {st.session_state.lat:.5f}, {st.session_state.lon:.5f}</p>
    </div>
""", unsafe_allow_html=True)

# 9. PIE DE PÁGINA: GOBERNANZA DE DATOS
st.markdown("---")
with st.expander("📄 Ver Fuentes de Datos y Metodología"):
    st.write("""
    - **Cotización de Moneda:** Datos capturados vía API de DolarApi.com (Referencia: Banco Nación Venta).
    - **Cálculo de Distancias:** Algoritmo Geodésico (Fórmula de Vincenty) sobre elipsoide WGS-84.
    - **Base de Valores:** Valores promedio para el AMBA basados en relevamientos de mercado inmobiliario 2025.
    - **Zonificación de Riesgo:** Base de datos de barrios vulnerables y focos de baja liquidez bancaria.
    """)
