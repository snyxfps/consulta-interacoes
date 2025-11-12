# app.py
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd
import altair as alt
import json
import io
import traceback
import numpy as np

st.set_page_config(layout="wide", page_title="Interações - Dashboard", initial_sidebar_state="collapsed")

# --------------------------
# Config Google Sheets
# --------------------------
SHEET_ID = "1VLps1Bi6lc2NX1Bk227ctqBpT0prJa3g4I6KrlXotfo"  # ajuste se necessário
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def load_sheet_data():
    try:
        gcp_key = json.loads(st.secrets["gcp_key"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(gcp_key, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        dados = sheet.get_all_records()
        return pd.DataFrame(dados)
    except Exception:
        st.error("❌ Erro ao conectar com a planilha. Verifique as credenciais em st.secrets e se o client_email tem permissão de Editor na planilha.")
        with st.expander("Detalhes do erro (apenas para debug)"):
            st.text(traceback.format_exc())
        st.stop()

# --------------------------
# Leitura e validação
# --------------------------
df = load_sheet_data()

expected_cols = ["data_hora", "segurado", "canal", "conteudo", "tipo_evento", "integracao"]
missing = [c for c in expected_cols if c not in df.columns]
if missing:
    st.error(f"Colunas faltando na planilha: {missing}")
    st.stop()

# Normaliza colunas texto
for c in ["segurado", "canal", "conteudo", "tipo_evento", "integracao"]:
    df[c] = df[c].astype(str).str.strip()

# --------------------------
# Datas: conversão robusta (aceita serial Excel ou strings)
# --------------------------
def excel_serial_to_datetime(serial):
    try:
        return pd.to_datetime(float(serial), unit='d', origin='1899-12-30')
    except Exception:
        return pd.NaT

def parse_date_value(v):
    if pd.isna(v) or (isinstance(v, str) and v.strip() == ""):
        return pd.NaT
    if isinstance(v, (pd.Timestamp, datetime)):
        return pd.to_datetime(v)
    try:
        if isinstance(v, (int, float, np.integer, np.floating)):
            return excel_serial_to_datetime(v)
    except:
        pass
    s = str(v).strip()
    try:
        # se for string que representa número serial do Excel
        sr = s.replace(",", ".")
        if all(ch.isdigit() or ch == '.' for ch in sr):
            return excel_serial_to_datetime(float(sr))
    except:
        pass
    try:
        # tenta parse com dayfirst
        return pd.to_datetime(s, dayfirst=True, errors='coerce')
    except:
        return pd.NaT

df["data_hora_parsed"] = df["data_hora"].apply(parse_date_value)
df["data_hora_fmt"] = df["data_hora_parsed"].dt.strftime("%d/%m/%Y %H:%M")
df.loc[df["data_hora_parsed"].isna(), "data_hora_fmt"] = ""
df["ano_mes"] = df["data_hora_parsed"].dt.to_period("M")
df["conteudo_lower"] = df["conteudo"].str.lower()

# --------------------------
# Utilitários
# --------------------------
def interpretar_status(texto):
    t = str(texto).lower()
    if any(k in t for k in ["reunião marcada", "reunião agendada", "agendada", "agendamento"]):
        return "✅ Reunião marcada"
    if any(k in t for k in ["solicitei retorno", "aguardando retorno", "aguardando disponibilidade", "aguardando"]):
        return "⏳ Aguardando retorno"
    if any(k in t for k in ["enviei e-mail", "e-mail enviado", "enviei email", "contato inicial", "primeiro contato"]):
        return "📨 Contato inicial"
    if any(k in t for k in ["finalizado", "concluído", "concluido", "encerrado"]):
        return "🏁 Finalizado"
    return "ℹ️ Em andamento"

def gerar_bar_chart(series: pd.Series, titulo: str, horizontal: bool = False):
    df_plot = series.reset_index()
    df_plot.columns = ["categoria", "quantidade"]
    df_plot["categoria"] = df_plot["categoria"].astype(str)
    if horizontal:
        chart = alt.Chart(df_plot).mark_bar().encode(
            x=alt.X("quantidade:Q"),
            y=alt.Y("categoria:N", sort='-x')
        ).properties(title=titulo, width=900, height=400)
    else:
        chart = alt.Chart(df_plot).mark_bar().encode(
            x=alt.X("categoria:N", sort='-y'),
            y=alt.Y("quantidade:Q")
        ).properties(title=titulo, width=900, height=400)
    return chart

def baixar_csv_bytes(df_in):
    buffer = io.StringIO()
    df_in.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8")

# --------------------------
# UI: botão no topo para abrir seleção de abas
# --------------------------
if "show_tabs" not in st.session_state:
    st.session_state.show_tabs = False

col1, col2, col3 = st.columns([1,8,1])
with col2:
    if st.button("Abrir abas"):
        st.session_state.show_tabs = True

if not st.session_state.show_tabs:
    st.markdown("<br/><br/><h2 style='text-align:center'>Clique em Abrir abas para começar</h2>", unsafe_allow_html=True)
    st.stop()

# --------------------------
# Seção principal: seleção de abas
# --------------------------
aba = st.radio("Escolha uma aba:", ["Análise por filtros", "Dados completos"], horizontal=True)

# --------------------------
# Aba: Análise por filtros
# --------------------------
if aba == "Análise por filtros":
    st.title("Análise de Interações com Segurados")
    with st.expander("Filtros rápidos", expanded=True):
        col1, col2, col3 = st.columns([3, 2, 2])
        with col1:
            cliente_filtro = st.text_input("Filtrar por cliente (nome exato):").strip()
        with col2:
            integracao_filtro = st.text_input("Filtrar por integração (ex: RCV):").strip()
        with col3:
            tipos = sorted(df["tipo_evento"].dropna().unique().tolist())
            tipo_filtro = st.selectbox("Filtrar por tipo de evento", options=["Todos"] + tipos)
        col4, col5 = st.columns([1, 1])
        with col4:
            periodo_de = st.date_input("Data inicial (a partir de)", value=None)
        with col5:
            periodo_ate = st.date_input("Data final (até)", value=None)

    filtro = df.copy()
    if cliente_filtro:
        filtro = filtro[filtro["segurado"].str.lower() == cliente_filtro.lower()]
    if integracao_filtro:
        filtro = filtro[filtro["integracao"].str.lower() == integracao_filtro.lower()]
    if tipo_filtro and tipo_filtro != "Todos":
        filtro = filtro[filtro["tipo_evento"] == tipo_filtro]
    if periodo_de:
        filtro = filtro[filtro["data_hora_parsed"] >= pd.to_datetime(periodo_de)]
    if periodo_ate:
        filtro = filtro[filtro["data_hora_parsed"] <= pd.to_datetime(periodo_ate) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)]

    if filtro.empty:
        st.warning("Nenhuma interação encontrada com esses filtros.")
    else:
        total = len(filtro)
        primeira = filtro["data_hora_parsed"].min()
        ultima = filtro["data_hora_parsed"].max()
        dias_desde_primeira = (datetime.now() - primeira).days if pd.notna(primeira) else None
        canal_mais_usado = filtro["canal"].mode().iloc[0] if not filtro["canal"].mode().empty else "—"

        left, right = st.columns([2, 3])
        with left:
            st.metric("Total de interações", total)
            if pd.notna(primeira):
                st.write("Primeira interação:", primeira.strftime("%d/%m/%Y %H:%M"))
                st.write("Última interação:", ultima.strftime("%d/%m/%Y %H:%M"))
                st.write("Dias desde a primeira:", dias_desde_primeira)
            st.write("Canal mais utilizado:", f"**{canal_mais_usado}**")

        with right:
            col_a, col_b = st.columns(2)
            with col_a:
                cont_canal = filtro["canal"].value_counts()
                st.altair_chart(gerar_bar_chart(cont_canal, "Interações por canal"), use_container_width=True)
            with col_b:
                cont_int = filtro["integracao"].value_counts()
                st.altair_chart(gerar_bar_chart(cont_int, "Interações por integração"), use_container_width=True)

        st.subheader("Status (interpretação automática)")
        ultimas_three = filtro.sort_values("data_hora_parsed", ascending=False).head(3)
        if cliente_filtro:
            conteudos = " ".join(ultimas_three["conteudo"].astype(str))
            st.write(f"Status atual para **{cliente_filtro}**: ", interpretar_status(conteudos))
        else:
            status_series = filtro["conteudo"].apply(interpretar_status).value_counts().head(10)
            st.table(status_series.rename_axis("Status").reset_index(name="Ocorrências"))

        st.subheader("Últimas interações")
        cols_display = ["data_hora_fmt", "segurado", "canal", "tipo_evento", "integracao", "conteudo"]
        st.dataframe(filtro.sort_values("data_hora_parsed", ascending=False)[cols_display].head(50), height=480)

        st.subheader("Interações por mês")
        cont_mes = filtro.groupby(filtro["data_hora_parsed"].dt.to_period("M")).size().sort_index()
        cont_mes.index = cont_mes.index.astype(str)
        st.altair_chart(gerar_bar_chart(cont_mes, "Interações por mês"), use_container_width=True)

        csv_bytes = baixar_csv_bytes(filtro.rename(columns={"data_hora_fmt": "data_hora"})[["data_hora","segurado","canal","conteudo","tipo_evento","integracao"]])
        st.download_button("Download dos dados filtrados (CSV)", data=csv_bytes, file_name="interacoes_filtradas.csv", mime="text/csv")

# --------------------------
# Aba: Dados completos
# --------------------------
elif aba == "Dados completos":
    st.title("Dados completos da planilha")
    cols = st.multiselect("Colunas a exibir", options=df.columns.tolist(), default=["data_hora_fmt","segurado","canal","conteudo","tipo_evento","integracao"])
    ordenar = st.selectbox("Ordenar por", options=["Nenhum"] + df.columns.tolist(), index=0)
    asc = st.checkbox("Ordem crescente", value=False)
    mostrar = st.number_input("Quantidade de linhas a mostrar", min_value=10, max_value=10000, value=200, step=10)

    tabela_full = df.copy().rename(columns={"data_hora_fmt":"data_hora"})
    if ordenar != "Nenhum":
        tabela_full = tabela_full.sort_values(by=ordenar, ascending=asc)
    st.dataframe(tabela_full[cols].head(mostrar), height=640)

    csv_bytes_all = baixar_csv_bytes(tabela_full[["data_hora","segurado","canal","conteudo","tipo_evento","integracao"]])
    st.download_button("Download dados completos (CSV)", data=csv_bytes_all, file_name="dados_completos.csv", mime="text/csv")
