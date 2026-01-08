import streamlit as st
import folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import st_folium

# Configuración GERIE - Verificación de Garantías
st.set_page_config(page_title="GERIE - Analista de Riesgo", layout="wide")

# --- 1. MEMORIA DE SESIÓN (Evita que la consulta desaparezca) ---
if 'tasacion_realizada' not in st.session_state:
    st.session_state.tasacion_realizada = False
if 'datos_propiedad' not in st.session_state:
    st.session_state.datos_propiedad = {}

# --- 2. MOTORES DE PRECISIÓN ---

def motor_precision_nacional(calle, altura, localidad):
    """Anclaje manual para zonas conflictivas (Uruguay 1500, etc.)"""
    c = calle.upper()
    h = int(altura) if altura.isdigit() else 0
    
    # Caso crítico: Uruguay entre Misiones y Formosa
    if "URUGUAY" in c and 1400 <= h <= 1700:
        return -34.4608, -58.5435
    return None

def analizar_riesgo_entorno(lat, lon):
    """Detección de asentamientos para política de garantías bancarias"""
    focos = [
        {"nombre": "La Cava", "lat": -34.4720, "lon": -58.5422},
        {"nombre": "Barrio Itatí / San Jorge", "lat": -34.4600, "lon": -58.5445}
    ]
    dist_min = 99999
    nombre_foco = ""
    for f in focos:
        d = geodesic((lat, lon), (f['lat'], f['lon'])).meters
        if d < dist_min:
            dist_min = d
            nombre_foco = f['nombre']
    return dist_min, nombre_foco

# --- 3. INTERFAZ DE USUARIO ---
st.title("🏦 GERIE: Verificación de Garantías")
st.markdown("---")

with st.sidebar:
    st.header("🔍 Datos del Colateral")
    with st.form("verificador_bancario"):
        calle = st.text_input("Calle", value="Uruguay")
        altura = st.text_input("Altura", value="1565")
        loc = st.text_input("Localidad", value="Beccar")
        tipo = st.selectbox("Tipo de Bien", ["Casa", "Departamento", "Local", "Oficina"])
        m2 = st.number_input("M2 Declarados", value=50)
        
        btn = st.form_submit_button("VALIDAR GARANTÍA")

if btn:
    # Intentar anclaje de precisión primero
    coords = motor_precision_nacional(calle, altura, loc)
    
    if not coords:
        geo = Nominatim(user_agent="gerie_bank_v14")
        ubicacion = geo.geocode(f"{calle} {altura}, {loc}, Argentina")
        if ubicacion:
            coords = (ubicacion.latitude, ubicacion.longitude)

    if coords:
        lat, lon = coords
        dist_r, barrio_r = analizar_riesgo_entorno(lat, lon)
        
        # Guardar en la sesión para que no desaparezca
        st.session_state.datos_propiedad = {
            "lat": lat, "lon": lon, "calle": calle, "altura": altura,
            "dist": dist_r, "barrio": barrio_r, "m2": m2, "tipo": tipo
        }
        st.session_state.tasacion_realizada = True
    else:
        st.error("No se pudo localizar la dirección.")

# --- 4. RENDERIZADO PERSISTENTE ---
if st.session_state.tasacion_realizada:
    d = st.session_state.data = st.session_state.datos_propiedad
    
    # Valuación Técnica (Valores conservadores para banco)
    base_m2 = 1600
    ajuste = 0.65 if d['dist'] < 500 else 1.0 # Castigo del 35% por riesgo
    m2_final = base_m2 * ajuste
    
    # Alertas de Política de Crédito
    if d['dist'] < 500:
        st.error(f"🚨 RIESGO DE COLATERAL: Cercanía a {d['barrio']} ({d['dist']:.0f}m)")
    else:
        st.success("✅ Garantía sin afectación de entorno detectada.")

    # Métricas Principales
    c1, c2, c3 = st.columns(3)
    c1.metric("M2 Valuado (USD)", f"USD {m2_final:,.0f}")
    c2.metric("Total Garantía (USD)", f"USD {m2_final * d['m2']:,.0f}")
    c3.metric("Ubicación", f"{d['calle']} {d['altura']}")

    # Paneles de Inspección
    col_mapa, col_foto = st.columns(2)
    with col_mapa:
        st.subheader("🗺️ Mapa de Ubicación")
        m = folium.Map(location=[d['lat'], d['lon']], zoom_start=17)
        folium.Marker([d['lat'], d['lon']], tooltip="Propiedad").add_to(m)
        folium.Circle([d['lat'], d['lon']], radius=500, color="red", fill=True, opacity=0.1).add_to(m)
        st_folium(m, height=450, width=None, key="mapa_estatico")
        
    with col_foto:
        st.subheader("📷 Fachada (Street View)")
        url_sv = f"https://maps.google.com/maps?q={d['lat']},{d['lon']}&layer=c&cbll={d['lat']},{d['lon']}&output=svembed"
        st.markdown(f'<iframe width="100%" height="450" src="{url_sv}" frameborder="0"></iframe>', unsafe_allow_html=True)
