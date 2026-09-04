import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN BÁSICA ---
st.set_page_config(page_title="Gastos Comunes - Alto Pirao", layout="centered")

# --- 2. CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_connection():
    # Llama a las variables secretas de Streamlit
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- 3. CARGA DE DATOS SEGUROS ---
@st.cache_data(ttl=60) # Refresca los datos cada 60 segundos
def cargar_datos():
    # Leer tabla directorio
    respuesta_dir = supabase.table("directorio").select("*").execute()
    # Prevención de errores: si está vacío, crea columnas vacías
    if respuesta_dir.data:
        df_directorio = pd.DataFrame(respuesta_dir.data)
    else:
        df_directorio = pd.DataFrame(columns=["parcela", "pin"])
    
    # Leer tabla de pagos
    respuesta_pagos = supabase.table("registro_pagos").select("*").execute()
    # Prevención de errores: si está vacío, crea columnas vacías
    if respuesta_pagos.data:
        df_pagos = pd.DataFrame(respuesta_pagos.data)
    else:
        df_pagos = pd.DataFrame(columns=["id", "id_pago", "parcela", "mes", "ano", "monto", "estado", "link_comprobante"])
    
    return df_directorio, df_pagos

df_directorio, df_pagos = cargar_datos()

# --- 4. CONTROL DE SESIÓN ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["parcela"] = ""

def cerrar_sesion():
    st.session_state["autenticado"] = False
    st.session_state["parcela"] = ""

# --- 5. PANTALLA DE LOGIN ---
if not st.session_state["autenticado"]:
    st.title("🔐 Acceso Alto Pirao")
    st.markdown("Ingrese sus credenciales para revisar o informar el pago de gastos comunes.")
    
    with st.form("formulario_login"):
        input_parcela = st.text_input("Número de Parcela (ej: 1) o 'Admin'")
        input_pin = st.text_input("PIN de seguridad", type="password")
        btn_ingresar = st.form_submit_button("Ingresar")
        
        if btn_ingresar:
            # Filtro en minúsculas para coincidir con Supabase
            usuario_valido = df_directorio[
                (df_directorio["parcela"] == input_parcela) & 
                (df_directorio["pin"] == input_pin)
            ]
            
            if not usuario_valido.empty:
                st.session_state["autenticado"] = True
                st.session_state["parcela"] = input_parcela
                st.rerun()
            else:
                st.error("Número de parcela o PIN incorrectos. Intente nuevamente.")

# --- 6. PANTALLA PRINCIPAL (Una vez dentro) ---
else:
    st.sidebar.title(f"Bienvenido, Parcela {st.session_state['parcela']}")
    st.sidebar.button("Cerrar Sesión", on_click=cerrar_sesion)
    
    parcela_actual = st.session_state["parcela"]
    
    # 🌟 CREAMOS UNA COPIA SOLO PARA LA VISTA (Oculta IDs y arregla textos)
    df_visual = df_pagos.drop(columns=["id", "id_pago"], errors='ignore').rename(
        columns={
            "parcela": "Parcela",
            "mes": "Mes",
            "ano": "Año",
            "monto": "Monto ($)",
            "estado": "Estado",
            "link_comprobante": "Comprobante"
        }
    )
    
    # VISTA ADMINISTRADOR
    if parcela_actual == "Admin":
        st.title("🛠️ Panel de Administración - Alto Pirao")
        
        st.subheader("Pagos Pendientes de Aprobación")
        # Filtramos usando la columna ya renombrada con mayúscula ("Estado")
        df_pendientes = df_visual[df_visual["Estado"] == "Pendiente"]
        
        if df_pendientes.empty:
            st.success("No hay pagos pendientes por revisar.")
        else:
            # Formateamos el DataFrame para que el link sea clickeable
            st.dataframe(
                df_pendientes, 
                use_container_width=True,
                column_config={
                    "Comprobante": st.column_config.LinkColumn("Ver Comprobante")
                }
            )
            st.info("Próximamente: lógica para aprobar pagos directamente desde aquí.")
            
        st.subheader("Todos los registros (Historial histórico)")
        st.dataframe(
            df_visual, 
            use_container_width=True,
            column_config={
                "Comprobante": st.column_config.LinkColumn("Ver Comprobante")
            }
        )

    # VISTA VECINO
    else:
        st.title(f"🏡 Panel de Parcela {parcela_actual}")
        
        st.subheader("Historial de Pagos")
        # Filtramos usando la columna ya renombrada ("Parcela")
        mis_pagos = df_visual[df_visual["Parcela"] == parcela_actual]
        
        if mis_pagos.empty:
            st.info("Aún no tienes pagos registrados en el sistema.")
        else:
            st.dataframe(
                mis_pagos, 
                use_container_width=True,
                column_config={
                    "Comprobante": st.column_config.LinkColumn("Ver Comprobante")
                }
            )
        
        st.divider()
        
        st.subheader("Informar Nuevo Pago")
        with st.form("form_nuevo_pago"):
            mes_pago = st.selectbox("Mes a pagar", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
            monto = st.number_input("Monto pagado ($)", min_value=0, step=1000)
            archivo = st.file_uploader("Adjuntar comprobante de transferencia", type=["jpg", "png", "pdf"])
            
            submit_pago = st.form_submit_button("Enviar Comprobante")
            
            if submit_pago:
                if archivo is not None:
                    with st.spinner("Procesando pago y subiendo archivo..."):
                        # 1. Armar la ruta del archivo (Ej: parcela_1/Enero_comprobante.pdf)
                        ruta_archivo = f"parcela_{parcela_actual}/{mes_pago}_{archivo.name}"
                        
                        # 2. Subir el archivo al bucket 'comprobantes' de Supabase
                        supabase.storage.from_("comprobantes").upload(
                            path=ruta_archivo,
                            file=archivo.getvalue(),
                            file_options={
                                "content-type": archivo.type,
                                "x-upsert": "true" # Permite reescribir si la imagen ya se había intentado subir
                            }
                        )
                        
                        # 3. Obtener el link público del archivo recién subido
                        link_publico = supabase.storage.from_("comprobantes").get_public_url(ruta_archivo)
                        
                        # 4. Crear el registro para la tabla SQL
                        nuevo_registro = {
                            "id_pago": f"P{parcela_actual}-2026-{mes_pago[:3].upper()}",
                            "parcela": str(parcela_actual),
                            "mes": mes_pago,
                            "ano": 2026, 
                            "monto": monto,
                            "estado": "Pendiente",
                            "link_comprobante": link_publico
                        }
                        # 5. Insertar los datos en la tabla registro_pagos
                        supabase.table("registro_pagos").insert(nuevo_registro).execute()
                        
                    st.success("¡Pago enviado exitosamente!")
                    cargar_datos.clear() # Limpia la memoria para forzar la lectura del nuevo pago
                    st.rerun() # Refresca la pantalla
                else:
                    st.error("⚠️ Por favor, adjunta un comprobante antes de enviar el formulario.")
