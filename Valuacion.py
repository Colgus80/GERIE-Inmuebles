import streamlit as st
import folium
import requests
import pandas as pd
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium

# --- 1. CONFIGURACIÓN DEL SISTEMA FEDERAL ---
st.set_page_config(page_title="GERIE FEDERAL - Valuador Nacional", layout="wide")

# Estilos CSS para reporte profesional
st.markdown("""
    <style>
    .big-font {font-size:24px !important; font-weight: bold;}
    .success-box {padding: 15px; background-color: #d4edda; border-left: 5px solid #28a745; border-radius: 5px;}
    .warning-box {padding: 15px; background-color: #fff3cd; border-left: 5px solid #ffc107; border-radius: 5px;}
    .danger-box {padding: 15px; background-color: #f8d7da; border-left: 5px solid #dc3545; border-radius: 5px;}
    </style>
""", unsafe_allow_html=True)

# Inicialización de Estado
if 'coords' not in st.session_state:
    st.session_state.coords = [-34.6037, -58.3816] # Obelisco (Centro del país simbólico)
if 'zoom' not in st.session_state:
    st.session_state.zoom = 5
if 'perfil_sugerido' not in st.session_state:
    st.session_state.perfil_sugerido = "Media"

# --- 2. MOTORES DE INTELIGENCIA DE DATOS ---

@st.cache_data(ttl=3600)
def get_dolar_bna():
    try:
        r = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return r.json()['venta']
    except: return 1150.0

def detectar_perfil_universal(direccion, localidad):
    """
    Motor Heurístico Universal: Detecta patrones de alto valor 
    aplicables a cualquier ciudad de Argentina.
    """
    txt = (direccion + " " + localidad).upper()
    
    # Patrones PREMIUM (Barrios Cerrados / Lujo)
    k_premium = ["COUNTRY", "GOLF", "CLUB DE CAMPO", "ESTANCIA", "BARRIO CERRADO", 
                 "NORDELTA", "PUERTO MADERO", "LOMAS DE", "LAS LOMAS", "DALVIAN", "YACHT"]
    
    # Patrones ALTA (Zonas consolidadas / Avenidas principales)
    k_alta = ["LIBERTADOR", "BOULEVARD", "AVENIDA", "COSTANERA", "PLAZA PRINCIPAL", 
              "CENTRO CIVICO", "PEATONAL", "RESIDENCIAL", "JARDINES"]
    
    if any(x in txt for x in k_premium): return "Premium"
    if any(x in txt for x in k_alta): return "Alta"
    
    return "Media" # Default conservador

def get_indice_provincial(provincia):
    """
    Ajusta el valor del m2 según la realidad económica de la región.
    Base 1.0 = CABA/GBA Norte.
    """
    indices = {
        "CABA": 1.0, "Buenos Aires": 0.85, # GBA Promedio
        "Córdoba": 0.80, "Santa Fe": 0.80, "Mendoza": 0.75,
        "Neuquén": 0.90, "Río Negro": 0.85, # Influencia Vaca Muerta / Turismo
        "Tierra del Fuego": 0.85, "Chubut": 0.70, "Santa Cruz": 0.65,
        "Salta": 0.65, "Tucumán": 0.60, "Jujuy": 0.55,
        "Entre Ríos": 0.60, "Corrientes": 0.55, "Misiones": 0.55,
        "San Juan": 0.55, "San Luis": 0.60, "La Rioja": 0.50, "Catamarca": 0.50,
        "Chaco": 0.45, "Formosa": 0.45, "Santiago del Estero": 0.45, "La Pampa": 0.50
    }
    return indices.get(provincia, 0.60) # Default resto del país

def calcular_valor_m2(tipo, perfil, provincia):
    # 1. Valor Base (Referencia CABA/GBA Norte)
    base_usd = {
        "Casa": {"Premium": 2200, "Alta": 1600, "Media": 1100, "Baja": 700},
        "Departamento": {"Premium": 3000, "Alta": 2300, "Media": 1700, "Baja": 1000},
        "Local Comercial": {"Premium": 3500, "Alta": 2500, "Media": 1500, "Baja": 800},
        "Depósito/Galpón": {"Premium": 1000, "Alta": 800, "Media": 500, "Baja": 300}
    }
    valor_base = base_usd.get(tipo, {}).get(perfil, 1000)
    
    # 2. Factor Provincial
    factor_prov = get_indice_provincial(provincia)
    
    # 3. Valor Ajustado Regional
    return valor_base * factor_prov

def analizar_riesgo_renabap_mock(lat, lon):
    # SIMULACIÓN: En producción, esto consulta la capa WMS del RENABAP
    # Aquí mantenemos los focos de ejemplo para Buenos Aires como prueba de concepto
    focos = [
        {"nombre": "Villa 31", "lat": -34.5846, "lon": -58.3794}, 
        {"nombre": "La Cava", "lat": -34.4720, "lon": -58.5422},
        {"nombre": "Villa Itatí", "lat": -34.7088, "lon": -58.3079}
    ]
    dist_min = 99999
    nombre = ""
    for f in focos:
        d = geodesic((lat, lon), (f['lat'], f['lon'])).meters
        if d < dist_min:
            dist_min = d
            nombre = f['nombre']
    return dist_min, nombre

