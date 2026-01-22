import streamlit as st
import folium
import requests
import pandas as pd
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium

# --- 1. CONFIGURACIÓN DEL SISTEMA EXPERTO ---
st.set_page_config(page_title="GERIE PRO - Valuador Bancario", layout="wide", initial_sidebar_state="expanded")

# Inyección de CSS para estética financiera profesional
st.markdown("""
    <style>
    .metric-card {background-color: #f8f9fa; border-left: 5px solid #1f77b4; padding: 15px; border-radius: 5px; margin-bottom: 10px;}
    .risk-alert {background-color: #ffebee; border: 1px solid #ffcdd2; padding: 10px; border-radius: 5px; color: #b71c1c;}
    .safe-zone {background-color: #e8f5e9; border: 1px solid #c8e6c9; padding: 10px; border-radius: 5px; color: #1b5e20;}
    </style>
""", unsafe_allow_html=True)

# Inicialización de Variables de Sesión (Persistencia)
if 'coords' not in st.session_state:
    st.session_state.coords = [-34.6037, -58.3816] # Default: Obelisco
if 'zoom' not in st.session_state:
    st.session_state.zoom = 12
if 'valuacion_data' not in st.session_state:
    st.session_state.valuacion_data = None

# --- 2. MOTORES DE DATOS EN TIEMPO REAL ---

@st.cache_data(ttl=3600)
def get_dolar_bna():
    """Obtiene cotización oficial BNA (Venta) para conversión normativa."""
    try:
        r = requests.get("https://dolarapi.com/v1/dolares/oficial", timeout=5)
        return r.json()['venta']
    except:
        return 1150.0 # Fallback conservador

def get_valor_base_m2(tipo, zona_calidad):
    """
    MATRIZ DE VALUACIÓN HEURÍSTICA 2026.
    Ajusta el valor base según la tipología y la categoría socioeconómica de la zona.
    """
    # Matriz de Precios Referenciales (USD/m2) - Fuente: Relevamiento de Mercado
    precios = {
        "Casa": {"Premium": 2100, "Alta": 1600, "Media": 1200, "Baja": 850},
        "Departamento": {"Premium": 2800, "Alta": 2200, "Media": 1650, "Baja": 1100},
        "Local Comercial": {"Premium": 3500, "Alta": 2500, "Media": 1800, "Baja": 1000},
        "Depósito/Galpón": {"Premium": 1200, "Alta": 900, "Media": 650, "Baja": 400}
    }
    return precios.get(tipo, {}).get(zona_calidad, 1000)

def analizar_riesgo_geo(lat, lon):
    """Motor de detección de riesgo por proximidad a asentamientos precarios."""
    # Base de datos simplificada de focos de riesgo (Ejemplo GBA Norte/Oeste/Sur)
    # En producción, esto se conectaría a la base completa del RENABAP
    focos = [
        {"nombre": "La Cava (San Isidro)", "lat": -34.4720, "lon": -58.5422},
        {"nombre": "Barrio Itatí (San Fernando)", "lat": -34.4600, "lon": -58.5445},
        {"nombre": "Villa 31 (Retiro)", "lat": -34.5833, "lon": -58.3786},
        {"nombre": "Fuerte Apache", "lat": -34.6225, "lon": -58.5392},
        {"nombre": "Villa La Rana", "lat": -34.5668, "lon": -58.5577},
        {"nombre": "Carlos Gardel", "lat": -34.6335, "lon": -58.5750}
    ]
    
    dist_min = 99999
    nombre_f = ""
    for f in focos:
        d = geodesic((lat, lon), (f['lat'], f['lon'])).meters
        if d < dist_min:
            dist_min = d
            nombre_f = f['nombre']
    
    return dist_min, nombre_f

# --- 3. INTERFAZ DE CONTROL (SIDEBAR) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2830/2830289.png", width=50)
    st.title("GERIE PRO")
    st.markdown("**Sistema de Valuación de Garantías**")
    st.markdown("---")
    
    with st.form("panel_control"):
        st.subheader("1. Ubicación y Tipología")
        # Datos geográficos
        direccion = st.text_input("Calle y Altura", value="Av. Rolón 1300")
        localidad = st.text_input("Barrio / Localidad", value="Beccar")
        provincia = st.selectbox("Provincia", ["Buenos Aires", "CABA", "Córdoba", "Santa Fe", "Mendoza", "Resto del País"])
        
        # Datos del activo
        tipo_inmueble = st.selectbox("Tipo de Inmueble", ["Casa", "Departamento", "Local Comercial", "Depósito/Galpón"])
        m2 = st.number_input("Superficie Total (m²)", value=100.0, step=1.0)
        
        st.subheader("2. Calificación de Zona")
        st.info("ℹ️ Seleccione el perfil de la zona para ajustar el valor m².")
        calidad_zona = st.select_slider(
            "Perfil Socioeconómico / Ubicación",
            options=["Baja", "Media", "Alta", "Premium"],
            value="Media",
            help="Premium: Zonas exclusivas/Country. Alta: Centros consolidados. Media: Barrios estándar. Baja: Periferia/Mixto industrial."
        )
        
        buscar = st.form_submit_button("📍 BUSCAR Y VALUAR")

