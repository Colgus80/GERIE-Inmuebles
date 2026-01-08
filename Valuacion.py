import streamlit as st
import folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import st_folium

# Configuración GERIE
st.set_page_config(page_title="GERIE - Verificación de Garantías", layout="wide")

def motor_precision_uruguay(altura):
    """
    Función de anclaje específica para la calle Uruguay (Límite Beccar/Victoria).
    Asigna coordenadas exactas según la altura declarada.
    """
    try:
        h = int(altura)
        # Uruguay 1500-1600: Zona Misiones / Formosa
        if 1500 <= h <= 1650:
            return -34.4608, -58.5435
        # Uruguay 1000: Zona Acceso Tigre
        elif 900 <= h <= 1100:
            return -34.4635, -58.5520
        # Uruguay 2000: Zona Suipacha / Blanco Encalada
        elif 1900 <= h <= 2100:
            return -34.4580, -58.5360
    except:
        pass
    return None

def chequeo_renabap_bancario(lat, lon):
    # Focos de riesgo conocidos en la zona para política de garantías
    focos = [
        {"nombre": "La Cava", "lat": -34.4720, "lon": -58.5422},
        {"nombre": "San Jorge / Uruguay Norte", "lat": -34.4615, "lon": -58.5480},
        {"nombre": "Barrio Itatí", "lat": -34.4600, "lon": -58.5445}
    ]
    dist_min = 99999
    nombre = ""
    for f in focos:
        d = geodesic((lat, lon), (f['lat'], f['lon'])).meters
        if d < dist_min:
            dist_min = d
            nombre = f['nombre']
    return dist_min, nombre

# --- INTERFAZ ---
st.title("🏦 GERIE: Verificación de Colateral")

with st.sidebar:
    with st.form("verificador"):
        calle = st.text_input("Calle", "Uruguay")
        altura = st.text_input("Altura", "1565")
        loc = st.text_input("Localidad", "Beccar")
        prov = st.selectbox("Provincia", ["Buenos Aires", "CABA", "Interior"])
        m2 = st.number_input("Superficie m2", value=50)
        btn = st.form_submit_button("VALIDAR GARANTÍA")

if btn:
    # 1. Ejecutar Motor de Precisión para calles conflictivas
    lat, lon = None, None
    if "URUGUAY" in calle.upper():
        lat, lon = motor_precision_uruguay(altura)
    
    # 2. Si no es Uruguay o falló el motor, usar Geocodificador estándar
    if not lat:
        geo = Nominatim(user_agent="gerie_risk_pro_v13", timeout=10)
        ubicacion = geo.geocode(f"{calle} {altura}, {loc}, Argentina")
        if ubicacion:
            lat, lon = ubicacion.latitude, ubicacion.longitude

    if lat:
        dist_r, barrio_r = chequeo_renabap_bancario(lat, lon)
        
        # Tasación Bancaria Conservadora
        v_base = 1500 # Valor base GBA Norte
        factor_riesgo = 0.65 if dist_r < 500 else 1.0
        m2_final = v_base * factor_riesgo
        
        # Resultados
        if dist_r < 500:
            st.error(f"🚨 ALERTA DE RIESGO: Garantía próxima a {barrio_r} ({dist_r:.0f}m).")
        else:
            st.success("✅ Verificación exitosa: Sin afectación de entorno.")

        st.metric("VALOR ESTIMADO M2", f"USD {m2_final:,.0f}")
        st.metric("VALOR TOTAL GARANTÍA", f"USD {m2_final * m2:,.0f}")

        # Visualización dual para el analista
        col_m, col_s = st.columns(2)
        with col_m:
            m = folium.Map(location=[lat, lon], zoom_start=17)
            folium.Marker([lat, lon], tooltip="Propiedad Declarada").add_to(m)
            # El radio de 500m es ley para analistas de riesgo
            folium.Circle([lat, lon], radius=500, color="red", fill=True, opacity=0.1).add_to(m)
            st_folium(m, height=400, width=None)
        with col_s:
            st.markdown(f'<iframe width="100%" height="400" src="https://maps.google.com/maps?q={lat},{lon}&layer=c&cbll={lat},{lon}&output=svembed"></iframe>', unsafe_allow_html=True)
    else:
        st.error("No se pudo localizar la dirección. Verifique los datos.")
