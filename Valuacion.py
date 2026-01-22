import streamlit as st
import folium
import requests
import pandas as pd
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium

# --- 1. CONFIGURACIÓN Y BLINDAJE DE MEMORIA ---
st.set_page_config(page_title="GERIE - Valuador Estable", layout="wide")

# Inicialización de la "Caja Fuerte" (Session State)
# Si no existen estas variables, las creamos vacías. Si existen, NO SE TOCAN.
if 'datos_valuacion' not in st.session_state:
    st.session_state.datos_valuacion = None  # Aquí guardaremos el informe
if 'coords' not in st.session_state:
    st.session_state.coords = [-34.6037, -58.3816]
if 'zoom' not in st.session_state:
    st.session_state.zoom = 12

# Estilos visuales
st.markdown("""
    <style>
    .result-card {background-color: #e8f4f8; padding: 20px; border-radius: 10px; border-left: 6px solid #007bff;}
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTORES Y MATRICES (Valores Fijos) ---
MATRIZ_BASE_USD_M2 = {
    "Casa": {"Premium": 2100, "Muy Bueno": 1500, "Bueno/Estándar": 1150, "A Refaccionar": 800},
    "Departamento": {"Premium": 2800, "Muy Bueno": 2200, "Bueno/Estándar": 1700, "A Refaccionar": 1200},
    "Local Comercial": {"Premium": 3000, "Muy Bueno": 2000, "Bueno/Estándar": 1400, "A Refaccionar": 900},
    "Depósito/Galpón": {"Premium": 1000, "Muy Bueno": 800, "Bueno/Estándar": 600, "A Refaccionar": 400}
}

INDICE_PROVINCIA = {
    "CABA": 1.10, "Buenos Aires": 1.00, "Córdoba": 0.90, "Santa Fe": 0.90, 
    "Mendoza": 0.85, "Neuquén": 1.05, "Río Negro": 0.90, "Resto del País": 0.75
}

@st.cache_data(ttl=3600)
def get_dolar_bna():
    try:
        r = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return r.json()['venta']
    except: return 1150.0

# --- 3. INTERFAZ DE CARGA (SIDEBAR) ---
with st.sidebar:
    st.header("📝 Datos de Tasación")
    
    with st.form("form_blindado"):
        calle = st.text_input("Dirección", value="Gervasio Posadas 1538")
        localidad = st.text_input("Localidad", value="Beccar")
        provincia = st.selectbox("Provincia", list(INDICE_PROVINCIA.keys()))
        
        st.divider()
        tipo = st.selectbox("Inmueble", list(MATRIZ_BASE_USD_M2.keys()))
        m2 = st.number_input("M2 Totales", value=100.0)
        calidad = st.select_slider("Calidad / Estado", options=["A Refaccionar", "Bueno/Estándar", "Muy Bueno", "Premium"], value="Bueno/Estándar")
        
        # EL BOTÓN SOLO DISPARA EL CÁLCULO, NO MUESTRA NADA
        btn_calcular = st.form_submit_button("CALCULAR Y GUARDAR")

# --- 4. LÓGICA DE PROCESAMIENTO (SOLO SI SE APRIETA EL BOTÓN) ---
if btn_calcular:
    # A. Intentar Ubicar
    try:
        geo = Nominatim(user_agent="gerie_stable_v3")
        loc = geo.geocode(f"{calle}, {localidad}, {provincia}, Argentina")
        if loc:
            st.session_state.coords = [loc.latitude, loc.longitude]
            st.session_state.zoom = 16
        else:
            # Fallback a localidad
            loc2 = geo.geocode(f"{localidad}, {provincia}, Argentina")
            if loc2:
                st.session_state.coords = [loc2.latitude, loc2.longitude]
                st.session_state.zoom = 14
    except: pass

    # B. Calcular Valores
    base = MATRIZ_BASE_USD_M2[tipo][calidad]
    ajuste = INDICE_PROVINCIA.get(provincia, 0.75)
    valor_m2 = base * ajuste
    total_usd = valor_m2 * m2
    dolar = get_dolar_bna()
    total_ars = total_usd * dolar
    
    # C. GUARDAR EN LA CAJA FUERTE (SESSION STATE)
    st.session_state.datos_valuacion = {
        "direccion": f"{calle}, {localidad}",
        "tipo": tipo,
        "calidad": calidad,
        "m2": m2,
        "valor_m2": valor_m2,
        "total_usd": total_usd,
        "total_ars": total_ars,
        "dolar": dolar
    }
    # Forzamos una recarga para asegurar que se muestre
    st.rerun()

# --- 5. PANTALLA DE RESULTADOS (PERSISTENTE) ---
# Esta parte se ejecuta SIEMPRE que haya datos en la memoria, 
# sin importar si apretaste el botón o moviste el mapa.

if st.session_state.datos_valuacion is not None:
    datos = st.session_state.datos_valuacion
    
    col_mapa, col_info = st.columns([1.5, 1])
    
    with col_mapa:
        st.subheader("📍 Validación Geográfica")
        # El mapa usa las coordenadas guardadas en memoria
        m = folium.Map(location=st.session_state.coords, zoom_start=st.session_state.zoom)
        folium.TileLayer(
            tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
            attr='Google',
            name='Google Satélite',
            overlay=False
        ).add_to(m)
        folium.Marker(st.session_state.coords, icon=folium.Icon(color="red", icon="home")).add_to(m)
        
        # Renderizamos el mapa
        out = st_folium(m, height=500, width=None)
        
        # Si el usuario hace clic para corregir el mapa:
        if out['last_clicked']:
            st.session_state.coords = [out['last_clicked']['lat'], out['last_clicked']['lng']]
            st.rerun() # Recargamos para centrar el mapa en el clic
            
    with col_info:
        st.subheader("📑 Resultados de Valuación")
        
        # Tarjeta de Resultados (Persistente)
        st.markdown(f"""
        <div class="result-card">
            <h4 style="margin:0; color:#555;">VALOR TÉCNICO TOTAL</h4>
            <h1 style="color:#0056b3; margin:5px 0;">USD {datos['total_usd']:,.0f}</h1>
            <p><b>{datos['valor_m2']:,.0f} USD/m²</b> ({datos['calidad']})</p>
            <hr>
            <h3 style="color:#333;">$ {datos['total_ars']:,.0f}</h3>
            <small>Pesos Arg (BNA Venta: ${datos['dolar']})</small>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        st.markdown("### Detalles:")
        df = pd.DataFrame({
            "Variable": ["Ubicación", "Tipo", "Superficie", "Coeficiente Prov."],
            "Dato": [datos['direccion'], datos['tipo'], f"{datos['m2']} m²", provincia]
        })
        st.table(df)
        
        if st.button("LIMPIAR / NUEVA BÚSQUEDA"):
            st.session_state.datos_valuacion = None
            st.rerun()

else:
    # Mensaje de bienvenida si no hay datos cargados
    st.info("👈 Complete el formulario en el menú lateral y presione 'CALCULAR Y GUARDAR' para iniciar.")
    st.write("El sistema mantendrá los resultados en pantalla hasta que realice una nueva búsqueda.")
