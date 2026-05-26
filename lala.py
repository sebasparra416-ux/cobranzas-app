import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# =====================================================================
# CONFIGURACIÓN VISUAL DE LA APP (MÓVIL / PC)
# =====================================================================
st.set_page_config(
    page_title="Cobranzas Parra Castillo", 
    page_icon="🏢", 
    layout="centered"
)

# Estilo para botones gigantes y fácil lectura en la calle desde el celular
st.markdown("""
    <style>
    div.stButton > button:first-child {
        width: 100%;
        height: 55px;
        font-size: 18px;
        font-weight: bold;
        border-radius: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 16px;
        font-weight: bold;
    }
    h3 {
        color: #1E3A8A;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🏢 COBRANZAS PARRA CASTILLO")
st.write("📲 _Sistema de Control de Créditos y Recaudos en Tiempo Real_")

# =====================================================================
# CONEXIÓN CON LA BASE DE DATOS EN LA NUBE (GOOGLE SHEETS)
# =====================================================================
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=2) # Sincronización rápida: se refresca cada 2 segundos
def cargar_todo_desde_nube():
    try:
        df_cli = conn.read(worksheet="CLIENTES")
        df_cre = conn.read(worksheet="CREDITOS")
        df_pag = conn.read(worksheet="PAGOS")
        return pd.DataFrame(df_cli), pd.DataFrame(df_cre), pd.DataFrame(df_pag)
    except Exception:
        # Estructura de respaldo si las hojas de cálculo están vacías de fábrica
        return (
            pd.DataFrame(columns=["ID_Cliente", "Nombre", "Cedula", "Telefono", "Direccion", "Fiador_Nombre", "Fiador_Cedula", "Fiador_Telefono", "Fiador_Direccion"]),
            pd.DataFrame(columns=["ID_Credito", "ID_Cliente", "Monto", "Interes", "Modalidad", "Cuotas", "Total_Pagar", "Valor_Cuota", "Fecha_Inicio"]),
            pd.DataFrame(columns=["ID_Pago", "ID_Credito", "Num_Cuota", "Fecha_Vencimiento", "Monto_Cuota", "Estado", "Abonado", "Fecha_Real_Pago"])
        )

df_clientes, df_creditos, df_pagos = cargar_todo_desde_nube()

# Menú de pestañas para celular
tab_buscar, tab_registro = st.tabs(["💵 Buscar y Cobrar", "📝 Registrar Crédito"])

# =====================================================================
# PESTAÑA 1: BUSCADOR EN VIVO, ESTADO DE CUENTAS Y CONTROL DE COBROS
# =====================================================================
with tab_buscar:
    st.subheader("🔎 Cobros en la Calle")
    buscar = st.text_input("Buscar cliente por Nombre o Cédula:", placeholder="Ej: Juan Carlos...")
    
    st.write("---")
    
    if not df_clientes.empty and not df_creditos.empty:
        # Unimos las tablas para saber qué crédito le pertenece a cada quién
        df_maestro = pd.merge(df_clientes, df_creditos, on="ID_Cliente", how="inner")
        
        if buscar:
            df_maestro = df_maestro[
                df_maestro["Nombre"].str.contains(buscar, case=False, na=False) | 
                df_maestro["Cedula"].astype(str).str.contains(buscar, na=False)
            ]
        
        if not df_maestro.empty:
            st.write("### 👥 Clientes Encontrados")
            for index, row in df_maestro.iterrows():
                # Filtrar los pagos específicos de este crédito para calcular el saldo real
                pagos_este_credito = df_pagos[df_pagos["ID_Credito"] == row["ID_Credito"]] if not df_pagos.empty else pd.DataFrame()
                
                total_recaudado = pagos_este_credito["Abonado"].astype(float).sum() if not pagos_este_credito.empty else 0.0
                saldo_restante = float(row["Total_Pagar"]) - total_recaudado
                
                # Tarjeta visual por cada cliente (Muy cómodo para ver en celular)
                with st.expander(f"👤 {row['Nombre']} | Saldo: ${saldo_restante:,.0f}"):
                    st.markdown(f"""
                    * **Cédula:** {row['Cedula']} | **Teléfono:** {row['Telefono']}
                    * **Dirección:** {row['Direccion']}
                    * **Fiador:** {row['Fiador_Nombre']} ({row['Fiador_Telefono']})
                    * **Detalle Préstamo:** ${float(row['Monto']):,.0f} al {row['Interes']}% ({row['Modalidad']})
                    * **Cuota Pactada:** {row['Cuotas']} cuotas de **${float(row['Valor_Cuota']):,.0f}**
                    """)
                    
                    st.write("---")
                    st.write("📊 **Plan de Cuotas e Historial:**")
                    if not pagos_este_credito.empty:
                        st.dataframe(pagos_este_credito[["Num_Cuota", "Fecha_Vencimiento", "Monto_Cuota", "Estado", "Abonado", "Fecha_Real_Pago"]], use_container_width=True)
                    else:
                        st.caption("No se han generado cuotas para este crédito.")
            
            st.write("---")
            st.write("### 💵 Registrar Recaudo / Abono")
            cliente_seleccionado = st.selectbox("Seleccione el cliente que va a pagar en este momento:", df_maestro["Nombre"].tolist())
            
            credito_sel = df_maestro[df_maestro["Nombre"] == cliente_seleccionado].iloc[0]
            id_credito_actual = credito_sel["ID_Credito"]
            cuota_fija = float(credito_sel["Valor_Cuota"])
            
            tipo_recaudo = st.radio("¿Qué tipo de pago va a realizar?", ["Pagar Cuota Completa", "Hacer un Abono Parcial"])
            
            monto_a_guardar = cuota_fija
            if tipo_recaudo == "Hacer un Abono Parcial":
                monto_a_guardar = st.number_input("Escriba el valor recibido ($):", min_value=0, step=5000, value=10000)
            
            if st.button("💾 Guardar Cobro en la Nube", type="primary"):
                # Lógica para asentar el pago en la tabla PAGOS
                pagos_credito = df_pagos[df_pagos["ID_Credito"] == id_credito_actual]
                cuotas_pendientes = pagos_credito[pagos_credito["Estado"] == "Pendiente"]
                
                if not cuotas_pendientes.empty:
                    idx_cuota_a_pagar = cuotas_pendientes.index[0]
                    df_pagos.at[idx_cuota_a_pagar, "Estado"] = "PAGADO" if tipo_recaudo == "Pagar Cuota Completa" else "ABONADO"
                    df_pagos.at[idx_cuota_a_pagar, "Abonado"] = float(df_pagos.at[idx_cuota_a_pagar, "Abonado"] or 0) + float(monto_a_guardar)
                    df_pagos.at[idx_cuota_a_pagar, "Fecha_Real_Pago"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                    
                    # Guardar cambios directo en la pestaña PAGOS de Google Sheets
                    conn.update(worksheet="PAGOS", data=df_pagos)
                    st.success(f"¡Excelente! Se registraron ${monto_a_guardar:,.0f} a la cuenta de {cliente_seleccionado}.")
                    st.balloons()
                    st.rerun()
                else:
                    st.warning("Este cliente ya no tiene más cuotas pendientes en este crédito.")
        else:
            st.warning("No se encontró ningún cliente con ese nombre.")
    else:
        st.info("No hay créditos registrados todavía en el sistema.")

# =====================================================================
# PESTAÑA 2: ESTUDIO, CÁLCULO DE FECHAS AUTOMÁTICAS Y NUEVOS CRÉDITOS
# =====================================================================
with tab_registro:
    st.subheader("📝 Crear Nuevo Plan de Crédito")
    
    col1, col2 = st.columns(2)
    with col1:
        nombre = st.text_input("Nombre Completo del Cliente (*)")
        cedula = st.text_input("Cédula / ID (*)")
        telefono = st.text_input("Teléfono Celular (*)")
        direccion = st.text_input("Dirección de Residencia (*)")
    with col2:
        f_nombre = st.text_input("Nombre Completo del Fiador (*)")
        f_cedula = st.text_input("Cédula del Fiador")
        f_telefono = st.text_input("Teléfono del Fiador (*)")
        f_direccion = st.text_input("Dirección del Fiador")
        
    st.write("---")
    st.write("📊 **Condiciones del Préstamo**")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        monto = st.number_input("Monto a Prestar ($) (*)", min_value=0, step=50000, value=500000)
    with c2:
        interes = st.number_input("Interés (%)", min_value=0, max_value=100, step=5, value=20)
    with c3:
        frecuencia = st.selectbox("Frecuencia", ["Diario", "Semanal", "Quincenal", "Mensual"])
    with c4:
        cuotas = st.number_input("N° Cuotas", min_value=1, step=1, value=20)
        
    st.write("---")
    
    if st.button("⚙️ Procesar Estudio, Calendario y Guardar Crédito"):
        if nombre and cedula and telefono and f_nombre and monto > 0:
            # Cálculos financieros automáticos
            total_interes = float(monto) * (float(interes) / 100)
            total_pagar = float(monto) + total_interes
            valor_cuota = total_pagar / int(cuotas)
            
            # Generar códigos de ID correlativos de forma automática
            nuevo_id_cliente = len(df_clientes) + 1
            nuevo_id_credito = len(df_creditos) + 1
            
            # 1. Crear fila de Clientes
            nueva_fila_cli = pd.DataFrame([{
                "ID_Cliente": nuevo_id_cliente, "Nombre": nombre, "Cedula": cedula,
                "Telefono": telefono, "Direccion": direccion, "Fiador_Nombre": f_nombre,
                "Fiador_Cedula": f_cedula, "Fiador_Telefono": f_telefono, "Fiador_Direccion": f_direccion
            }])
            
            # 2. Crear fila de Crédito
            nueva_fila_cre = pd.DataFrame([{
                "ID_Credito": nuevo_id_credito, "ID_Cliente": nuevo_id_cliente, "Monto": monto,
                "Interes": interes, "Modalidad": frecuencia, "Cuotas": cuotas,
                "Total_Pagar": total_pagar, "Valor_Cuota": valor_cuota, "Fecha_Inicio": datetime.now().strftime("%d/%m/%Y")
            }])
            
            # 3. LÓGICA DE CALENDARIO: Generación automática de fechas de vencimiento de las cuotas
            lista_nuevos_pagos = []
            fecha_actual = datetime.now()
            
            for i in range(1, int(cuotas) + 1):
                if frecuencia == "Diario":
                    fecha_actual += timedelta(days=1)
                elif frecuencia == "Semanal":
                    fecha_actual += timedelta(weeks=1)
                elif frecuencia == "Quincenal":
                    fecha_actual += timedelta(days=15)
                elif frecuencia == "Mensual":
                    fecha_actual += timedelta(days=30)
                
                nuevo_id_pago = len(df_pagos) + len(lista_nuevos_pagos) + 1
                lista_nuevos_pagos.append({
                    "ID_Pago": nuevo_id_pago,
                    "ID_Credito": nuevo_id_credito,
                    "Num_Cuota": i,
                    "Fecha_Vencimiento": fecha_actual.strftime("%d/%m/%Y"),
                    "Monto_Cuota": valor_cuota,
                    "Estado": "Pendiente",
                    "Abonado": 0.0,
                    "Fecha_Real_Pago": ""
                })
            
            nueva_tabla_pagos = pd.DataFrame(lista_nuevos_pagos)
            
            # Unir lo nuevo con lo viejo y subir todo sincronizado a Google Sheets
            df_clientes = pd.concat([df_clientes, nueva_fila_cli], ignore_index=True)
            df_creditos = pd.concat([df_creditos, nueva_fila_cre], ignore_index=True)
            df_pagos = pd.concat([df_pagos, nueva_tabla_pagos], ignore_index=True)
            
            conn.update(worksheet="CLIENTES", data=df_clientes)
            conn.update(worksheet="CREDITOS", data=df_creditos)
            conn.update(worksheet="PAGOS", data=df_pagos)
            
            st.success(f"🎉 ¡Crédito de {nombre} aprobado! Las {cuotas} cuotas se crearon en el calendario.")
            st.markdown(f"""
            * **Valor por Cuota:** {cuotas} pagos de **${valor_cuota:,.0f}** ({frecuencia})
            * **Total Neto a Recaudar:** ${total_pagar:,.0f}
            """)
            st.rerun()
        else:
            st.error("🚨 Revisa los campos obligatorios (*) y asegúrate de ingresar un monto válido.")
