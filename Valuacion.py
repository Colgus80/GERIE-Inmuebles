import streamlit as st
import folium
import requests
import pandas as pd
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium

# --- 1. CONFIGURACIÓN ESTRUCTURAL ---
st.set_page_config(page_title="GERIE - Valuador Estandarizado", layout="wide")

# ESTILOS CSS PARA REPORTE BANCARIO
st.markdown("""
    <style>
    .metric-container {background-color: #f0f2f6; border-left: 5px solid #004085; padding: 15px; border-radius: 5px;}
    .ref-table {font-size: 0.8em; color: #666;}
    </style>
""", unsafe_allow_html=True)

if 'coords' not in st.session_state:
    st.session_state.coords = [-34.6037, -58.3816]
if 'zoom' not in st.session_state:
    st.session_state.zoom = 12

# --- 2. LA "VERDAD" DEL SISTEMA (MATRIZ FIJA) ---
# Estos valores son promedios de mercado para GBA Norte / CABA (Zona Estándar).
# Se aplican coeficientes para ajustar por provincia o zona específica.

MATRIZ_BASE_USD_M2 = {
    "Casa": {
        "Premium/Country": 2100, 
        "Muy Bueno": 1500, 
        "Bueno/Estándar": 1150,  # Valor típico para Posadas 1538
        "Regular/A Refaccionar": 800
    },
    "Departamento": {
        "Premium/Country": 2800, 
        "Muy Bueno": 2200, 
        "Bueno/Estándar": 1700, 
        "Regular/A Refaccionar": 1200
    },
    "Local Comercial": {
        "Premium/Country": 3000, 
        "Muy Bueno": 2000, 
        "Bueno/Estándar": 1400, 
        "Regular/A Refaccionar": 900
    },
    "Depósito/Galpón": {
        "Premium/Country": 1000, 
        "Muy Bueno": 800, 
        "Bueno/Estándar": 600, 
        "Regular/A Refaccionar": 400
    }
}

# Coeficientes de Ajuste Regional (Estabilidad Federal)
INDICE_PROVINCIA = {
    "CABA": 1.10, "Buenos Aires": 1.00, # GBA es la base (1.0)
    "Córdoba": 0.90, "Santa Fe": 0.90, "Mendoza": 0.85,
    "Neuquén": 1.05, "Río Negro": 0.90, "Resto del País": 0.75
}

# --- 3. MOTORES AUXILIARES ---
@st.cache_data(ttl=3600)
def get_dolar_bna():
    try:
        r = requests.get("https://dolarapi.com/v1/dolares/oficial")
        return r.json()['venta']
    except: return 1150.0

# --- 4. INTERFAZ DE CARGA (CONTROL TOTAL DEL ANALISTA) ---
with st.sidebar:
    st.header("🎛️ Parámetros de Tasación")
    st.info("Defina las variables para obtener el valor técnico.")
    
    with st.form("form_tasacion"):
        # 1. UBICACIÓN
        calle = st.text_input("Dirección", value="Gervasio Posadas 1538")
        localidad = st.text_input("Localidad", value="Beccar")
        provincia = st.selectbox("Provincia", INDICE_PROVINCIA.keys())
        
        st.divider()
        
        # 2. CARACTERÍSTICAS FÍSICAS
        tipo = st.selectbox("Tipo de Inmueble", MATRIZ_BASE_USD_M2.keys())
        m2 = st.number_input("Superficie Total (m²)", value=100.0)
        
        # 3. FACTOR DE CALIDAD (CRÍTICO PARA LA PRECISIÓN)
        st.markdown("**Calidad Constructiva / Ubicación Específica**")
        calidad = st.select_slider(
            "Seleccione Nivel:",
            options=["Regular/A Refaccionar", "Bueno/Estándar", "Muy Bueno", "Premium/Country"],
            value="Bueno/Estándar",
            help="Estándar: Barrio abierto consolidado. Premium: Barrio Cerrado o Av. Libertador."
        )
        
        btn_calcular = st.form_submit_button("CALCULAR VALOR OFICIAL")