# --- 3. INTERFAZ DE USUARIO ---
with st.sidebar:
    st.header("🇦🇷 GERIE FEDERAL")
    st.caption("Sistema de Valuación Nacional")
    
    with st.form("carga_federal"):
        tipo_inmueble = st.selectbox("Tipo de Inmueble", ["Casa", "Departamento", "Local Comercial", "Depósito/Galpón"])
        
        calle = st.text_input("Dirección", placeholder="Ej: Av. San Martín 500")
        localidad = st.text_input("Localidad", placeholder="Ej: Resistencia")
        provincia = st.selectbox("Provincia", [
            "Buenos Aires", "CABA", "Catamarca", "Chaco", "Chubut", "Córdoba", 
            "Corrientes", "Entre Ríos", "Formosa", "Jujuy", "La Pampa", "La Rioja", 
            "Mendoza", "Misiones", "Neuquén", "Río Negro", "Salta", "San Juan", 
            "San Luis", "Santa Cruz", "Santa Fe", "Santiago del Estero", "Tierra del Fuego", "Tucumán"
        ])
        
        m2 = st.number_input("Superficie (m²)", value=100.0)
        
        btn_buscar = st.form_submit_button("UBICAR Y VALUAR")

# --- 4. LÓGICA DE GEOLOCALIZACIÓN HÍBRIDA ---
if btn_buscar:
    # A. Detección de Perfil
    perfil = detectar_perfil_universal(calle, localidad)
    st.session_state.perfil_sugerido = perfil
    
    # B. Búsqueda Geográfica
    try:
        geo = Nominatim(user_agent="gerie_federal_v20")
        query = f"{calle}, {localidad}, {provincia}, Argentina"
        loc = geo.geocode(query, timeout=10)
        
        if loc:
            st.session_state.coords = [loc.latitude, loc.longitude]
            st.session_state.zoom = 16
        else:
            st.warning(f"Altura exacta no encontrada. Centrando en {localidad}.")
            loc_gen = geo.geocode(f"{localidad}, {provincia}, Argentina")
            if loc_gen:
                st.session_state.coords = [loc_gen.latitude, loc_gen.longitude]
                st.session_state.zoom = 14
    except:
        st.error("Error de conexión. Verifique su internet.")

# --- 5. VISUALIZACIÓN Y AJUSTE MANUAL ---
c_map, c_data = st.columns([1.5, 1])

with c_map:
    st.subheader("1. Confirmación de Ubicación")
    st.info("💡 Hacé clic en el mapa para corregir la posición exacta (esencial para evitar errores de buscador).")
    
    m = folium.Map(location=st.session_state.coords, zoom_start=st.session_state.zoom)
    
    # CAPA SATELITAL (Clave para verificar entorno visualmente)
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google',
        name='Google Satélite',
        overlay=False
    ).add_to(m)
    
    folium.Marker(st.session_state.coords, icon=folium.Icon(color="red", icon="home")).add_to(m)
    
    # Salida del mapa interactivo
    map_data = st_folium(m, height=500, width=None)

# Recalcular si hay clic
if map_data['last_clicked']:
    st.session_state.coords = [map_data['last_clicked']['lat'], map_data['last_clicked']['lng']]

# --- 6. CÁLCULOS FINALES ---
lat_f, lon_f = st.session_state.coords
dist_riesgo, nombre_riesgo = analizar_riesgo_renabap_mock(lat_f, lon_f)
dolar = get_dolar_bna()

# Selección Final de Perfil (Con Manual Override)
with c_data:
    st.subheader("2. Análisis de Valor")
    
    # Selector deslizante con el valor sugerido por el sistema
    perfil_final = st.select_slider(
        "Categoría de la Zona (Detectada/Ajustable)",
        options=["Baja", "Media", "Alta", "Premium"],
        value=st.session_state.perfil_sugerido,
        key="slider_perfil"
    )

    # Cálculo Matemático
    val_m2_regional = calcular_valor_m2(tipo_inmueble, perfil_final, provincia)
    
    # Castigo por Riesgo (Si aplica)
    factor_riesgo = 1.0
    if dist_riesgo < 500:
        factor_riesgo = 0.65
        st.markdown(f'<div class="danger-box">🚨 <b>RIESGO DETECTADO:</b> Proximidad a {nombre_riesgo} ({dist_riesgo:.0f}m).<br>Se aplica castigo del 35%.</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="success-box">✅ <b>ENTORNO OK:</b> Sin focos de riesgo inmediatos detectados.</div>', unsafe_allow_html=True)

    val_m2_final = val_m2_regional * factor_riesgo
    total_usd = val_m2_final * m2
    total_ars = total_usd * dolar
    
    st.divider()
    
    # RESULTADOS
    c1, c2 = st.columns(2)
    c1.metric("Valor m² (Ajustado)", f"USD {val_m2_final:,.0f}")
    c2.metric("Valor Total (USD)", f"USD {total_usd:,.0f}")
    
    st.markdown(f"""
        <div style="background-color:#e1f5fe; padding:15px; border-radius:10px; text-align:center; margin-top:15px;">
            <small style="color:#0277bd; font-weight:bold;">VALUACIÓN TÉCNICA EN PESOS (BNA)</small>
            <h1 style="color:#01579b; margin:0;">$ {total_ars:,.0f}</h1>
        </div>
    """, unsafe_allow_html=True)

    with st.expander("Ver desglose del cálculo"):
        indice_prov = get_indice_provincial(provincia)
        st.write(f"• **Base CABA ({perfil_final}):** USD {calcular_valor_m2(tipo_inmueble, perfil_final, 'CABA'):.0f}")
        st.write(f"• **Ajuste Provincial ({provincia}):** {indice_prov*100:.0f}%")
        st.write(f"• **Valor Regional:** USD {val_m2_regional:.0f}")
        st.write(f"• **Castigo Riesgo:** {(1-factor_riesgo)*100:.0f}%")
