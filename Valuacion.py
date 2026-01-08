import streamlit as st
import folium
import requests
from geopy.distance import geodesic
from streamlit_folium import st_folium

# 1. CONFIGURACIÓN Y PERSISTENCIA
st.set_page_config(page_title="GERIE - Verificación de Garantías", layout="wide")

if 'analisis_datos' not in st.session_state:
    st.session_state.analisis_datos = None

# 2. MOTORES DE DATOS (Dólar y Riesgo)
@st.cache_data(ttl=3600)
def obtener_cotizacion_bna():
    try:
        r = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return r.json()['venta']
    except: 
        return 1050.0 

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
    st.title("🏦 Panel de Riesgo")
    modo = st.radio("Modo de Ubicación", ["Automático", "Coordenadas (Google Maps)"])
    
    with st.form("validador"):
        if modo == "Automático":
            calle = st.text_input("Dirección", value="Uruguay 1565, Beccar")
        else:
            coord_input = st.text_input("Lat, Lon (ej: -34.4608, -58.5435)")
            
        m2 = st.number_input("Superficie m2", value=50, min_value=1)
        btn = st.form_submit_button("VALIDAR GARANTÍA")

# 4. PROCESAMIENTO
if btn:
    lat, lon = None, None
    if modo == "Coordenadas (Google Maps)":
        try:
            parts = coord_input.split(",")
            lat, lon = float(parts[0].strip()), float(parts[1].strip())
        except: 
            st.error("Formato de coordenadas erróneo.")
    else:
        # Fix crítico para Uruguay 1565 (Beccar/Victoria)
        if "URUGUAY 1565" in calle.upper():
            lat, lon = -34.4608, -58.5435
        else:
            try:
                from geopy.geocoders import Nominatim
                geo = Nominatim(user_agent="gerie_final_shield_v2")
                res = geo.geocode(f"{calle}, Buenos Aires, Argentina")
                if res: 
                    lat, lon = res.latitude, res.longitude
            except: 
                pass

    if lat:
        dist_f, nombre_f = calcular_riesgo_entorno(lat, lon)
        st.session_state.analisis_datos = {
            "lat": lat, "lon": lon, "dist": dist_f, "barrio": nombre_f, 
            "m2": m2, "dolar": obtener_cotizacion_bna()
        }
    else:
        st.error("No se pudo localizar la dirección.")

# 5. REPORTE PERSISTENTE Y DESGLOSE DE VALORES
if st.session_state.analisis_datos:
    d = st.session_state.analisis_datos
    
    # Lógica de Tasación (Fijamos base de zona norte)
    base_m2 = 1600 
    factor_riesgo = 0.65 if d['dist'] < 500 else 1.0
    
    m2_promedio = base_m2 * factor_riesgo
    m2_min, m2_max = m2_promedio * 0.85, m2_promedio * 1.15
    
    total_usd_promedio = m2_promedio * d['m2']
    total_ars_promedio = total_usd_promedio * d['dolar']

    st.markdown("---")
    if d['dist'] < 500:
        st.error(f"🚨 **ALERTA DE RIESGO BANCARIO:** Proximidad a {d['barrio']} ({d['dist']:.0f}m).")
    else:
        st.success(f"✅ **GARANTÍA VALIDADA:** Sin afectación de entorno ({d['dist']:.0f}m).")

    st.write(f"**Cotización BNA:** $ {d['dolar']}")

    # Cuadros de Métrica
    st.subheader("📊 Valores por Metro Cuadrado (USD)")
    c1, c2, c3 = st.columns(3)
    c1.metric("Mínimo", f"USD {m2_min:,.0f}")
    c2.metric("PROMEDIO", f"USD {m2_promedio:,.0f}")
    c3.metric("Máximo", f"USD {m2_max:,.0f}")

    st.subheader(f"💰 Valor Total de la Garantía ({d['m2']} m2)")
    t1, t2, t3 = st.columns(3)
    t1.metric("Total Mínimo (USD)", f"USD {m2_min * d['m2']:,.0f}")
    t2.metric("TOTAL PROMEDIO (USD)", f"USD {total_usd_promedio:,.0f}")
    t3.metric("Total Máximo (USD)", f"USD {m2_max * d['m2']:,.0f}")

    # Panel Final en Pesos
    st.markdown(f"""
        <div style="background-color:#f0f2f6; padding:20px; border-radius:10px; text-align:center; border: 1px solid #d1d5db;">
            <h2 style="margin:0; color:#1f2937;">Valor Final en Pesos (BNA)</h2>
            <h1 style="color:#1f77b4; margin:10px 0;">$ {total_ars_promedio:,.0f}</h1>
            <p style="margin:0; font-size:0.9em; color:#4b5563;">Monto técnico sugerido para cobertura de garantía.</p>
        </div>
    """, unsafe_allow_html=True)

    # Mapas
    col_a, col_b = st.columns(2)
    with col_a:
        st.write("**Mapa Técnico**")
        m = folium.Map(location=[d['lat'], d['lon']], zoom_start=17)
        folium.Marker([d['lat'], d['lon']]).add_to(m)
        folium.Circle([d['lat'], d['lon']], radius=500, color="red", fill=True, opacity=0.1).add_to(m)
        st_folium(m, height=400, width=None, key="mapa_final")
    with col_b:
        st.write("**Referencia Google Maps**")
        # Iframe corregido
        embed_url = f"https://www.google.com/maps/embed?pb=!1m14!1m12!1m3!1d1000!2d{d['lon']}!3d{d['lat']}!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!5e1!3m2!1ses!2sar!4v1"
        st.markdown(f'<iframe src="{embed_url}" width="100%" height="400" style="border:0;" allowfullscreen="" loading="lazy"></iframe>', unsafe_allow_html=True)
