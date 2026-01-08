import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from shapely.geometry import Point
from streamlit_folium import st_folium

# Configuración de nivel bancario
st.set_page_config(page_title="GERIE - Verificación de Garantías", layout="wide")

# --- 1. GESTIÓN DE PERSISTENCIA ---
if 'analisis' not in st.session_state:
    st.session_state.analisis = None

# --- 2. MOTOR DE PRECISIÓN DEPURADO ---
def geolocalizar_con_validacion(calle, altura, localidad, provincia):
    """
    Motor de búsqueda con validación cruzada para evitar 'saltos' de ubicación.
    """
    geo = Nominatim(user_agent="gerie_risk_pro_v16", timeout=15)
    
    # Intentamos búsqueda estructurada (más precisa para límites de partidos)
    intentos = [
        f"{calle} {altura}, {localidad}, {provincia}, Argentina",
        f"{calle} {altura}, {provincia}, Argentina",
        f"{calle} {altura}, Buenos Aires, Argentina"
    ]
    
    for query in intentos:
        try:
            loc = geo.geocode(query, addressdetails=True)
            if loc:
                # Validamos que no nos haya mandado a otra provincia por error
                addr = loc.raw.get('address', {})
                state = addr.get('state', '')
                if provincia.lower() in state.lower() or not state:
                    return loc
        except:
            continue
    return None

@st.cache_data
def buscar_riesgo_renabap(lat, lon):
    """Carga dinámica y filtrado por radio para cualquier punto del país"""
    url = "https://datosabiertos.desarrollosocial.gob.ar/dataset/0d50730b-1662-4217-9ef1-37018c1b359f/resource/828292d3-96b4-4b9e-99e5-b1030e466b0a/download/barrios-populares.json"
    try:
        gdf = gpd.read_file(url)
        punto = Point(lon, lat)
        # Filtro de proximidad (aprox 2km alrededor)
        caja = gdf.cx[lon-0.02:lon+0.02, lat-0.02:lat+0.02]
        if not caja.empty:
            # Calculamos distancia al borde del polígono más cercano
            # (Convertimos a grados a metros aproximadamente para rapidez)
            distancias = caja.distance(punto) * 111139 
            idx_min = distancias.idxmin()
            return distancias.min(), caja.loc[idx_min, 'nombre']
    except:
        pass
    return 99999, ""

# --- 3. INTERFAZ DE USUARIO ---
st.title("🏦 GERIE: Verificación de Garantías Inmobiliarias")
st.markdown("---")

with st.sidebar:
    st.header("📍 Ubicación a Verificar")
    with st.form("validador_bancario"):
        c = st.text_input("Calle", value="Uruguay")
        h = st.text_input("Altura", value="1565")
        l = st.text_input("Localidad", value="Beccar")
        p = st.selectbox("Provincia", ["Buenos Aires", "CABA", "Santa Fe", "Cordoba", "Mendoza"])
        m2 = st.number_input("M2 Totales", value=50)
        btn = st.form_submit_button("VALIDAR COLATERAL")

if btn:
    with st.spinner('Depurando localización...'):
        resultado = geolocalizar_con_validacion(c, h, l, p)
        if resultado:
            dist, barrio = buscar_riesgo_renabap(resultado.latitude, resultado.longitude)
            st.session_state.analisis = {
                "lat": resultado.latitude, "lon": resultado.longitude,
                "address": resultado.address, "dist": dist, "barrio": barrio, "m2": m2
            }
        else:
            st.error("⚠️ Error: No se pudo localizar la dirección con la precisión requerida.")

# --- 4. EXPOSICIÓN DE RESULTADOS (PERSISTENTE) ---
if st.session_state.analisis:
    res = st.session_state.analisis
    
    # Lógica de Política Bancaria
    es_zona_riesgo = res['dist'] < 500
    color_alerta = "red" if es_zona_riesgo else "green"
    
    if es_zona_riesgo:
        st.error(f"🚨 ALERTA DE RIESGO: Garantía afectada por proximidad a '{res['barrio']}' ({res['dist']:.0f}m)")
    else:
        st.success(f"✅ Entorno Validado: Sin afectación crítica detectada ({res['dist']:.0f}m)")

    # Valuación Técnica Estimada
    v_base = 1550 # Valor referencial
    ajuste = 0.65 if es_zona_riesgo else 1.0
    v_m2 = v_base * ajuste
    
    col1, col2, col3 = st.columns(3)
    col1.metric("M2 Valuado (USD)", f"USD {v_m2:,.0f}")
    col2.metric("Valor Total Garantía", f"USD {v_m2 * res['m2']:,.0f}")
    col3.metric("LTV Estimado", "75%", help="Ratio préstamo/valor sugerido")

    # Visualización de Inspección
    t1, t2 = st.tabs(["🗺️ Mapa de Verificación", "📷 Registro Street View"])
    with t1:
        m = folium.Map(location=[res['lat'], res['lon']], zoom_start=17)
        folium.Marker([res['lat'], res['lon']], popup=res['address']).add_to(m)
        # Radio de política bancaria (500m)
        folium.Circle([res['lat'], res['lon']], radius=500, color="red", fill=True, opacity=0.1).add_to(m)
        st_folium(m, height=450, width=None, key="mapa_riesgo")
    with t2:
        url_sv = f"https://maps.google.com/maps?q={res['lat']},{res['lon']}&layer=c&cbll={res['lat']},{res['lon']}&output=svembed"
        st.markdown(f'<iframe width="100%" height="450" src="{url_sv}" frameborder="0"></iframe>', unsafe_allow_html=True)
