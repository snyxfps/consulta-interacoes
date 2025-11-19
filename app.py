import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
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

# Conversão robusta de datas (aceita serial Excel e strings)
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

# cria colunas derivadas no DataFrame original (antes de renomear colunas)
df["data_hora_parsed"] = df["data_hora"].apply(parse_date_value)
df["data_hora_fmt"] = df["data_hora_parsed"].dt.strftime("%d/%m/%Y %H:%M")
df.loc[df["data_hora_parsed"].isna(), "data_hora_fmt"] = ""
df["ano_mes"] = df["data_hora_parsed"].dt.to_period("M")
df["conteudo_lower"] = df["conteudo"].str.lower()

# --------------------------
# UI: topo (Abrir abas + Recarregar dados robusto)
# --------------------------
if "show_tabs" not in st.session_state:
    st.session_state.show_tabs = False

col1, col2, col3, col4 = st.columns([1,6,2,1])
with col2:
    if st.button("Abrir abas"):
        st.session_state.show_tabs = True

with col3:
    if st.button("🔄 Recarregar dados"):
        try:
            st.session_state.clear()
            st.experimental_rerun()
        except AttributeError:
            st.session_state["_needs_reload"] = True
            st.stop()
        except Exception:
            st.error("Falha ao tentar recarregar automaticamente. Recarregue a página manualmente.")
            with st.expander("Detalhes do erro (debug)"):
                st.text(traceback.format_exc())
            st.stop()

if st.session_state.get("_needs_reload"):
    st.info("Recarregamento pendente. Recarregue a página (F5) para aplicar as mudanças.")
    del st.session_state["_needs_reload"]

if not st.session_state.show_tabs:
    st.sidebar.success("📄 Páginas carregadas no menu →")
    st.markdown("<br/><br/><h2 style='text-align:center'>Clique em Abrir abas para acessar o painel principal</h2>", unsafe_allow_html=True)
    st.stop()

# --------------------------
# Prepare tabela_full com colunas únicas
# --------------------------
tabela_full = df.copy()
# renomeia coluna de exibição e garante unicidade de colunas
if "data_hora_fmt" in tabela_full.columns:
    tabela_full = tabela_full.rename(columns={"data_hora_fmt": "data_hora"})
tabela_full = make_unique_cols(tabela_full)
available_cols = tabela_full.columns.tolist()

# cria coluna datetime consistente para filtros/ordenacao (não dependemos do nome original)
# tenta localizar a coluna exibida de data_hora (pode ser 'data_hora' ou 'data_hora_1' etc) e a parsed original
def find_col(prefix, cols):
    for c in cols:
        if c == prefix or c.startswith(prefix + "_"):
            return c
    return None

# localiza coluna que contém os valores originais de data_hora (após make_unique_cols)
col_data_display = find_col("data_hora", tabela_full.columns)
# preferir coluna já parseada se existir (data_hora_parsed ou data_hora_parsed_1)
col_parsed = find_col("data_hora_parsed", tabela_full.columns)
# se não existir parsed (raro), criar a partir da coluna display
if col_parsed is None and col_data_display is not None:
    tabela_full["data_hora_parsed_internal"] = pd.to_datetime(tabela_full[col_data_display], dayfirst=True, errors='coerce')
    col_parsed = "data_hora_parsed_internal"
elif col_parsed is None:
    tabela_full["data_hora_parsed_internal"] = pd.NaT
    col_parsed = "data_hora_parsed_internal"

# --------------------------
# Seção principal: seleção de abas
# --------------------------
aba = st.radio("Escolha uma aba:", ["Análise por filtros", "Dados completos"], horizontal=True)

# localizar outras colunas fundamentais (após make_unique_cols)
col_seg = find_col("segurado", tabela_full.columns)
col_canal = find_col("canal", tabela_full.columns)
col_conteudo = find_col("conteudo", tabela_full.columns)
col_tipo = find_col("tipo_evento", tabela_full.columns)
col_integr = find_col("integracao", tabela_full.columns)

