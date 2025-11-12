# app.py
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd
import altair as alt
import json
import io

st.set_page_config(layout="wide", page_title="Interações - Dashboard", initial_sidebar_state="expanded")

# --------------------------
# Carregamento do Google Sheets
# --------------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    gcp_key = json.loads(st.secrets["gcp_key"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(gcp_key, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key("1VLps1Bi6lc2NX1Bk227ctqBpT0prJa3g4I6KrlXotfo").sheet1
    dados = sheet.get_all_records()
except Exception as e:
    st.error("❌ Erro ao conectar com a planilha. Verifique as credenciais em st.secrets.")
    st.stop()

# DataFrame
df = pd.DataFrame(dados)

# Validação de colunas esperadas
expected_cols = ["data_hora", "segurado", "canal", "conteudo", "tipo_evento", "integracao"]
missing = [c for c in expected_cols if c not in df.columns]
if missing:
    st.error(f"Colunas faltando na planilha: {missing}")
    st.stop()

# Normaliza strings e datas
df["segurado"] = df["segurado"].astype(str).str.strip()
df["canal"] = df["canal"].astype(str).str.strip()
df["conteudo"] = df["conteudo"].astype(str).str.strip()
df["tipo_evento"] = df["tipo_evento"].astype(str).str.strip()
df["integracao"] = df["integracao"].astype(str).str.strip()

def try_parse_date(col):
    try:
        return pd.to_datetime(col, format="%d/%m/%Y %H:%M")
    except:
        try:
            return pd.to_datetime(col)
        except:
            return pd.NaT

df["data_hora"] = try_parse_date(df["data_hora"])
if df["data_hora"].isna().any():
    st.warning("Algumas datas não foram reconhecidas e ficaram vazias (NaT). Verifique o formato na planilha.")

# Colunas auxiliares
df["ano_mes"] = df["data_hora"].dt.to_period("M")
df["conteudo_lower"] = df["conteudo"].str.lower()

# --------------------------
# Utilitários
# --------------------------
def interpretar_status(texto):
    t = texto.lower()
    if "reunião marcada" in t or "reunião agendada" in t or "agendada" in t:
        return "✅ Reunião marcada"
    if "solicitei retorno" in t or "aguardando retorno" in t or "aguardando disponibilidade" in t:
        return "⏳ Aguardando retorno"
    if "enviei e-mail" in t or "e-mail enviado" in t or "contato inicial" in t:
        return "📨 Contato inicial"
    if "finalizado" in t or "concluído" in t:
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
        ).properties(title=titulo, width=600, height=350)
    else:
        chart = alt.Chart(df_plot).mark_bar().encode(
            x=alt.X("categoria:N", sort='-y'),
            y=alt.Y("quantidade:Q")
        ).properties(title=titulo, width=600, height=350)
    return chart

def baixar_csv(df_in):
    buffer = io.StringIO()
    df_in.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8")

# --------------------------
# Layout - abas (sem Conversacional)
# --------------------------
aba = st.sidebar.radio("Escolha uma aba:", ["📊 Análise por filtros", "📁 Dados completos"])

# --------------------------
# Aba: Análise por filtros
# --------------------------
if aba == "📊 Análise por filtros":
    st.title("📊 Análise de Interações com Segurados")

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

    # Aplica filtros
    filtro = df.copy()
    if cliente_filtro:
        filtro = filtro[filtro["segurado"].str.lower() == cliente_filtro.lower()]
    if integracao_filtro:
        filtro = filtro[filtro["integracao"].str.lower() == integracao_filtro.lower()]
    if tipo_filtro and tipo_filtro != "Todos":
        filtro = filtro[filtro["tipo_evento"] == tipo_filtro]
    if periodo_de:
        filtro = filtro[filtro["data_hora"] >= pd.to_datetime(periodo_de)]
    if periodo_ate:
        filtro = filtro[filtro["data_hora"] <= pd.to_datetime(periodo_ate)]

    if filtro.empty:
        st.warning("⚠️ Nenhuma interação encontrada com esses filtros.")
    else:
        # Métricas
        total = len(filtro)
        primeira = filtro["data_hora"].min()
        ultima = filtro["data_hora"].max()
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
            # Gráficos: canal e integração (Altair)
            col_a, col_b = st.columns(2)
            with col_a:
                cont_canal = filtro["canal"].value_counts()
                st.write("Interações por canal")
                st.altair_chart(gerar_bar_chart(cont_canal, "Interações por canal"), use_container_width=True)
            with col_b:
                cont_int = filtro["integracao"].value_counts()
                st.write("Interações por integração")
                st.altair_chart(gerar_bar_chart(cont_int, "Interações por integração"), use_container_width=True)

        # Status interpretado
        st.subheader("Status (interpretação automática)")
        ultimas_three = filtro.sort_values("data_hora", ascending=False).head(3)
        if cliente_filtro:
            conteudos = " ".join(ultimas_three["conteudo"].astype(str))
            st.write(f"Status atual para **{cliente_filtro}**: ", interpretar_status(conteudos))
        else:
            status_series = filtro["conteudo"].apply(interpretar_status).value_counts().head(10)
            st.table(status_series.rename_axis("Status").reset_index(name="Ocorrências"))

        # Mostrar últimas interações
        st.subheader("Últimas interações")
        cols_display = ["data_hora", "segurado", "canal", "tipo_evento", "integracao", "conteudo"]
        st.dataframe(filtro.sort_values("data_hora", ascending=False)[cols_display].head(50), height=320)

        # Gráfico adicional: interações por mês
        st.subheader("Interações por mês")
        cont_mes = filtro.groupby(filtro["data_hora"].dt.to_period("M")).size().sort_index()
        cont_mes.index = cont_mes.index.astype(str)
        st.altair_chart(gerar_bar_chart(cont_mes, "Interações por mês"), use_container_width=True)

        # Download CSV desta seleção
        csv_bytes = baixar_csv(filtro[cols_display])
        st.download_button("📥 Download dos dados filtrados (CSV)", data=csv_bytes, file_name="interacoes_filtradas.csv", mime="text/csv")

# --------------------------
# Aba: Dados completos
# --------------------------
elif aba == "📁 Dados completos":
    st.title("📁 Dados completos da planilha")
    st.write("Visualize e baixe todos os campos da planilha. Use filtros e ordenações no DataFrame exibido.")
    cols = st.multiselect("Colunas a exibir", options=df.columns.tolist(), default=expected_cols)
    ordenar = st.selectbox("Ordenar por", options=["Nenhum"] + df.columns.tolist(), index=0)
    asc = st.checkbox("Ordem crescente", value=False)
    mostrar = st.number_input("Quantidade de linhas a mostrar", min_value=10, max_value=10000, value=200, step=10)

    tabela_full = df[cols].copy()
    if ordenar != "Nenhum":
        tabela_full = tabela_full.sort_values(by=ordenar, ascending=asc)
    st.dataframe(tabela_full.head(mostrar), height=500)

    csv_bytes_all = baixar_csv(tabela_full)
    st.download_button("📥 Download dados completos (CSV)", data=csv_bytes_all, file_name="dados_completos.csv", mime="text/csv")

# --------------------------
# Rodapé / dicas
# --------------------------
st.sidebar.markdown("---")
st.sidebar.write("Dicas de uso:")
st.sidebar.write("- Use a aba Análise por filtros para consultas rápidas e gráficos.")
st.sidebar.write("- Use a aba Dados completos para exportar todo o conteúdo da planilha.")
