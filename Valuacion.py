import streamlit as st
import folium
import requests
import webbrowser
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="GERIE MARKET - Valuador con Referencias", layout="wide")

if 'coords' not in st.session_state:
    st.session_state.coords = [-34.6037, -58.3816]
if 'zoom' not in st.session_state:
    st.session_state.zoom = 13
if 'valor_manual_m2' not in st.session_state:
    st.session_state.valor_manual_m2 = 0.0

# --- 2. MOTORES DE DATOS ---

@st.cache_data(ttl=3600)
def get_dolar_bna():
    try:
        r = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return r.json()['venta']
    except: return 1150.0

def generar_links_mercado(tipo, barrio, provincia):
    """
    Genera URLs dinámicas para buscar comparables en tiempo real
    sin violar políticas de scraping.
    """
    # Normalización para URLs
    b_url = barrio.lower().replace(" ", "-")
    p_url = provincia.lower().replace(" ", "-")
    
    # Mapeo de tipos para Zonaprop/Argenprop
    mapa_tipo_zp = {
        "Casa": "casas", "Departamento": "departamentos", 
        "Local Comercial": "locales-comerciales", "Depósito/Galpón": "galpones"
    }
    t_zp = mapa_tipo_zp.get(tipo, "propiedades")
    
    # Links construidos
    link_zp = f"https://www.zonaprop.com.ar/{t_zp}-venta-{b_url}.html"
    link_ap = f"https://www.argenprop.com/{t_zp[:-1]}-en-venta-en-{b_url}"
    link_ml = f"https://inmuebles.mercadolibre.com.ar/venta/{b_url}/{t_zp}"
    
    return link_zp, link_ap, link_ml

def get_valor_tabulado(tipo, provincia, calidad):
    """
    Matriz de valores REFERENCIALES (Base Reporte Inmobiliario / Zonaprop Index 2025).
    Sirve como punto de partida antes del ajuste manual.
    """
    # Base CABA/GBA Norte (USD/m2)
    base = {
        "Casa": {"Premium": 2100, "Alta": 1600, "Media": 1100, "Baja": 750},
        "Departamento": {"Premium": 2900, "Alta": 2300, "Media": 1750, "Baja": 1100},
        "Local Comercial": {"Premium": 3200, "Alta": 2200, "Media": 1400, "Baja": 800},
        "Depósito/Galpón": {"Premium": 1000, "Alta": 800, "Media": 550, "Baja": 350}
    }
    
    # Factor Provincial (Ajuste Regional)
    indices = {
        "CABA": 1.0, "Buenos Aires": 0.85, "Córdoba": 0.80, "Santa Fe": 0.80,
        "Mendoza": 0.75, "Neuquén": 0.95, "Río Negro": 0.85, "Salta": 0.65,
        "Tucumán": 0.60, "Chaco": 0.50, "Misiones": 0.55
    }
    
    idx_prov = indices.get(provincia, 0.60)
    valor_base = base.get(tipo, {}).get(calidad, 1000)
    
    return valor_base * idx_prov

# --- 3. INTERFAZ DE CARGA ---
with st.sidebar:
    st.header("🔎 Investigación de Mercado")
    
    with st.form("datos_inmueble"):
        tipo = st.selectbox("Tipo", ["Casa", "Departamento", "Local Comercial", "Depósito/Galpón"])
        direccion = st.text_input("Dirección", value="Av. Libertador 2400")
        localidad = st.text_input("Barrio/Localidad", value="Olivos")
        provincia = st.selectbox("Provincia", ["Buenos Aires", "CABA", "Córdoba", "Santa Fe", "Mendoza", "Neuquén", "Salta", "Resto del País"])
        m2 = st.number_input("Superficie (m²)", value=80.0)
        
        # Calidad Percibida (Ajuste inicial)
        calidad = st.select_slider("Perfil Zona", options=["Baja", "Media", "Alta", "Premium"], value="Alta")
        
        btn_analizar = st.form_submit_button("1. ANALIZAR ZONA")

