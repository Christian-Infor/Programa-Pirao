import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- CARGA DE DATOS REALES ---
@st.cache_data(ttl=60) # Refresca los datos cada 60 segundos
def cargar_datos():
    # Leer tabla directorio
    respuesta_dir = supabase.table("directorio").select("*").execute()
    df_directorio = pd.DataFrame(respuesta_dir.data)
    
    # Leer tabla de pagos
    respuesta_pagos = supabase.table("registro_pagos").select("*").execute()
    df_pagos = pd.DataFrame(respuesta_pagos.data)
    
    return df_directorio, df_pagos

df_directorio, df_pagos = cargar_datos()

# --- 2. CONTROL DE SESIÓN ---
# Verificamos si el usuario ya inició sesión
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["parcela"] = ""

# Función para cerrar sesión
def cerrar_sesion():
    st.session_state["autenticado"] = False
    st.session_state["parcela"] = ""

# --- 3. PANTALLA DE LOGIN ---
if not st.session_state["autenticado"]:
    st.title("🔐 Acceso Alto Pirao")
    st.markdown("Ingrese sus credenciales para revisar o informar el pago de gastos comunes.")
    
    with st.form("formulario_login"):
        input_parcela = st.text_input("Número de Parcela (ej: 1) o 'Admin'")
        input_pin = st.text_input("PIN de seguridad", type="password")
        btn_ingresar = st.form_submit_button("Ingresar")
        
        if btn_ingresar:
            # Filtramos el dataframe para ver si existe coincidencia
            usuario_valido = df_directorio[
                (df_directorio["parcela"] == input_parcela) & 
                (df_directorio["pin"] == input_pin)
            ]
            
            if not usuario_valido.empty:
                st.session_state["autenticado"] = True
                st.session_state["parcela"] = input_parcela
                st.rerun() # Recarga la página para mostrar el panel
            else:
                st.error("Número de parcela o PIN incorrectos. Intente nuevamente.")

# --- 4. PANTALLA PRINCIPAL (Una vez dentro) ---
else:
    # Menú lateral para cerrar sesión
    st.sidebar.title(f"Bienvenido, Parcela {st.session_state['parcela']}")
    st.sidebar.button("Cerrar Sesión", on_click=cerrar_sesion)
    
    parcela_actual = st.session_state["parcela"]
    
    # VISTA ADMINISTRADOR
    if parcela_actual == "Admin":
        st.title("🛠️ Panel de Administración - Alto Pirao")
        
        st.subheader("Pagos Pendientes de Aprobación")
        # Filtramos solo lo que está pendiente en todo el condominio
        df_pendientes = df_pagos[df_pagos["estado"] == "Pendiente"]
        
        if df_pendientes.empty:
            st.success("No hay pagos pendientes por revisar.")
        else:
            st.dataframe(df_pendientes, use_container_width=True)
            st.info("Aquí agregaremos la lógica para cambiar el estado de 'Pendiente' a 'Aprobado'.")
            
        st.subheader("Todos los registros (Historial histórico)")
        st.dataframe(df_pagos, use_container_width=True)

    # VISTA VECINO
    else:
        st.title(f"🏡 Panel de Parcela {parcela_actual}")
        
        st.subheader("Historial de Pagos")
        # Filtramos la base de datos SOLO para la parcela que inició sesión
        mis_pagos = df_pagos[df_pagos["parcela"] == parcela_actual]
        st.dataframe(mis_pagos, use_container_width=True)
        
        st.divider()
        
        st.subheader("Informar Nuevo Pago")
        with st.form("form_nuevo_pago"):
            mes_pago = st.selectbox("Mes a pagar", ["Enero", "Febrero", "Marzo", "Abril", "Mayo"])
            monto = st.number_input("Monto pagado ($)", min_value=0, step=1000)
            archivo = st.file_uploader("Adjuntar comprobante de transferencia", type=["jpg", "png", "pdf"])
            
            submit_pago = st.form_submit_button("Enviar Comprobante")
            
            if submit_pago:
                st.success("Esta función subirá el archivo a Google Drive y registrará el pago en Google Sheets.")
