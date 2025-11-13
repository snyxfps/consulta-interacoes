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
SHEET_ID = "1331BNS5F0lOsIT9fNDds4Jro_nMYvfeWGVeqGhgj_BE"  # ajuste se necessário
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
# Utilitários gerais
# --------------------------
def make_unique_cols(df):
    cols = []
    seen = {}
    for c in df.columns:
        if c in seen:
            seen[c] += 1
            new = f"{c}_{seen[c]}"
        else:
            seen[c] = 0
            new = c
        cols.append(new)
    df = df.copy()
    df.columns = cols
    return df

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

# --------------------------
# Leitura e pré-processamento
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
        sr = s.replace(",", ".")
        if all(ch.isdigit() or ch == '.' for ch in sr):
            return excel_serial_to_datetime(float(sr))
    except:
        pass
    try:
        return pd.to_datetime(s, dayfirst=True, errors='coerce')
    except:
        return pd.NaT

df["data_hora_parsed"] = df["data_hora"].apply(parse_date_value)
df["data_hora_fmt"] = df["data_hora_parsed"].dt.strftime("%d/%m/%Y %H:%M")
df.loc[df["data_hora_parsed"].isna(), "data_hora_fmt"] = ""
df["ano_mes"] = df["data_hora_parsed"].dt.to_period("M")
df["conteudo_lower"] = df["conteudo"].str.lower()

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
# Prepare tabela_full com colunas únicas para evitar Duplicate column names
# --------------------------
tabela_full = df.copy().rename(columns={"data_hora_fmt": "data_hora"})
tabela_full = make_unique_cols(tabela_full)  # corrige colunas duplicadas se houver

available_cols = tabela_full.columns.tolist()

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
            # tenta mapear tipo_evento correto (pode ter sido renomeado por make_unique_cols)
            tipo_candidates = [c for c in tabela_full.columns if c.startswith("tipo_evento")]
            tipos = []
            if tipo_candidates:
                # coleta valores do primeiro matching column
                tipos = sorted(tabela_full[tipo_candidates[0]].dropna().unique().tolist())
            tipo_filtro = st.selectbox("Filtrar por tipo de evento", options=["Todos"] + tipos)

        col4, col5 = st.columns([1, 1])
        with col4:
            periodo_de = st.date_input("Data inicial (a partir de)", value=None)
        with col5:
            periodo_ate = st.date_input("Data final (até)", value=None)

    # Para filtros, precisamos referenciar as colunas reais dentro de tabela_full
    # localizar colunas correspondentes (primeira ocorrência)
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

    filtro = tabela_full.copy()

    if cliente_filtro and col_seg:
        filtro = filtro[filtro[col_seg].str.lower() == cliente_filtro.lower()]
    if integracao_filtro and col_integr:
        filtro = filtro[filtro[col_integr].str.lower() == integracao_filtro.lower()]
    if tipo_filtro and tipo_filtro != "Todos" and col_tipo:
        filtro = filtro[filtro[col_tipo] == tipo_filtro]
    if periodo_de and col_data:
        filtro = filtro[pd.to_datetime(filtro[col_data], dayfirst=True, errors='coerce') >= pd.to_datetime(periodo_de)]
    if periodo_ate and col_data:
        filtro = filtro[pd.to_datetime(filtro[col_data], dayfirst=True, errors='coerce') <= pd.to_datetime(periodo_ate) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)]

    if filtro.empty:
        st.warning("Nenhuma interação encontrada com esses filtros.")
    else:
        total = len(filtro)
        try:
            primeira = pd.to_datetime(filtro[col_data], dayfirst=True, errors='coerce').min() if col_data else pd.NaT
            ultima = pd.to_datetime(filtro[col_data], dayfirst=True, errors='coerce').max() if col_data else pd.NaT
        except Exception:
            primeira = ultima = pd.NaT
        dias_desde_primeira = (datetime.now() - primeira).days if pd.notna(primeira) else None
        canal_mais_usado = filtro[col_canal].mode().iloc[0] if (col_canal and not filtro[col_canal].mode().empty) else "—"

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
                if col_canal:
                    cont_canal = filtro[col_canal].value_counts()
                    st.altair_chart(gerar_bar_chart(cont_canal, "Interações por canal"), use_container_width=True)
            with col_b:
                if col_integr:
                    cont_int = filtro[col_integr].value_counts()
                    st.altair_chart(gerar_bar_chart(cont_int, "Interações por integração"), use_container_width=True)

        st.subheader("Status (interpretação automática)")
        ultimas_three = filtro.sort_values(by=col_data, ascending=False).head(3) if col_data else filtro.head(3)
        if cliente_filtro and not ultimas_three.empty and col_conteudo:
            conteudos = " ".join(ultimas_three[col_conteudo].astype(str))
            st.write(f"Status atual para **{cliente_filtro}**: ", interpretar_status(conteudos))
        else:
            if col_conteudo:
                status_series = filtro[col_conteudo].apply(interpretar_status).value_counts().head(10)
                st.table(status_series.rename_axis("Status").reset_index(name="Ocorrências"))

        st.subheader("Últimas interações")
        display_cols = [c for c in [col_data, col_seg, col_canal, col_tipo, col_integr, col_conteudo] if c]
        st.dataframe(filtro.sort_values(by=col_data if col_data else filtro.columns[0], ascending=False)[display_cols].head(50), height=480)

        st.subheader("Interações por mês")
        if col_data:
            cont_mes = pd.to_datetime(filtro[col_data], dayfirst=True, errors='coerce').dt.to_period("M").value_counts().sort_index()
            cont_mes.index = cont_mes.index.astype(str)
            st.altair_chart(gerar_bar_chart(cont_mes, "Interações por mês"), use_container_width=True)

        # prepara CSV: renomeia colunas padrão para saída
        output_df = filtro.copy()
        # garantir colunas de saída padronizadas, se existirem
        out_cols_map = {}
        for logical, real_prefix in [("data_hora", "data_hora"), ("segurado", "segurado"), ("canal", "canal"),
                                     ("conteudo", "conteudo"), ("tipo_evento", "tipo_evento"), ("integracao", "integracao")]:
            real = find_col(real_prefix)
            if real:
                out_cols_map[real] = logical
        if out_cols_map:
            csv_df = output_df[list(out_cols_map.keys())].rename(columns=out_cols_map)
        else:
            csv_df = output_df
        csv_bytes = baixar_csv_bytes(csv_df)
        st.download_button("Download dos dados filtrados (CSV)", data=csv_bytes, file_name="interacoes_filtradas.csv", mime="text/csv")

