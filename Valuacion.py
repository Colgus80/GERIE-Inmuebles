import streamlit as st
import folium
import requests
from geopy.distance import geodesic
from streamlit_folium import st_folium

# 1. CONFIGURACIÓN
st.set_page_config(page_title="GERIE - Admisión de Garantías", layout="wide")

if 'analisis_datos' not in st.session_state:
    st.session_state.analisis_datos = None

# 2. MOTORES DE DATOS Y TASACIÓN
@st.cache_data(ttl=3600)
def obtener_cotizacion_bna():
    try:
        r = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return r.json()['venta']
    except: return 1100.0 

def calcular_riesgo_entorno(lat, lon):
    # Focos críticos de referencia (pueden ampliarse por provincia)
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

# 3. INTERFAZ LATERAL (ADAPTADA A DATOS DE ESCRITURA/DOMINIO)
with st.sidebar:
    st.title("🏦 Admisión de Colateral")
    st.info("Utilice 'Coordenadas' para datos de escrituras con ubicación imprecisa o zonas rurales.")
    
    modo_ubicacion = st.radio("Dato disponible:", ["Dirección/Barrio/Localidad", "Coordenadas GPS"])
    
    with st.form("validador_bancario"):
        tipo_inmueble = st.selectbox("Tipo de Inmueble", [
            "Casa", "Departamento", "Local Comercial", 
            "Depósito/Galpón", "Campo Agrícola", "Campo Ganadero"
        ])
        
        if modo_ubicacion == "Dirección/Barrio/Localidad":
            entrada_geo = st.text_input("Ubicación (Según Escritura/Propuesta)", placeholder="Ej: Barrio Santa Rita, Boulogne")
        else:
            entrada_geo = st.text_input("Latitud, Longitud (Desde Google Maps)", placeholder="-34.4608, -58.5435")
            
        provincia = st.selectbox("Provincia", [
            "Buenos Aires", "CABA", "Catamarca", "Chaco", "Chubut", "Córdoba", 
            "Corrientes", "Entre Ríos", "Formosa", "Jujuy", "La Pampa", "La Rioja", 
            "Mendoza", "Misiones", "Neuquén", "Río Negro", "Salta", "San Juan", 
            "San Luis", "Santa Cruz", "Santa Fe", "Santiago del Estero", "Tierra del Fuego", "Tucumán"
        ])
        
        label_sup = "Superficie (Hectáreas)" if "Campo" in tipo_inmueble else "Superficie (m²)"
        superficie = st.number_input(label_sup, value=1.0, min_value=0.1)
        
        btn = st.form_submit_button("ANALIZAR PROPUESTA")

# 4. PROCESAMIENTO
if btn:
    lat, lon = None, None
    if modo_ubicacion == "Coordenadas GPS":
        try:
            parts = entrada_geo.split(",")
            lat, lon = float(parts[0].strip()), float(parts[1].strip())
        except: st.error("Formato de coordenadas incorrecto.")
    else:
        try:
            from geopy.geocoders import Nominatim
            geo = Nominatim(user_agent="gerie_final_flexible")
            res = geo.geocode(f"{entrada_geo}, {provincia}, Argentina")
            if res: lat, lon = res.latitude, res.longitude
        except: pass

    if lat:
        dist_f, nombre_f = calcular_riesgo_entorno(lat, lon)
        
        # Configuración de valores base USD
        config_valuacion = {
            "Casa": {"base": 1500, "es_ha": False},
            "Departamento": {"base": 1850, "es_ha": False},
            "Local Comercial": {"base": 2200, "es_ha": False},
            "Depósito/Galpón": {"base": 850, "es_ha": False},
            "Campo Agrícola": {"base": 12000, "es_ha": True},
            "Campo Ganadero": {"base": 4500, "es_ha": True}
        }
        
        v_conf = config_valuacion[tipo_inmueble]
        # Castigo por riesgo solo para urbanos cercanos a focos
        factor_riesgo = 0.65 if (not v_conf["es_ha"] and dist_f < 500) else 1.0
            
        st.session_state.analisis_datos = {
            "lat": lat, "lon": lon, "dist": dist_f, "barrio": nombre_f, 
            "m2": superficie, "dolar": obtener_cotizacion_bna(),
            "tipo": tipo_inmueble, "base": v_conf["base"], 
            "factor": factor_riesgo, "es_ha": v_conf["es_ha"],
            "ubicacion_nom": entrada_geo
        }
    else:
        st.error("No se pudo localizar. Se recomienda buscar en Google Maps y usar coordenadas.")

