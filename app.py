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

# Configuração da página
st.set_page_config(layout="wide", page_title="Interações - Dashboard", initial_sidebar_state="collapsed")

# --------------------------
# Config Google Sheets
# --------------------------
SHEET_ID = "1331BNS5F0lOsIT9fNDds4Jro_nMYvfeWGVeqGhgj_BE"
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

@st.cache_data(ttl=300)
def load_sheet_data():
    """Carrega dados do Google Sheets com cache (5 minutos)."""
    try:
        gcp_key = json.loads(st.secrets["gcp_key"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(gcp_key, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        dados = sheet.get_all_records()
        return pd.DataFrame(dados)
    except Exception:
        st.error("❌ Erro ao conectar com a planilha. Verifique credenciais e permissões.")
        with st.expander("Detalhes do erro (debug)"):
            st.text(traceback.format_exc())
        st.stop()

# --------------------------
# Utilitários
# --------------------------
def make_unique_cols(df):
    """Garante nomes únicos de colunas."""
    df = df.loc[:, ~df.columns.duplicated()].copy()
    return df

def gerar_bar_chart(series: pd.Series, titulo: str, horizontal: bool = False):
    """Gera gráfico de barras com tooltip e cores automáticas."""
    df_plot = series.reset_index()
    df_plot.columns = ["categoria", "quantidade"]
    df_plot["categoria"] = df_plot["categoria"].astype(str)
    chart = alt.Chart(df_plot).mark_bar().encode(
        x=alt.X("quantidade:Q") if horizontal else alt.X("categoria:N", sort='-y'),
        y=alt.Y("categoria:N", sort='-x') if horizontal else alt.Y("quantidade:Q"),
        color=alt.Color("categoria:N", legend=None),
        tooltip=["categoria", "quantidade"]
    ).properties(title=titulo, width=900, height=400)
    return chart

def baixar_csv_bytes(df_in):
    """Gera bytes CSV com separador ';' para compatibilidade Excel PT-BR."""
    buffer = io.StringIO()
    df_in.to_csv(buffer, index=False, sep=";")
    return buffer.getvalue().encode("utf-8")

def interpretar_status(texto):
    """Classifica status com base no conteúdo textual."""
    t = str(texto).lower()
    if any(k in t for k in ["reunião marcada", "agendada", "agendamento"]):
        return "✅ Reunião marcada"
    if any(k in t for k in ["aguardando retorno", "aguardando disponibilidade", "aguardando"]):
        return "⏳ Aguardando retorno"
    if any(k in t for k in ["enviei e-mail", "contato inicial", "email enviado"]):
        return "📨 Contato inicial"
    if any(k in t for k in ["finalizado", "concluído", "encerrado"]):
        return "🏁 Finalizado"
    return "ℹ️ Em andamento"

# --------------------------
# Leitura e pré-processamento
# --------------------------
df = load_sheet_data()

expected_cols = ["data_hora", "segurado", "canal", "conteudo", "tipo_evento", "integracao"]
missing = [c for c in expected_cols if c not in df.columns]
if missing:
    st.error(f"Colunas faltando na planilha: {missing}")
    st.stop()

for c in ["segurado", "canal", "conteudo", "tipo_evento", "integracao"]:
    df[c] = df[c].fillna("").astype(str).str.strip()

# Conversão robusta de datas
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
    if isinstance(v, (int, float, np.integer, np.floating)):
        return excel_serial_to_datetime(v)
    s = str(v).strip().replace(",", ".")
    if all(ch.isdigit() or ch == '.' for ch in s):
        return excel_serial_to_datetime(float(s))
    return pd.to_datetime(s, dayfirst=True, errors='coerce')

df["data_hora_parsed"] = df["data_hora"].apply(parse_date_value)
df["data_hora_fmt"] = df["data_hora_parsed"].dt.strftime("%d/%m/%Y %H:%M").fillna("")
df["ano_mes"] = df["data_hora_parsed"].dt.to_period("M")

# --------------------------
# UI - Topo
# --------------------------
if "show_tabs" not in st.session_state:
    st.session_state.show_tabs = False

col1, col2, col3, col4 = st.columns([1,6,2,1])
with col2:
    if st.button("Abrir abas"):
        st.session_state.show_tabs = True
with col3:
    if st.button("🔄 Recarregar dados"):
        st.cache_data.clear()
        st.session_state.clear()
        st.experimental_rerun()

if not st.session_state.show_tabs:
    st.markdown("<br/><br/><h2 style='text-align:center'>Clique em Abrir abas para começar</h2>", unsafe_allow_html=True)
    st.stop()

# --------------------------
# Dados principais
# --------------------------
tabela_full = make_unique_cols(df.copy())
tabela_full.rename(columns={"data_hora_fmt": "data_hora"}, inplace=True)
available_cols = tabela_full.columns.tolist()

aba = st.radio("Escolha uma aba:", ["Análise por filtros", "Dados completos"], horizontal=True)

# --------------------------
# Aba: Análise por filtros
# --------------------------
if aba == "Análise por filtros":
    st.title("Análise de Interações com Segurados")

    def find_col(prefix):
        for c in tabela_full.columns:
            if c == prefix or c.startswith(prefix + "_"):
                return c
        return None

    col_data = find_col("data_hora")
    col_seg = find_col("segurado")
    col_canal = find_col("canal")
    col_conteudo = find_col("conteudo")
    col_tipo = find_col("tipo_evento")
    col_integr = find_col("integracao")

    segurados = sorted([s for s in tabela_full[col_seg].dropna().astype(str).unique()]) if col_seg else []
    segurados_options = ["Todos"] + segurados

    with st.expander("Filtros rápidos", expanded=True):
        col1, col2, col3 = st.columns([3, 2, 2])
        cliente_filtro = col1.selectbox("Cliente:", segurados_options, index=0)
        integracao_filtro = col2.text_input("Integração (ex: RCV):").strip()
        tipos = sorted(tabela_full[col_tipo].dropna().astype(str).unique().tolist()) if col_tipo else []
        tipo_filtro = col3.selectbox("Tipo de evento:", ["Todos"] + tipos)
        col4, col5 = st.columns([1, 1])
        periodo_de = col4.date_input("Data inicial:", value=None)
        periodo_ate = col5.date_input("Data final:", value=None)

    filtro = tabela_full.copy()
    if cliente_filtro != "Todos":
        filtro = filtro[filtro[col_seg].str.lower() == cliente_filtro.lower()]
    if integracao_filtro:
        filtro = filtro[filtro[col_integr].str.lower() == integracao_filtro.lower()]
    if tipo_filtro != "Todos":
        filtro = filtro[filtro[col_tipo] == tipo_filtro]
    if periodo_de:
        filtro = filtro[pd.to_datetime(filtro[col_data], dayfirst=True, errors='coerce') >= pd.to_datetime(periodo_de)]
    if periodo_ate:
        filtro = filtro[pd.to_datetime(filtro[col_data], dayfirst=True, errors='coerce') <= pd.to_datetime(periodo_ate) + pd.Timedelta(days=1)]

    if filtro.empty:
        st.warning("Nenhuma interação encontrada com esses filtros.")
        st.stop()

    total = len(filtro)
    primeira = pd.to_datetime(filtro[col_data], dayfirst=True, errors='coerce').min()
    ultima = pd.to_datetime(filtro[col_data], dayfirst=True, errors='coerce').max()
    dias_desde_primeira = (datetime.now() - primeira).days if pd.notna(primeira) else None
    canal_mais_usado = filtro[col_canal].mode().iloc[0] if col_canal and not filtro[col_canal].mode().empty else "—"

    left, right = st.columns([2, 3])
    with left:
        st.metric("Total de interações", total)
        st.write(f"🕐 Período: {primeira.strftime('%d/%m/%Y')} → {ultima.strftime('%d/%m/%Y')}")
        if dias_desde_primeira:
            st.write(f"📅 Dias desde a primeira: {dias_desde_primeira}")
        st.write(f"💬 Canal mais usado: **{canal_mais_usado}**")

    with right:
        col_a, col_b = st.columns(2)
        if col_canal:
            st.altair_chart(gerar_bar_chart(filtro[col_canal].value_counts(), "Interações por canal"), use_container_width=True)
        if col_integr:
            st.altair_chart(gerar_bar_chart(filtro[col_integr].value_counts(), "Interações por integração"), use_container_width=True)

    st.subheader("Status automático")
    ultimas = filtro.sort_values(by=col_data, ascending=False).head(3)
    if cliente_filtro != "Todos":
        conteudos = " ".join(ultimas[col_conteudo].astype(str))
        st.write(f"Status atual para **{cliente_filtro}**: {interpretar_status(conteudos)}")
    else:
        status_series = filtro[col_conteudo].apply(interpretar_status).value_counts().head(10)
        st.table(status_series.rename_axis("Status").reset_index(name="Ocorrências"))

    st.subheader("Últimas interações")
    display_cols = [c for c in [col_data, col_seg, col_canal, col_tipo, col_integr, col_conteudo] if c]
    st.dataframe(filtro.sort_values(by=col_data, ascending=False)[display_cols].head(50), height=480)

    st.subheader("Interações por mês")
    cont_mes = pd.to_datetime(filtro[col_data], dayfirst=True, errors='coerce').dt.to_period("M").value_counts().sort_index()
    cont_mes.index = cont_mes.index.astype(str)
    st.altair_chart(gerar_bar_chart(cont_mes, "Interações por mês"), use_container_width=True)

    csv_bytes = baixar_csv_bytes(filtro)
    st.download_button("💾 Download (dados filtrados)", data=csv_bytes, file_name="interacoes_filtradas.csv", mime="text/csv")

# --------------------------
# Aba: Dados completos
# --------------------------
else:
    st.title("Dados completos da planilha")
    cols = st.multiselect("Colunas a exibir", available_cols,
                          default=[c for c in expected_cols if c in available_cols])
    ordenar = st.selectbox("Ordenar por", ["Nenhum"] + available_cols)
    asc = st.checkbox("Ordem crescente", value=False)
    mostrar = st.number_input("Linhas a mostrar", min_value=10, max_value=10000, value=200, step=10)

    if ordenar != "Nenhum":
        tabela_full = tabela_full.sort_values(by=ordenar, ascending=asc)

    st.dataframe(tabela_full[cols].head(mostrar), height=640)
    csv_bytes_all = baixar_csv_bytes(tabela_full[cols])
    st.download_button("💾 Download (dados completos)", data=csv_bytes_all, file_name="dados_completos.csv", mime="text/csv")