# --- 5. LÓGICA DE GEOLOCALIZACIÓN Y CÁLCULO ---
if btn_calcular:
    # A. Geolocalización (Solo para mapa y riesgo, NO afecta precio base)
    try:
        geo = Nominatim(user_agent="gerie_stable_v1")
        query = f"{calle}, {localidad}, {provincia}, Argentina"
        loc = geo.geocode(query)
        if loc:
            st.session_state.coords = [loc.latitude, loc.longitude]
            st.session_state.zoom = 16
        else:
            # Fallback a localidad
            loc_gen = geo.geocode(f"{localidad}, {provincia}, Argentina")
            if loc_gen:
                st.session_state.coords = [loc_gen.latitude, loc_gen.longitude]
                st.session_state.zoom = 14
                st.warning("Dirección exacta no hallada. Mostrando centro de localidad.")
    except: pass

    # B. CÁLCULO DE VALOR (MATEMÁTICA PURA, SIN CAJAS NEGRAS)
    
    # 1. Valor de Tabla
    valor_tabla_base = MATRIZ_BASE_USD_M2[tipo][calidad]
    
    # 2. Ajuste Provincial
    factor_prov = INDICE_PROVINCIA.get(provincia, 0.75)
    valor_m2_ajustado = valor_tabla_base * factor_prov
    
    # 3. Totales
    total_usd = valor_m2_ajustado * m2
    dolar_bna = get_dolar_bna()
    total_ars = total_usd * dolar_bna

    # --- 6. VISUALIZACIÓN DE RESULTADOS ---
    
    # COLUMNA IZQUIERDA: VALIDACIÓN VISUAL
    c_map, c_data = st.columns([1.5, 1])
    
    with c_map:
        st.subheader("📍 Ubicación del Activo")
        m = folium.Map(location=st.session_state.coords, zoom_start=st.session_state.zoom)
        folium.TileLayer(
            tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
            attr='Google',
            name='Google Satélite',
            overlay=False
        ).add_to(m)
        
        folium.Marker(st.session_state.coords, icon=folium.Icon(color="red", icon="home")).add_to(m)
        st_folium(m, height=450)
        st.caption("*Verifique visualmente la calidad del entorno con la vista satelital.*")

    # COLUMNA DERECHA: INFORME FINANCIERO
    with c_data:
        st.subheader("📑 Informe de Valuación")
        
        st.markdown(f"""
        <div class="metric-container">
            <h3 style="margin:0; color:#555;">VALOR DE GARANTÍA (USD)</h3>
            <h1 style="margin:0; color:#004085;">USD {total_usd:,.0f}</h1>
            <p style="margin:0;"><b>{valor_m2_ajustado:,.0f} USD/m²</b> (Ajustado)</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        st.markdown(f"**Valor de Cobertura en Pesos (BNA ${dolar_bna}):**")
        st.markdown(f"### $ {total_ars:,.0f}")
        
        st.divider()
        st.write("🔍 **Desglose del Algoritmo:**")
        
        df_desglose = pd.DataFrame({
            "Variable": ["Valor Base Matriz", "Categoría", "Ajuste Provincial", "Superficie"],
            "Detalle": [f"USD {valor_tabla_base}", calidad, f"{factor_prov*100:.0f}% ({provincia})", f"{m2} m²"]
        })
        st.table(df_desglose)
        
        st.info("Este valor es técnico y estable. Solo variará si usted cambia la categoría de 'Bueno' a 'Premium'.")

else:
    st.info("Ingrese los datos en el panel lateral para iniciar la valuación.")

# --- 7. TABLA DE REFERENCIA (TRANSPARENCIA TOTAL) ---
with st.expander("Ver Matriz de Precios Base del Sistema (USD/m²)"):
    st.write("Estos son los valores fijos que utiliza el sistema antes de aplicar el coeficiente provincial.")
    st.dataframe(pd.DataFrame(MATRIZ_BASE_USD_M2))