# --------------------------
# A - Análise por filtros (correção: usa coluna datetime interna para filtrar)
# --------------------------
if aba == "Análise por filtros":
    st.title("Análise de Interações com Segurados")

    # Lista de segurados única e ordenada para seleção pesquisável
    segurados = sorted([s for s in tabela_full[col_seg].dropna().astype(str).unique()]) if col_seg else []
    segurados_options = ["Todos"] + segurados

    with st.expander("Filtros rápidos", expanded=True):
        col1, col2, col3 = st.columns([3, 2, 2])
        with col1:
            cliente_filtro = st.selectbox("Filtrar por cliente (escolha pesquisando):", options=segurados_options, index=0)
        with col2:
            integracao_filtro = st.text_input("Filtrar por integração (ex: RCV):").strip()
        with col3:
            tipos = []
            if col_tipo:
                tipos = sorted(tabela_full[col_tipo].dropna().astype(str).unique().tolist())
            tipo_filtro = st.selectbox("Filtrar por tipo de evento", options=["Todos"] + tipos)
        st.write("")  # espaçamento
        use_date_filter = st.checkbox("Ativar filtro por data", value=False)
        min_date = pd.to_datetime(tabela_full[col_parsed], errors='coerce').min()
        max_date = pd.to_datetime(tabela_full[col_parsed], errors='coerce').max()
        if pd.isna(min_date):
            min_date = date.today()
        if pd.isna(max_date):
            max_date = date.today()
        if use_date_filter:
            col4, col5 = st.columns([1, 1])
            with col4:
                periodo_de = st.date_input("Data inicial (a partir de)", value=min_date.date())
            with col5:
                periodo_ate = st.date_input("Data final (até)", value=max_date.date())
        else:
            periodo_de = None
            periodo_ate = None

    filtro = tabela_full.copy()

    if cliente_filtro and cliente_filtro != "Todos" and col_seg:
        filtro = filtro[filtro[col_seg].astype(str).str.lower() == cliente_filtro.lower()]
    if integracao_filtro and col_integr:
        filtro = filtro[filtro[col_integr].astype(str).str.lower() == integracao_filtro.lower()]
    if tipo_filtro and tipo_filtro != "Todos" and col_tipo:
        filtro = filtro[filtro[col_tipo].astype(str) == tipo_filtro]

    # filtros de data: usar a coluna parsed interna (col_parsed)
    if periodo_de is not None and col_parsed:
        start_dt = pd.to_datetime(periodo_de)
        filtro = filtro[pd.to_datetime(filtro[col_parsed], errors='coerce') >= start_dt]
    if periodo_ate is not None and col_parsed:
        end_dt = pd.to_datetime(periodo_ate) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        filtro = filtro[pd.to_datetime(filtro[col_parsed], errors='coerce') <= end_dt]

    if filtro.empty:
        st.warning("Nenhuma interação encontrada com esses filtros.")
    else:
        total = len(filtro)
        try:
            primeira = pd.to_datetime(filtro[col_parsed], errors='coerce').min() if col_parsed else pd.NaT
            ultima = pd.to_datetime(filtro[col_parsed], errors='coerce').max() if col_parsed else pd.NaT
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
        if col_parsed:
            ultimas_three = filtro.assign(_parsed=pd.to_datetime(filtro[col_parsed], errors='coerce')).sort_values("_parsed", ascending=False).head(3)
        else:
            ultimas_three = filtro.head(3)
        if cliente_filtro and cliente_filtro != "Todos" and not ultimas_three.empty and col_conteudo:
            conteudos = " ".join(ultimas_three[col_conteudo].astype(str))
            st.write(f"Status atual para **{cliente_filtro}**: ", interpretar_status(conteudos))
        else:
            if col_conteudo:
                status_series = filtro[col_conteudo].apply(interpretar_status).value_counts().head(10)
                st.table(status_series.rename_axis("Status").reset_index(name="Ocorrências"))

        st.subheader("Últimas interações")
        display_cols = [c for c in [col_data_display, col_seg, col_canal, col_tipo, col_integr, col_conteudo] if c]
        if col_parsed:
            filtro_sorted = filtro.assign(_parsed=pd.to_datetime(filtro[col_parsed], errors='coerce')).sort_values("_parsed", ascending=False)
            st.dataframe(filtro_sorted[display_cols].head(50), height=480)
        else:
            st.dataframe(filtro.sort_values(by=display_cols[0], ascending=False)[display_cols].head(50), height=480)

        st.subheader("Interações por mês")
        if col_parsed:
            cont_mes = pd.to_datetime(filtro[col_parsed], errors='coerce').dt.to_period("M").value_counts().sort_index()
            cont_mes.index = cont_mes.index.astype(str)
            st.altair_chart(gerar_bar_chart(cont_mes, "Interações por mês"), use_container_width=True)

        # prepara CSV padronizando colunas de saída quando possível
        output_df = filtro.copy()
        out_cols_map = {}
        for logical, real_prefix in [("data_hora", "data_hora"), ("segurado", "segurado"), ("canal", "canal"),
                                     ("conteudo", "conteudo"), ("tipo_evento", "tipo_evento"), ("integracao", "integracao")]:
            real = find_col(real_prefix, tabela_full.columns)
            if real and real in output_df.columns:
                out_cols_map[real] = logical
        if out_cols_map:
            csv_df = output_df[list(out_cols_map.keys())].rename(columns=out_cols_map)
        else:
            csv_df = output_df
        csv_bytes = baixar_csv_bytes(csv_df)
        st.download_button("Download dos dados filtrados (CSV)", data=csv_bytes, file_name="interacoes_filtradas.csv", mime="text/csv")

# --------------------------
# B - Dados completos (ordenação/filtragem por datetime corrigida)
# --------------------------
elif aba == "Dados completos":
    st.title("Dados completos da planilha")

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

    tabela_display = tabela_full.copy()
    # se o usuário pedir para ordenar por data_hora, garantir que usamos a coluna parsed para ordenar
    if ordenar != "Nenhum":
        if ordenar.startswith("data_hora") and col_parsed:
            tabela_display = tabela_display.assign(_parsed=pd.to_datetime(tabela_display[col_parsed], errors='coerce')).sort_values("_parsed", ascending=asc)
        elif ordenar in tabela_display.columns:
            tabela_display = tabela_display.sort_values(by=ordenar, ascending=asc)

    if not existing:
        st.info("Nenhuma coluna válida selecionada. Selecione colunas para visualizar a tabela.")
    else:
        st.dataframe(tabela_display[existing].head(mostrar), height=640)

    download_cols = [c for c in ["data_hora", "segurado", "canal", "conteudo", "tipo_evento", "integracao"] if c in tabela_full.columns]
    csv_bytes_all = baixar_csv_bytes(tabela_full[download_cols])
    st.download_button("Download dados completos (CSV)", data=csv_bytes_all, file_name="dados_completos.csv", mime="text/csv")
