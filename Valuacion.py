import streamlit as st
import folium
import requests
import pandas as pd
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium

# --- 1. CONFIGURACIÓN DEL SISTEMA ---
st.set_page_config(page_title="GERIE EXPERT - Valuación Inteligente", layout="wide")

# CSS Profesional para Reportes
st.markdown("""
    <style>
    .report-box {padding: 20px; border-radius: 10px; border: 1px solid #ddd; background-color: #fdfdfd;}
    .premium-tag {background-color: #ffd700; color: #000; padding: 5px 10px; border-radius: 5px; font-weight: bold; font-size: 0.8em;}
    .alert-tag {background-color: #ffcdd2; color: #b71c1c; padding: 5px 10px; border-radius: 5px; font-weight: bold; font-size: 0.8em;}
    </style>
""", unsafe_allow_html=True)

if 'coords' not in st.session_state:
    st.session_state.coords = [-34.6037, -58.3816]
if 'zoom' not in st.session_state:
    st.session_state.zoom = 13
if 'perfil_sugerido' not in st.session_state:
    st.session_state.perfil_sugerido = "Media"

# --- 2. MOTORES DE INTELEGENCIA DE DATOS ---

@st.cache_data(ttl=3600)
def get_dolar_bna():
    try:
        r = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return r.json()['venta']
    except: return 1150.0

def detectar_perfil_zona(direccion, localidad, provincia):
    """
    Motor Heurístico: Determina el perfil socioeconómico basado en 
    Corredores Inmobiliarios y Localidades Clave.
    """
    dir_u = direccion.upper()
    loc_u = localidad.upper()
    
    # 1. NIVEL PREMIUM (Top Tier)
    keywords_premium = [
        "LIBERTADOR", "FIGUEROA ALCORTA", "ALVEAR", "PUERTO MADERO", 
        "NORDELTA", "BARRIO PARQUE", "LOMAS DE SAN ISIDRO", "LA HORQUETA",
        "ESTANCIA ABRIL", "HIGHLAND", "TORTUGAS"
    ]
    if any(k in dir_u for k in keywords_premium) or any(k in loc_u for k in keywords_premium):
        return "Premium"
    
    # 2. NIVEL ALTO (Zonas Consolidadas)
    keywords_alta = [
        "RECOLETA", "BELGRANO R", "PALERMO CHICO", "VICENTE LOPEZ", 
        "OLIVOS (BAJO)", "MARTINEZ (VIAS A RIO)", "SAN ISIDRO (CENTRO)",
        "COUNTRY", "BARRIO CERRADO", "CLUB DE CAMPO"
    ]
    if any(k in loc_u for k in keywords_alta) or "MAIPU" in dir_u or "SANTA FE" in dir_u:
        return "Alta"
    
    # 3. NIVEL MEDIO (Estándar)
    # Por defecto, la mayoría de los barrios consolidados caen aquí.
    return "Media"

def analizar_riesgo_geo(lat, lon):
    # Base de focos ampliada para el ejemplo
    focos = [
        {"nombre": "Villa 31 (Retiro)", "lat": -34.5846, "lon": -58.3794}, 
        {"nombre": "La Cava (San Isidro)", "lat": -34.4720, "lon": -58.5422},
        {"nombre": "Itatí (San Fernando)", "lat": -34.4600, "lon": -58.5445},
        {"nombre": "Villa 1-11-14", "lat": -34.6496, "lon": -58.4363},
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

def obtener_valor_referencia(tipo, perfil):
    # Matriz de Precios 2026 (USD/m2) refinada por corredor
    matriz = {
        "Casa": {"Premium": 2300, "Alta": 1700, "Media": 1100, "Baja": 700},
        "Departamento": {"Premium": 3200, "Alta": 2400, "Media": 1600, "Baja": 950},
        "Local Comercial": {"Premium": 4000, "Alta": 2800, "Media": 1500, "Baja": 800},
        "Depósito/Galpón": {"Premium": 1100, "Alta": 800, "Media": 500, "Baja": 300}
    }
    return matriz.get(tipo, {}).get(perfil, 1000)

# --- 3. INTERFAZ DE CARGA ---
with st.sidebar:
    st.header("🏢 GERIE EXPERT")
    st.markdown("Herramienta de Valuación Bancaria")
    st.info("El sistema detectará automáticamente si la zona es Premium (ej: Libertador, Puerto Madero).")
    
    with st.form("carga_datos"):
        tipo_inmueble = st.selectbox("Tipo de Inmueble", ["Departamento", "Casa", "Local Comercial", "Depósito/Galpón"])
        
        # Inputs de dirección
        calle = st.text_input("Calle y Altura", value="Av. del Libertador 14000")
        localidad = st.text_input("Barrio / Localidad", value="Martinez")
        provincia = st.selectbox("Provincia", ["Buenos Aires", "CABA", "Santa Fe", "Córdoba", "Mendoza", "Resto del País"])
        
        m2_total = st.number_input("Superficie Total (m²)", value=85.0)
        
        btn_analizar = st.form_submit_button("🔍 ANALIZAR ZONA Y VALOR")

# --- 4. LÓGICA DE DETECCIÓN Y GEOREFERENCIA ---
if btn_analizar:
    # 1. Detectar Perfil Socioeconómico por Texto (Heurística)
    perfil_detectado = detectar_perfil_zona(calle, localidad, provincia)
    st.session_state.perfil_sugerido = perfil_detectado
    
    # 2. Geolocalizar
    try:
        geo = Nominatim(user_agent="gerie_expert_v12")
        query = f"{calle}, {localidad}, {provincia}, Argentina"
        loc = geo.geocode(query)
        
        if loc:
            st.session_state.coords = [loc.latitude, loc.longitude]
            st.session_state.zoom = 16
        else:
            st.warning("Dirección exacta no encontrada. Se mostrará el centro de la localidad para ajuste manual.")
            loc_gen = geo.geocode(f"{localidad}, {provincia}, Argentina")
            if loc_gen:
                st.session_state.coords = [loc_gen.latitude, loc_gen.longitude]
                st.session_state.zoom = 14
    except:
        st.error("Error de conexión con servicio de mapas.")

# --- 5. ZONA DE TRABAJO (MAPA Y PERFIL) ---

# Columnas: Mapa (Izquierda) | Ajustes y Resultados (Derecha)
c_mapa, c_datos = st.columns([1.5, 1])

with c_mapa:
    st.subheader("1. Validación Geográfica")
    st.caption("Verifique que el pin rojo esté sobre la propiedad. Si no, **haga clic en el mapa** para corregir.")
    
    m = folium.Map(location=st.session_state.coords, zoom_start=st.session_state.zoom)
    # Capa Satélite (Google)
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google',
        name='Google Satélite',
        overlay=False
    ).add_to(m)
    
    folium.Marker(st.session_state.coords, icon=folium.Icon(color="red")).add_to(m)
    folium.Circle(st.session_state.coords, radius=500, color="red", fill=True, opacity=0.1).add_to(m)
    
    map_out = st_folium(m, height=500, width=None)

