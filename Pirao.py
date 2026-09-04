import streamlit as st
import pandas as pd

# Configuración básica de la página
st.set_page_config(page_title="Gastos Comunes - Alto Pirao", layout="centered")

# --- 1. SIMULACIÓN DE BASE DE DATOS (Luego conectaremos Google Sheets) ---
@st.cache_data
def cargar_datos():
    # Pestaña oculta: Directorio de contraseñas
    directorio = pd.DataFrame({
        "Parcela": ["1", "2", "3", "Admin"],
        "PIN": ["1111", "2222", "3333", "9999"]
    })
    
    # Pestaña visible: Registro de Pagos (Estructura vertical)
    pagos = pd.DataFrame({
        "ID Pago": ["P1-2026-01", "P2-2026-01", "P1-2026-02"],
        "Parcela": ["1", "2", "1"],
        "Mes": ["Enero", "Enero", "Febrero"],
        "Año": [2026, 2026, 2026],
        "Monto": [10000, 10000, 4000],
        "Estado": ["Aprobado", "Pendiente", "Pendiente"],
        "Link Comprobante": ["url_drive_1", "url_drive_2", "url_drive_3"]
    })
    return directorio, pagos

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
                (df_directorio["Parcela"] == input_parcela) & 
                (df_directorio["PIN"] == input_pin)
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
        df_pendientes = df_pagos[df_pagos["Estado"] == "Pendiente"]
        
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
        mis_pagos = df_pagos[df_pagos["Parcela"] == parcela_actual]
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