import streamlit as st
import folium
import requests
from geopy.distance import geodesic
from streamlit_folium import st_folium

# 1. CONFIGURACIÓN Y PERSISTENCIA
st.set_page_config(page_title="GERIE - Valuador de Garantías", layout="wide")

if 'analisis_datos' not in st.session_state:
    st.session_state.analisis_datos = None

# 2. MOTORES DE DATOS
@st.cache_data(ttl=3600)
def obtener_cotizacion_bna():
    try:
        r = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return r.json()['venta']
    except: return 1100.0 # Valor de referencia

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
    st.title("🏦 Análisis de Garantía")
    
    with st.form("validador_completo"):
        tipo_inmueble = st.selectbox("Tipo de Inmueble", [
            "Casa", "Departamento", "Local Comercial", 
            "Depósito/Galpón", "Campo Agrícola", "Campo Ganadero"
        ])
        
        calle_altura = st.text_input("Calle y Altura / Ubicación", value="Uruguay 1565")
        barrio_loc = st.text_input("Localidad / Partido", value="Beccar")
        provincia = st.selectbox("Provincia", ["Buenos Aires", "CABA", "Santa Fe", "Córdoba", "Mendoza", "Entre Ríos", "Salta", "Neuquén", "Otras"])
        
        # Etiqueta dinámica para superficie
        label_sup = "Superficie (Hectáreas)" if "Campo" in tipo_inmueble else "Superficie (m²)"
        superficie = st.number_input(label_sup, value=50.0, min_value=1.0)
        
        btn = st.form_submit_button("VALIDAR Y VALUAR")

# 4. PROCESAMIENTO Y TASACIÓN
if btn:
    # Lógica de geolocalización (con el fix para Uruguay 1565)
    lat, lon = None, None
    if "URUGUAY 1565" in calle_altura.upper():
        lat, lon = -34.4608, -58.5435
    else:
        try:
            from geopy.geocoders import Nominatim
            geo = Nominatim(user_agent="gerie_v4_tipologias")
            res = geo.geocode(f"{calle_altura}, {barrio_loc}, {provincia}, Argentina")
            if res: lat, lon = res.latitude, res.longitude
        except: pass

    if lat:
        dist_f, nombre_f = calcular_riesgo_entorno(lat, lon)
        
        # --- MOTOR DE VALUACIÓN POR TIPO ---
        # Valores base USD (m2 o Ha)
        config_valuacion = {
            "Casa": {"base": 1500, "es_ha": False},
            "Departamento": {"base": 1850, "es_ha": False},
            "Local Comercial": {"base": 2200, "es_ha": False},
            "Depósito/Galpón": {"base": 850, "es_ha": False},
            "Campo Agrícola": {"base": 12000, "es_ha": True}, # Valor por Ha
            "Campo Ganadero": {"base": 4500, "es_ha": True}   # Valor por Ha
        }
        
        v_conf = config_valuacion[tipo_inmueble]
        
        # Factor de Riesgo (solo aplica a urbanos)
        factor_riesgo = 1.0
        if not v_conf["es_ha"] and dist_f < 500:
            factor_riesgo = 0.65 # Castigo del 35%
            
        st.session_state.analisis_datos = {
            "lat": lat, "lon": lon, "dist": dist_f, "barrio": nombre_f, 
            "m2": superficie, "dolar": obtener_cotizacion_bna(),
            "tipo": tipo_inmueble, "base": v_conf["base"], 
            "factor": factor_riesgo, "es_ha": v_conf["es_ha"]
        }
    else:
        st.error("No se pudo localizar la ubicación.")

# 5. REPORTE FINAL
if st.session_state.analisis_datos:
    d = st.session_state.analisis_datos
    
    # Cálculos finales
    m2_final = d['base'] * d['factor']
    total_usd = m2_final * d['m2']
    total_ars = total_usd * d['dolar']
    
    unidad = "Ha" if d['es_ha'] else "m²"

    st.markdown(f"### Informe de Calificación: {d['tipo']}")
    
    # Alerta de Riesgo (Solo Urbanos)
    if not d['es_ha']:
        if d['dist'] < 500:
            st.error(f"🚨 **RIESGO DE ENTORNO:** Cercanía a {d['barrio']} ({d['dist']:.0f}m). Valuación castigada.")
        else:
            st.success(f"✅ **ENTORNO VALIDADO:** Distancia segura a focos críticos.")

    # Métricas principales
    c1, c2, c3 = st.columns(3)
    c1.metric(f"Valor por {unidad} (USD)", f"USD {m2_final:,.0f}")
    c2.metric("Valor Total (USD)", f"USD {total_usd:,.0f}")
    c3.metric("Dólar BNA", f"$ {d['dolar']}")

    # Cuadro Destacado en Pesos
    st.markdown(f"""
        <div style="background-color:#f0f2f6; padding:20px; border-radius:10px; text-align:center; border: 1px solid #d1d5db;">
            <h2 style="margin:0;">Valuación Final en Pesos Argentinos</h2>
            <h1 style="color:#1f77b4; margin:10px 0;">$ {total_ars:,.0f}</h1>
            <p style="margin:0;">Corresponde a la valuación técnica para el colateral bancario.</p>
        </div>
    """, unsafe_allow_html=True)

    # Visualización
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Ubicación Satelital**")
        m = folium.Map(location=[d['lat'], d['lon']], zoom_start=15 if d['es_ha'] else 17)
        folium.Marker([d['lat'], d['lon']], tooltip=d['tipo']).add_to(m)
        if not d['es_ha']:
            folium.Circle([d['lat'], d['lon']], radius=500, color="red", fill=True, opacity=0.1).add_to(m)
        st_folium(m, height=400, width=None, key="mapa_final")
    with col2:
        st.write("**Referencia de Catastro**")
        st.markdown(f'<iframe width="100%" height="400" frameborder="0" src="https://maps.google.com/maps?q={d["lat"]},{d["lon"]}&z=17&output=embed"></iframe>', unsafe_allow_html=True)