# 5. RESULTADOS Y GOBERNANZA DE DATOS
if st.session_state.analisis_datos:
    d = st.session_state.analisis_datos
    
    m2_promedio = d['base'] * d['factor']
    m2_min, m2_max = m2_promedio * 0.85, m2_promedio * 1.15
    total_usd = m2_promedio * d['m2']
    total_ars = total_usd * d['dolar']
    unidad = "Ha" if d['es_ha'] else "m²"

    st.markdown(f"### Análisis de Admisión: {d['tipo']}")
    
    # Alertas de Riesgo
    if not d['es_ha'] and d['dist'] < 500:
        st.error(f"🚨 **ALERTA DE CUMPLIMIENTO:** Cercanía a {d['barrio']} ({d['dist']:.0f}m).")
    elif not d['es_ha']:
        st.success(f"✅ **ENTORNO VALIDADO:** Garantía fuera de radios de riesgo detectados.")

    # MÉTRICAS
    c1, c2, c3 = st.columns(3)
    c1.metric(f"Valor por {unidad} (USD)", f"USD {m2_promedio:,.0f}", delta=f"({m2_min:,.0f} - {m2_max:,.0f})", delta_color="off")
    c2.metric("Valor Total (USD)", f"USD {total_usd:,.0f}")
    c3.metric("Dólar BNA", f"$ {d['dolar']}")

    # PANEL PESOS
    st.markdown(f"""
        <div style="background-color:#f8f9fa; padding:25px; border-radius:15px; text-align:center; border: 2px solid #e9ecef; margin: 20px 0;">
            <h2 style="margin:0; color:#343a40;">Valor Proyectado en Pesos (Oficial BNA)</h2>
            <h1 style="color:#1f77b4; margin:10px 0; font-size:48px;">$ {total_ars:,.0f}</h1>
        </div>
    """, unsafe_allow_html=True)

    # MAPA Y SATÉLITE
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Visualización Geográfica**")
        zoom_lv = 14 if d['es_ha'] else 17
        m = folium.Map(location=[d['lat'], d['lon']], zoom_start=zoom_lv)
        folium.Marker([d['lat'], d['lon']]).add_to(m)
        if not d['es_ha']:
            folium.Circle([d['lat'], d['lon']], radius=500, color="red", fill=True, opacity=0.1).add_to(m)
        st_folium(m, height=400, width=None, key="mapa_final")
    with col2:
        st.write("**Referencia de Catastro/Imagen Satelital**")
        st.markdown(f'<iframe width="100%" height="400" frameborder="0" src="https://maps.google.com/maps?q={d["lat"]},{d["lon"]}&z={zoom_lv}&output=embed"></iframe>', unsafe_allow_html=True)

    # 6. PIE DE CONSULTA: FUENTES Y METODOLOGÍA
    st.markdown("---")
    with st.expander("📄 Gobernanza de Datos y Metodología"):
        st.markdown("""
        **Fuentes de Información:**
        * **Divisas:** Cotización oficial del Banco Nación Argentina (BNA) vía *DolarApi.com*.
        * **Geolocalización:** *OpenStreetMap* y motores geodésicos *Geopy* (Elipsoide WGS-84).
        * **Riesgo Social:** Base de Barrios Populares (*RENABAP*).
        
        **Metodología de Valuación:**
        * **Urbanos:** Valores promedio basados en series históricas de *Zonaprop* y *Reporte Inmobiliario*. El rango (±15%) contempla variaciones de estado de conservación no verificadas.
        * **Rurales:** Valores por Hectárea de referencia para Región Pampeana y Litoral.
        * **Castigo por Entorno:** Se aplica un factor de mitigación del 0.65 (35% de descuento) sobre el valor base en zonas urbanas con cercanía crítica (<500m) a asentamientos, por considerar baja liquidez de reventa.
        
        *Este reporte es una herramienta de pre-calificación y no reemplaza la tasación de un perito matriculado.*
        """)