# --- 4. LÓGICA DE MAPA Y VALUACIÓN ---
if btn_analizar:
    try:
        geo = Nominatim(user_agent="gerie_market_v1")
        loc = geo.geocode(f"{direccion}, {localidad}, {provincia}, Argentina")
        if loc:
            st.session_state.coords = [loc.latitude, loc.longitude]
            st.session_state.zoom = 16
        else:
            st.warning("Dirección aprox. (Centro de localidad)")
            loc_gen = geo.geocode(f"{localidad}, {provincia}, Argentina")
            if loc_gen:
                st.session_state.coords = [loc_gen.latitude, loc_gen.longitude]
    except: pass
    
    # Reseteamos valor manual al cambiar búsqueda
    st.session_state.valor_manual_m2 = 0.0

# --- 5. VISUALIZACIÓN ---
c_izq, c_der = st.columns([1, 1])

with c_izq:
    st.subheader("Mapa de Ubicación")
    m = folium.Map(location=st.session_state.coords, zoom_start=st.session_state.zoom)
    folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google', name='Satélite').add_to(m)
    folium.Marker(st.session_state.coords, icon=folium.Icon(color="red")).add_to(m)
    st_folium(m, height=400)
    
    # --- MÓDULO DE INVESTIGACIÓN DE MERCADO ---
    st.info("👇 **Buscar Comparables Reales:** Hacé clic para ver precios reales en la zona.")
    l_zp, l_ap, l_ml = generar_links_mercado(tipo, localidad, provincia)
    
    col_b1, col_b2, col_b3 = st.columns(3)
    with col_b1: st.link_button("Zonaprop", l_zp)
    with col_b2: st.link_button("Argenprop", l_ap)
    with col_b3: st.link_button("MercadoLibre", l_ml)

with c_der:
    st.subheader("Valuación Técnica")
    
    # 1. Valor Tabulado (Algoritmo)
    val_algoritmo = get_valor_tabulado(tipo, provincia, calidad)
    
    # 2. Ajuste por Comparables (Human in the loop)
    st.markdown("---")
    st.write("**¿Encontraste un comparable mejor?**")
    use_manual = st.checkbox("Ajustar con valor de mercado observado")
    
    val_final_m2 = val_algoritmo
    
    if use_manual:
        precio_testigo = st.number_input("Precio de propiedad similar vista (USD)", value=100000.0)
        m2_testigo = st.number_input("m² de la propiedad similar", value=m2)
        if m2_testigo > 0:
            val_mercado_real = precio_testigo / m2_testigo
            st.caption(f"El mercado indica: USD {val_mercado_real:.0f}/m²")
            # Ponderación: 70% Mercado Real / 30% Algoritmo (Para suavizar desvíos)
            val_final_m2 = (val_mercado_real * 0.7) + (val_algoritmo * 0.3)
    
    # Cálculos Finales
    total_usd = val_final_m2 * m2
    dolar = get_dolar_bna()
    total_ars = total_usd * dolar
    
    st.divider()
    c1, c2 = st.columns(2)
    c1.metric("Valor m² Final", f"USD {val_final_m2:,.0f}")
    c2.metric("Total Garantía", f"USD {total_usd:,.0f}")
    
    st.markdown(f"""
        <div style="background-color:#d1e7dd; padding:15px; border-radius:10px; text-align:center;">
            <h2 style="color:#0f5132; margin:0">$ {total_ars:,.0f}</h2>
            <small>Valor en Pesos (BNA)</small>
        </div>
    """, unsafe_allow_html=True)
    
    if use_manual:
        st.caption("✅ Valuación calibrada con datos de mercado en tiempo real.")
    else:
        st.caption("⚠️ Valuación estimada por algoritmo. Se sugiere verificar comparables.")
