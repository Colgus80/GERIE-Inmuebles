import streamlit as st
import folium
from geopy.distance import geodesic
from streamlit_folium import st_folium
import requests

# 1. BLINDAJE DE SESIÓN
st.set_page_config(page_title="GERIE - Verificación de Garantías", layout="wide")

if 'analisis_datos' not in st.session_state:
    st.session_state.analisis_datos = None

# 2. FUNCIONES DE CÁLCULO
def calcular_riesgo_entorno(lat, lon):
    # Coordenadas exactas de focos de riesgo conocidos
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

# 3. INTERFAZ DE ENTRADA
with st.sidebar:
    st.title("🏦 Verificador de Colateral")
    st.info("Si la búsqueda automática falla, use el modo manual para asegurar precisión bancaria.")
    
    modo = st.radio("Modo de Ubicación", ["Búsqueda Automática", "Coordenadas Exactas (Google Maps)"])
    
    with st.form("validador"):
        if modo == "Búsqueda Automática":
            calle = st.text_input("Calle y Altura", value="Uruguay 1565")
            loc = st.text_input("Localidad", value="Beccar")
        else:
            coord_input = st.text_input("Pegue Coordenadas (Lat, Lon)", placeholder="-34.4608, -58.5435")
            calle = "Ubicación Manual"
            loc = "Coordenadas"
            
        m2 = st.number_input("Superficie m2", value=50)
        btn = st.form_submit_button("EJECUTAR VALIDACIÓN")

# 4. PROCESAMIENTO
if btn:
    lat, lon = None, None
    
    if modo == "Coordenadas Exactas (Google Maps)":
        try:
            lat_str, lon_str = coord_input.split(",")
            lat, lon = float(lat_str.strip()), float(lon_str.strip())
        except:
            st.error("Formato de coordenadas inválido. Use: -34.4608, -58.5435")
    else:
        # Fallback de búsqueda automática
        try:
            from geopy.geocoders import Nominatim
            geo = Nominatim(user_agent="gerie_bank_final")
            res = geo.geocode(f"{calle}, {loc}, Buenos Aires, Argentina")
            if res:
                lat, lon = res.latitude, res.longitude
        except: pass

    if lat:
        dist_f, nombre_f = calcular_riesgo_entorno(lat, lon)
        st.session_state.analisis_datos = {
            "lat": lat, "lon": lon, "dist": dist_f, "barrio": nombre_f, "m2": m2
        }
    else:
        st.error("No se pudo localizar la propiedad.")

# 5. REPORTE PERSISTENTE
if st.session_state.analisis_datos:
    d = st.session_state.analisis_datos
    
    # Lógica de Política Bancaria
    es_riesgo = d['dist'] < 500
    ajuste = 0.65 if es_riesgo else 1.0
    val_m2 = 1600 * ajuste
    
    st.markdown("---")
    if es_riesgo:
        st.error(f"🚨 ALERTA BANCARIA: Proximidad a {d['barrio']} ({d['dist']:.0f}m)")
    else:
        st.success(f"✅ GARANTÍA VALIDADA: Sin afectación detectada ({d['dist']:.0f}m)")

    c1, c2, c3 = st.columns(3)
    c1.metric("M2 Valuado", f"USD {val_m2:,.0f}")
    c2.metric("Valor Total", f"USD {val_m2 * d['m2']:,.0f}")
    c3.metric("Ubicación GPS", f"{d['lat']:.4f}, {d['lon']:.4f}")

    # Visualización
    col_a, col_b = st.columns(2)
    with col_a:
        m = folium.Map(location=[d['lat'], d['lon']], zoom_start=18)
        folium.Marker([d['lat'], d['lon']]).add_to(m)
        folium.Circle([d['lat'], d['lon']], radius=500, color="red", fill=True, opacity=0.1).add_to(m)
        st_folium(m, height=400, width=None, key="mapa_final")
    with col_b:
        sv_url = f"https://www.google.com/maps/embed/v1/streetview?key=TU_API_KEY&location={d['lat']},{d['lon']}"
        # Usamos un iframe directo de Google Maps para evitar errores de carga
        st.markdown(f'<iframe width="100%" height="400" src="https://maps.google.com/maps?q={d["lat"]},{d["lon"]}&z=18&output=embed"></iframe>', unsafe_allow_html=True)
