import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date
import io

# --- 1. CONFIGURACIÓN BÁSICA ---
st.set_page_config(page_title="Gastos Comunes - Alto Pirao v1.0", layout="centered")

# --- 1.1 ESTILOS CSS PERSONALIZADOS ---
st.markdown(
    """
    <style>
        html, body, [class*="css"] {
            font-size: 18px !important;
        }
        h1 {
            font-size: 2.3rem !important;
        }
        h2 {
            font-size: 1.8rem !important;
        }
        h3 {
            font-size: 1.4rem !important;
        }
        .stForm {
            padding: 20px;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 2. CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- 3. CARGA DE DATOS SEGUROS ---
@st.cache_data(ttl=60)
def cargar_datos():
    respuesta_dir = supabase.table("directorio").select("*").execute()
    df_directorio = pd.DataFrame(respuesta_dir.data) if respuesta_dir.data else pd.DataFrame(columns=["parcela", "pin"])
    
    respuesta_pagos = supabase.table("registro_pagos").select("*").execute()
    df_pagos = pd.DataFrame(respuesta_pagos.data) if respuesta_pagos.data else pd.DataFrame(columns=["id", "id_pago", "parcela", "mes", "ano", "monto", "estado", "link_comprobante"])
    
    respuesta_gastos = supabase.table("registro_gastos").select("*").execute()
    df_gastos = pd.DataFrame(respuesta_gastos.data) if respuesta_gastos.data else pd.DataFrame(columns=["id", "fecha", "motivo", "monto", "forma_pago", "link_comprobante"])
    
    return df_directorio, df_pagos, df_gastos

df_directorio, df_pagos, df_gastos = cargar_datos()

# Función auxiliar para formatear números a pesos chilenos (Ej: 10000 -> $10.000)
def formato_clp(valor):
    if pd.isna(valor) or valor == 0:
        return "$0"
    return f"${int(valor):,}".replace(",", ".")

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

# --- 6. PANTALLA PRINCIPAL ---
else:
    st.sidebar.title(f"Bienvenido, Parcela {st.session_state['parcela']}")
    st.sidebar.caption("Software de Gestión - Alto Pirao **v1.0**")
    st.sidebar.button("Cerrar Sesión", on_click=cerrar_sesion)
    
    parcela_actual = st.session_state["parcela"]
    
    # Preparamos el DataFrame visual de pagos aplicando formato chileno a los montos
    df_visual = df_pagos.drop(columns=["id", "id_pago"], errors='ignore').copy()
    if not df_visual.empty and "monto" in df_visual.columns:
        df_visual["monto"] = df_visual["monto"].apply(formato_clp)
        
    df_visual = df_visual.rename(
        columns={
            "parcela": "Parcela",
            "mes": "Mes",
            "ano": "Año",
            "monto": "Monto",
            "estado": "Estado",
            "link_comprobante": "Comprobante"
        }
    )
    
    # ----------------------------------------
    # VISTA ADMINISTRADOR
    # ----------------------------------------
    if parcela_actual == "Admin":
        st.title("🛠️ Panel de Administración - Alto Pirao v1.0")
        
        tab_pendientes, tab_matriz, tab_gastos, tab_historial, tab_migrar = st.tabs([
            "📥 Validar Pagos", 
            "📊 Matriz Anual (Cuotas)", 
            "💸 Registrar Gastos (Egresos)", 
            "📜 Historial General",
            "⚙️ Migrar Excel"
        ])
        
        with tab_pendientes:
            st.subheader("Pagos Pendientes de Aprobación")
            df_pendientes = df_pagos[df_pagos["estado"] == "Pendiente"]
            
            if df_pendientes.empty:
                st.success("No hay pagos pendientes por revisar.")
            else:
                for index, fila in df_pendientes.iterrows():
                    with st.container(border=True):
                        col1, col2, col3, col4 = st.columns(4)
                        col1.write(f"**Parcela:** {fila['parcela']}")
                        col2.write(f"**Mes:** {fila['mes']}")
                        col3.write(f"**Monto:** {formato_clp(fila['monto'])}")
                        col4.markdown(f"[📎 Ver Comprobante]({fila['link_comprobante']})")
                        
                        btn_col1, btn_col2 = st.columns(2)
                        if btn_col1.button("✅ Aprobar", key=f"aprobar_{fila['id']}", use_container_width=True):
                            supabase.table("registro_pagos").update({"estado": "Aprobado"}).eq("id", fila['id']).execute()
                            cargar_datos.clear()
                            st.rerun()
                            
                        if btn_col2.button("❌ Rechazar", key=f"rechazar_{fila['id']}", use_container_width=True):
                            supabase.table("registro_pagos").update({"estado": "Rechazado"}).eq("id", fila['id']).execute()
                            cargar_datos.clear()
                            st.rerun()

        # --- PESTAÑA 2: MATRIZ ANUAL (Con formato monetario chileno) ---
        with tab_matriz:
            st.subheader("Matriz de Estado de Cuotas")
            ano_seleccionado = st.selectbox("Seleccione el Año a Visualizar", [2026, 2025], index=0)
            
            if not df_pagos.empty:
                df_filtrado = df_pagos[(df_pagos["estado"] == "Aprobado") & (df_pagos["ano"] == ano_seleccionado)].copy()
                if not df_filtrado.empty:
                    df_filtrado["parcela_num"] = pd.to_numeric(df_filtrado["parcela"], errors="coerce")
                    meses_orden = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                    
                    matriz = df_filtrado.pivot_table(index="parcela_num", columns="mes", values="monto", fill_value=0)
                    matriz.index = [f"Parcela {int(p)}" for p in matriz.index]
                    meses_existentes = [m for m in meses_orden if m in matriz.columns]
                    matriz = matriz[meses_existentes]
                    
                    # Aplicamos formato CLP a cada celda de la matriz
                    matriz_formateada = matriz.applymap(formato_clp)
                    
                    with st.container():
                        st.dataframe(matriz_formateada, use_container_width=True, height=500)
                else:
                    st.info(f"Aún no hay pagos aprobados para el año {ano_seleccionado}.")
            else:
                st.info("No hay registros en la base de datos.")

        with tab_gastos:
            st.subheader("Control de Gastos y Egresos del Condominio")
            
            with st.form("form_nuevo_gasto"):
                col_g1, col_g2 = st.columns(2)
                fecha_gasto = col_g1.date_input("Fecha del gasto", value=date.today())
                monto_gasto = col_g2.number_input("Monto del gasto ($)", min_value=0, step=1000)
                
                motivo_gasto = st.text_input("Motivo o Detalle (Ej: CGE Electricidad, Compra de cámaras)")
                forma_pago_gasto = st.selectbox("Forma de pago", ["Pagado directamente con fondos GC", "Reembolsado a Parcela"])
                archivo_boleta = st.file_uploader("Adjuntar boleta/factura del gasto (Opcional)", type=["jpg", "png", "pdf"])
                
                submit_gasto = st.form_submit_button("Guardar Gasto")
                
                if submit_gasto:
                    if motivo_gasto and monto_gasto > 0:
                        link_pub_boleta = ""
                        if archivo_boleta is not None:
                            with st.spinner("Subiendo boleta a Supabase..."):
                                ruta_boleta = f"gastos_{fecha_gasto}_{archivo_boleta.name}"
                                supabase.storage.from_("boletas-gastos").upload(
                                    path=ruta_boleta,
                                    file=archivo_boleta.getvalue(),
                                    file_options={"content-type": archivo.type, "x-upsert": "true"}
                                )
                                link_pub_boleta = supabase.storage.from_("boletas-gastos").get_public_url(ruta_boleta)
                        
                        nuevo_gasto_dict = {
                            "fecha": str(fecha_gasto),
                            "motivo": motivo_gasto,
                            "monto": int(monto_gasto),
                            "forma_pago": forma_pago_gasto,
                            "link_comprobante": link_pub_boleta
                        }
                        supabase.table("registro_gastos").insert(nuevo_gasto_dict).execute()
                        st.success("¡Gasto registrado exitosamente!")
                        cargar_datos.clear()
                        st.rerun()
                    else:
                        st.error("Por favor completa el motivo y un monto válido.")
            
            st.divider()
            st.markdown("### Historial de Egresos Registrados")
            if not df_gastos.empty:
                df_g_visual = df_gastos.copy()
                if "monto" in df_g_visual.columns:
                    df_g_visual["monto"] = df_g_visual["monto"].apply(formato_clp)
                
                df_g_visual = df_g_visual.drop(columns=["id"], errors="ignore").rename(
                    columns={
                        "fecha": "Fecha",
                        "motivo": "Motivo",
                        "monto": "Monto",
                        "forma_pago": "Forma de Pago",
                        "link_comprobante": "Boleta"
                    }
                )
                st.dataframe(
                    df_g_visual, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={"Boleta": st.column_config.LinkColumn("Ver Boleta")}
                )
            else:
                st.info("No hay gastos registrados todavía.")

        with tab_historial:
            st.subheader("Todos los registros de pagos")
            st.dataframe(
                df_visual, 
                use_container_width=True,
                hide_index=True,
                column_config={"Comprobante": st.column_config.LinkColumn("Ver Comprobante")}
            )

        with tab_migrar:
            st.subheader("⚡ Herramienta de Migración Histórica Completa desde Excel")
            st.markdown("Sube tu archivo de Excel. El sistema importará automáticamente las cuotas de **2026**, las de **2025** y los registros de la pestaña **Gastos**.")
            
            archivo_excel = st.file_uploader("Selecciona tu archivo Excel (.xlsx)", type=["xlsx"])
            
            if archivo_excel is not None:
                if st.button("🚀 Procesar e Importar Todo el Historial"):
                    try:
                        with st.spinner("Leyendo y migrando 2025, 2026 y Gastos..."):
                            excel_bytes = io.BytesIO(archivo_excel.getvalue())
                            registros_pagos = []
                            meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

                            try:
                                df_c26 = pd.read_excel(excel_bytes, sheet_name="Cuotas 2026")
                                df_c26.columns = [str(c).strip().lower() for c in df_c26.columns]
                                for index, row in df_c26.iterrows():
                                    parcela_nombre = row.iloc[0]
                                    if pd.isna(parcela_nombre) or "Parcela" not in str(parcela_nombre):
                                        continue
                                    num_p = str(parcela_nombre).replace("Parcela", "").strip()
                                    for i, mes in enumerate(meses):
                                        val = row.iloc[i + 1]
                                        if pd.notna(val) and isinstance(val, (int, float)) and val > 0:
                                            registros_pagos.append({
                                                "id_pago": f"P{num_p}-2026-{mes[:3].upper()}",
                                                "parcela": num_p,
                                                "mes": mes,
                                                "ano": 2026,
                                                "monto": int(val),
                                                "estado": "Aprobado",
                                                "link_comprobante": "https://dummyimage.com/600x400/000/fff&text=Migrado+Excel+2026"
                                            })
                            except Exception as ex:
                                st.warning(f"No se pudo leer Cuotas 2026: {ex}")

                            try:
                                excel_bytes.seek(0)
                                df_c25 = pd.read_excel(excel_bytes, sheet_name="Cuotas 2025")
                                df_c25.columns = [str(c).strip().lower() for c in df_c25.columns]
                                for index, row in df_c25.iterrows():
                                    parcela_nombre = row.iloc[0]
                                    if pd.isna(parcela_nombre) or "Parcela" not in str(parcela_nombre):
                                        continue
                                    num_p = str(parcela_nombre).replace("Parcela", "").strip()
                                    for i, mes in enumerate(meses):
                                        val = row.iloc[i + 1]
                                        if pd.notna(val) and isinstance(val, (int, float)) and val > 0:
                                            registros_pagos.append({
                                                "id_pago": f"P{num_p}-2025-{mes[:3].upper()}",
                                                "parcela": num_p,
                                                "mes": mes,
                                                "ano": 2025,
                                                "monto": int(val),
                                                "estado": "Aprobado",
                                                "link_comprobante": "https://dummyimage.com/600x400/000/fff&text=Migrado+Excel+2025"
                                            })
                            except Exception as ex:
                                st.warning(f"No se pudo leer Cuotas 2025: {ex}")

                            if registros_pagos:
                                supabase.table("registro_pagos").upsert(registros_pagos).execute()

                            try:
                                excel_bytes.seek(0)
                                df_g = pd.read_excel(excel_bytes, sheet_name="Gastos")
                                registros_gastos = []
                                for index, row in df_g.iterrows():
                                    fecha = row.get("Fecha")
                                    motivo = row.get("Motivo")
                                    monto = row.get("Monto")
                                    forma_pago = row.get("Forma de Pago")
                                    link_comp = row.get("Link Comprobante")

                                    if pd.notna(motivo) and pd.notna(monto):
                                        registros_gastos.append({
                                            "fecha": str(fecha).split(" ")[0] if pd.notna(fecha) else "2025-01-01",
                                            "motivo": str(motivo),
                                            "monto": int(monto),
                                            "forma_pago": str(forma_pago) if pd.notna(forma_pago) else "Pagado directamente con fondos GC",
                                            "link_comprobante": str(link_comp) if pd.notna(link_comp) else ""
                                        })
                                
                                if registros_gastos:
                                    supabase.table("registro_gastos").upsert(registros_gastos).execute()
                            except Exception as ex:
                                st.warning(f"No se pudo leer la pestaña de Gastos: {ex}")

                        st.success("¡Migración histórica completa con éxito! Los datos de 2025, 2026 y Gastos ya están en Supabase.")
                        cargar_datos.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error general durante la migración: {e}")

    # ----------------------------------------
    # VISTA VECINO
    # ----------------------------------------
    else:
        st.title(f"🏡 Panel de Parcela {parcela_actual}")
        
        st.subheader("Historial de Mis Pagos")
        mis_pagos = df_visual[df_visual["Parcela"] == parcela_actual]
        
        if mis_pagos.empty:
            st.info("Aún no tienes pagos registrados en el sistema.")
        else:
            st.dataframe(
                mis_pagos, 
                use_container_width=True,
                hide_index=True,
                column_config={"Comprobante": st.column_config.LinkColumn("Ver Comprobante")}
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
                        ruta_archivo = f"parcela_{parcela_actual}/{mes_pago}_{archivo.name}"
                        
                        supabase.storage.from_("comprobantes").upload(
                            path=ruta_archivo,
                            file=archivo.getvalue(),
                            file_options={"content-type": archivo.type, "x-upsert": "true"}
                        )
                        
                        link_publico = supabase.storage.from_("comprobantes").get_public_url(ruta_archivo)
                        
                        nuevo_registro = {
                            "id_pago": f"P{parcela_actual}-2026-{mes_pago[:3].upper()}",
                            "parcela": str(parcela_actual),
                            "mes": mes_pago,
                            "ano": 2026, 
                            "monto": int(monto),
                            "estado": "Pendiente",
                            "link_comprobante": link_publico
                        }
                        
                        supabase.table("registro_pagos").insert(nuevo_registro).execute()
                        
                    st.success("¡Pago enviado exitosamente!")
                    cargar_datos.clear() 
                    st.rerun()
                else:
                    st.error("⚠️ Por favor, adjunta un comprobante antes de enviar el formulario.")