# --------------------------
# Aba: Dados completos
# --------------------------
elif aba == "Dados completos":
    st.title("Dados completos da planilha")

    # available_cols já criado a partir de tabela_full (único)
    cols = st.multiselect(
        "Colunas a exibir",
        options=available_cols,
        default=[c for c in ["data_hora", "segurado", "canal", "conteudo", "tipo_evento", "integracao"] if c in available_cols]
    )

    ordenar = st.selectbox("Ordenar por", options=["Nenhum"] + available_cols, index=0)
    asc = st.checkbox("Ordem crescente", value=False)
    mostrar = st.number_input("Quantidade de linhas a mostrar", min_value=10, max_value=10000, value=200, step=10)

    requested = cols
    existing = [c for c in requested if c in tabela_full.columns]
    missing_cols = [c for c in requested if c not in tabela_full.columns]
    if missing_cols:
        st.warning(f"As colunas a seguir não existem e foram ignoradas: {missing_cols}")

    if ordenar != "Nenhum" and ordenar in tabela_full.columns:
        tabela_full = tabela_full.sort_values(by=ordenar, ascending=asc)

    if not existing:
        st.info("Nenhuma coluna válida selecionada. Selecione colunas para visualizar a tabela.")
    else:
        st.dataframe(tabela_full[existing].head(mostrar), height=640)

    # download: usa tabela_full mas garante ordem de colunas padrão quando possível
    download_cols = [c for c in ["data_hora", "segurado", "canal", "conteudo", "tipo_evento", "integracao"] if c in tabela_full.columns]
    csv_bytes_all = baixar_csv_bytes(tabela_full[download_cols])
    st.download_button("Download dados completos (CSV)", data=csv_bytes_all, file_name="dados_completos.csv", mime="text/csv")