# Actualización por clic en mapa
if map_out['last_clicked']:
    st.session_state.coords = [map_out['last_clicked']['lat'], map_out['last_clicked']['lng']]

# --- 6. CÁLCULO EN TIEMPO REAL ---
lat_f, lon_f = st.session_state.coords
dist_r, nombre_r = analizar_riesgo_geo(lat_f, lon_f)
dolar = get_dolar_bna()

# Lógica de Conflicto: ¿Es Premium pero está pegado a una Villa?
# Caso emblemático: Libertador en Retiro cerca de Villa 31.
es_premium = st.session_state.perfil_sugerido == "Premium"
riesgo_activo = dist_r < 500

factor_ajuste = 1.0
mensaje_ajuste = "Valor de Mercado Estándar"

if riesgo_activo:
    factor_ajuste = 0.60 # Castigo del 40% (Más severo por ser zona de contraste)
    mensaje_ajuste = f"Castigo Severo (-40%) por proximidad a {nombre_r}"
elif es_premium:
    factor_ajuste = 1.10 # Plus del 10% por marca "Premium"
    mensaje_ajuste = "Plus (+10%) por Corredor Premium / Zona Exclusiva"

# Cálculo Final
val_base = obtener_valor_referencia(tipo_inmueble, st.session_state.perfil_sugerido)
val_m2_final = val_base * factor_ajuste
total_usd = val_m2_final * m2_total
total_ars = total_usd * dolar

with c_datos:
    st.subheader("2. Perfil y Valuación")
    
    # Selector de Perfil (Con sugerencia automática)
    perfil_final = st.select_slider(
        "Perfil Socioeconómico Detectado",
        options=["Baja", "Media", "Alta", "Premium"],
        value=st.session_state.perfil_sugerido,
        help="El sistema sugiere basado en calles clave (Libertador, Puerto Madero, etc). Ajuste si es necesario."
    )
    
    if perfil_final != st.session_state.perfil_sugerido:
        # Recalcular si el usuario cambia el slider manualmente
        val_base = obtener_valor_referencia(tipo_inmueble, perfil_final)
        val_m2_final = val_base * factor_ajuste
        total_usd = val_m2_final * m2_total
        total_ars = total_usd * dolar

    st.markdown("---")
    
    # ALERTAS INTELIGENTES
    if es_premium and riesgo_activo:
        st.error(f"⚠️ **CASO COMPLEJO:** Zona Premium ({calle}) afectada por entorno inmediato ({nombre_r}). Se prioriza el riesgo sobre el valor de zona.")
    elif es_premium:
        st.markdown(f'<span class="premium-tag">🌟 ZONA PREMIUM DETECTADA</span>', unsafe_allow_html=True)
        st.caption("Ubicación en Corredor de Alto Valor o Barrio Cerrado.")
    elif riesgo_activo:
        st.error(f"🚨 **RIESGO DE ENTORNO:** A {dist_r:.0f}m de {nombre_r}.")

    # RESULTADOS NUMÉRICOS
    st.write("")
    c1, c2 = st.columns(2)
    c1.metric("Valor m² (USD)", f"USD {val_m2_final:,.0f}")
    c2.metric("Total Garantía (USD)", f"USD {total_usd:,.0f}")
    
    st.markdown(f"""
        <div style="background-color:#e3f2fd; padding:15px; border-radius:10px; margin-top:10px; text-align:center;">
            <small style="color:#555">VALOR TÉCNICO EN PESOS (BNA)</small>
            <h2 style="color:#1565c0; margin:0">$ {total_ars:,.0f}</h2>
        </div>
    """, unsafe_allow_html=True)
    
    with st.expander("Ver detalle de cálculo"):
        st.write(f"**Valor Base Matriz:** USD {val_base}")
        st.write(f"**Ajuste Aplicado:** {mensaje_ajuste}")
        st.write(f"**Distancia a Riesgo:** {dist_r:.0f} metros")

# --- 7. PIE DE PÁGINA ---
st.markdown("---")
st.caption("GERIE System v2.1 | Motor Heurístico de Zonas + Cartografía Satelital | Dólar BNA Live")