# --- 4. LÓGICA DE BÚSQUEDA Y REFINAMIENTO ---
if buscar:
    try:
        # Intento de geolocalización automática
        geo = Nominatim(user_agent="gerie_pro_bank_v10")
        # Optimizamos la query para evitar el error de Av Rolón
        query = f"{direccion}, {localidad}, {provincia}, Argentina"
        loc = geo.geocode(query, timeout=10)
        
        if loc:
            st.session_state.coords = [loc.latitude, loc.longitude]
            st.session_state.zoom = 16
            st.toast(f"Ubicación encontrada: {loc.address}", icon="✅")
        else:
            st.error("No se encontró la altura exacta. Se centrará en la localidad.")
            # Fallback a localidad
            loc_general = geo.geocode(f"{localidad}, {provincia}, Argentina")
            if loc_general:
                st.session_state.coords = [loc_general.latitude, loc_general.longitude]
                st.session_state.zoom = 14
    except Exception as e:
        st.error(f"Error de conexión con el servidor de mapas: {e}")

# --- 5. VISUALIZACIÓN INTERACTIVA (EL NÚCLEO DEL SISTEMA) ---

col_map, col_data = st.columns([1.2, 1])

with col_map:
    st.subheader("🗺️ Validación Geográfica de Precisión")
    st.caption("🔍 **Instrucción Crítica:** Si el punto rojo no es exacto, **haga clic en el mapa** sobre el techo de la propiedad real. El sistema recalculará todo instantáneamente.")
    
    # Mapa Base
    m = folium.Map(location=st.session_state.coords, zoom_start=st.session_state.zoom, control_scale=True)
    
    # Capa de Satélite (Google Maps) para máxima precisión visual
    folium.TileLayer(
        tiles = 'https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr = 'Google',
        name = 'Google Satélite',
        overlay = False,
        control = True
    ).add_to(m)
    
    # Marcador y Radio de Riesgo
    folium.Marker(
        st.session_state.coords, 
        popup="Ubicación Analizada", 
        icon=folium.Icon(color="red", icon="home")
    ).add_to(m)
    
    folium.Circle(
        st.session_state.coords, 
        radius=500, 
        color="#e53935", 
        fill=True, 
        fill_opacity=0.1, 
        tooltip="Radio de Análisis de Entorno (500m)"
    ).add_to(m)

    # Captura de interacción del usuario
    map_output = st_folium(m, height=500, width=None)

# --- 6. PROCESAMIENTO DE DATOS (POST-INTERACCIÓN) ---

# Si el usuario hizo clic en el mapa, actualizamos las coordenadas
if map_output['last_clicked']:
    st.session_state.coords = [map_output['last_clicked']['lat'], map_output['last_clicked']['lng']]
    # No hacemos rerun forzoso para evitar parpadeo, calculamos con los nuevos datos

# Variables finales para cálculo
lat_final, lon_final = st.session_state.coords
dist_riesgo, nombre_riesgo = analizar_riesgo_geo(lat_final, lon_final)
dolar_oficial = get_dolar_bna()

# Lógica de Tasación
valor_base_m2 = get_valor_base_m2(tipo_inmueble, calidad_zona)
factor_castigo = 0.65 if dist_riesgo < 500 else 1.0

# Ajuste fino: Valor final
valor_m2_final = valor_base_m2 * factor_castigo
valor_total_usd = valor_m2_final * m2
valor_total_ars = valor_total_usd * dolar_oficial

# Rangos de negociación (Norma de tasación)
rango_min = valor_total_usd * 0.85
rango_max = valor_total_usd * 1.15

with col_data:
    st.subheader("📊 Informe de Valuación Técnica")
    
    # Alertas de Compliance
    if dist_riesgo < 500:
        st.markdown(f"""
        <div class="risk-alert">
            🚨 <b>ALERTA DE RIESGO SEVERO</b><br>
            La propiedad se encuentra a <b>{dist_riesgo:.0f} metros</b> de un foco de riesgo ({nombre_riesgo}).<br>
            <i>Se ha aplicado un factor de castigo del 35% sobre el valor de mercado.</i>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="safe-zone">
            ✅ <b>ENTORNO VALIDADO</b><br>
            Propiedad fuera de radios de riesgo críticos detectados.<br>
            Distancia mínima a foco: {dist_riesgo:.0f} metros.
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # Panel de Precios
    t1, t2 = st.tabs(["💵 Valuación", "📈 Datos Técnicos"])
    
    with t1:
        st.markdown(f"### Valor de Realización Sugerido (USD)")
        st.metric("Total USD", f"USD {valor_total_usd:,.0f}", delta=f"Rango: {rango_min:,.0f} - {rango_max:,.0f} k", delta_color="off")
        
        st.markdown("### Cobertura en Pesos (BNA)")
        st.markdown(f"""
        <div style="background: #e3f2fd; padding: 15px; border-radius: 10px; text-align: center;">
            <h2 style="color: #1565c0; margin: 0;">$ {valor_total_ars:,.0f}</h2>
            <small>Cotización BNA: ${dolar_oficial}</small>
        </div>
        """, unsafe_allow_html=True)

    with t2:
        st.write("**Desglose del Cálculo:**")
        df_calc = pd.DataFrame({
            "Concepto": ["Valor Base Zona", "Factor de Ajuste", "Valor m² Final", "Superficie"],
            "Valor": [f"USD {valor_base_m2}", f"{factor_castigo*100:.0f}%", f"USD {valor_m2_final:.0f}", f"{m2} m²"]
        })
        st.table(df_calc)
        
        st.write(f"**Coordenadas GPS:** {lat_final:.6f}, {lon_final:.6f}")

# --- 7. EXPORTACIÓN ---
st.markdown("---")
st.caption("Gobernanza de Datos: Dólar BNA (API Tiempo Real) | Cartografía Google/OSM | Valores Referenciales Matriz 2026")
