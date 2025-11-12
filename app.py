# app.py
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import json
import io

st.set_page_config(layout="wide", page_title="Interações - Dashboard", initial_sidebar_state="expanded")
sns.set_style("whitegrid")

# --------------------------
# Config e carregamento CSV
# --------------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    gcp_key = json.loads(st.secrets["gcp_key"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(gcp_key, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key("1331BNS5F0lOsIT9fNDds4Jro_nMYvfeWGVeqGhgj_BE").sheet1
    dados = sheet.get_all_records()
except Exception as e:
    st.error("❌ Erro ao conectar com a planilha. Verifique as credenciais em st.secrets.")
    st.stop()

# DataFrame
df = pd.DataFrame(dados)

# Checagens básicas e limpeza
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

# Tenta converter data_hora
def try_parse_date(col):
    try:
        return pd.to_datetime(col, format="%d/%m/%Y %H:%M")
    except:
        try:
            return pd.to_datetime(col)  # fallback
        except:
            return pd.NaT

df["data_hora"] = try_parse_date(df["data_hora"])
if df["data_hora"].isna().any():
    st.warning("Algumas datas não foram reconhecidas e ficaram vazias (NaT). Verifique o formato na planilha.")

# Colunas auxiliares
df["ano_mes"] = df["data_hora"].dt.to_period("M")
df["conteudo_lower"] = df["conteudo"].str.lower()

# --------------------------
# Funções utilitárias
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

def gerar_bar_plot(series, titulo, orient="vertical"):
    fig, ax = plt.subplots(figsize=(8, 5))
    if orient == "vertical":
        sns.barplot(x=series.index.astype(str), y=series.values, palette="Blues_d", ax=ax)
        ax.set_xticklabels(ax.get_xticklabels(), rotation=35, ha="right")
        ax.set_xlabel("")
    else:
        sns.barplot(x=series.values, y=series.index.astype(str), palette="Blues_d", ax=ax)
        ax.set_ylabel("")
    ax.set_title(titulo)
    ax.set_ylabel("Quantidade")
    plt.tight_layout()
    return fig

def baixar_csv(df_in):
    buffer = io.StringIO()
    df_in.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8")

# --------------------------
# Layout - abas
# --------------------------
aba = st.sidebar.radio("Escolha uma aba:", ["📊 Análise por filtros", "🗣️ Modo Conversacional", "📁 Dados completos"])

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
            tipo_filtro = st.selectbox("Filtrar por tipo de evento", options=["Todos"] + sorted(df["tipo_evento"].dropna().unique().tolist()))
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
            # Gráficos: canal e integração
            col_a, col_b = st.columns(2)
            with col_a:
                cont_canal = filtro["canal"].value_counts()
                st.write("Interações por canal")
                st.pyplot(gerar_bar_plot(cont_canal, "Interações por canal"))
            with col_b:
                cont_int = filtro["integracao"].value_counts()
                st.write("Interações por integração")
                st.pyplot(gerar_bar_plot(cont_int, "Interações por integração"))

        # Top 3 status ou status atual se filtrado por cliente
        st.subheader("Status (interpretação automática)")
        ultimas_three = filtro.sort_values("data_hora", ascending=False).head(3)
        if cliente_filtro:
            conteudos = " ".join(ultimas_three["conteudo"].astype(str))
            st.write(f"Status atual para **{cliente_filtro}**: ", interpretar_status(conteudos))
        else:
            status_series = filtro["conteudo"].apply(interpretar_status).value_counts().head(10)
            st.table(status_series.rename_axis("Status").reset_index(name="Ocorrências"))

        # Mostrar últimas 10 interações
        st.subheader("Últimas interações")
        cols_display = ["data_hora", "segurado", "canal", "tipo_evento", "integracao", "conteudo"]
        st.dataframe(filtro.sort_values("data_hora", ascending=False)[cols_display].head(50), height=320)

        # Download CSV desta seleção
        csv_bytes = baixar_csv(filtro[cols_display])
        st.download_button("📥 Download dos dados filtrados (CSV)", data=csv_bytes, file_name="interacoes_filtradas.csv", mime="text/csv")

# --------------------------
# Aba: Modo Conversacional
# --------------------------
elif aba == "🗣️ Modo Conversacional":
    st.title("🗣️ Modo Conversacional")
    st.write("Faça perguntas em linguagem natural. Exemplos: 'qual o canal que eu mais utilizo?', 'me mostra gráfico por integração', 'qual integração mais usada', 'o que foi feito com 5 Rodas'.")

    pergunta = st.text_input("Digite sua pergunta:", value="", key="pergunta_input")
    executar = st.button("Enviar pergunta")

    def responde_pergunta(texto):
        t = texto.lower()
        resp_lines = []
        show_table = False
        show_plot = False
        plot_obj = None
        plot_title = ""
        tabela_para_baixar = None

        # Intenção: canal mais usado (geral ou por cliente)
        canal_intents = [
            "canal mais usado", "canal que eu mais utilizo", "canal mais utilizado", "qual canal eu uso mais",
            "canal utilizo para tratar", "me mostra o canal mais usado", "qual o canal que eu mais utilizo"
        ]
        if any(k in t for k in canal_intents):
            # tenta detectar cliente
            cliente_detectado = None
            for nome in df["segurado"].unique():
                if nome.lower() in t:
                    cliente_detectado = nome
                    break
            if cliente_detectado:
                filtro_c = df[df["segurado"].str.lower() == cliente_detectado.lower()]
                if filtro_c.empty:
                    resp_lines.append(f"ℹ️ Não encontrei interações para {cliente_detectado}.")
                else:
                    canal = filtro_c["canal"].mode().iloc[0] if not filtro_c["canal"].mode().empty else "—"
                    resp_lines.append(f"📨 Canal mais utilizado com **{cliente_detectado}**: **{canal}**")
                    # dados e gráfico
                    cont = filtro_c["canal"].value_counts()
                    plot_obj = gerar_bar_plot(cont, f"Interações por canal - {cliente_detectado}")
                    show_plot = True
                    tabela_para_baixar = filtro_c.sort_values("data_hora", ascending=False)[["data_hora","segurado","canal","tipo_evento","integracao","conteudo"]]
            else:
                canal = df["canal"].mode().iloc[0] if not df["canal"].mode().empty else "—"
                resp_lines.append(f"📨 Canal mais utilizado no geral: **{canal}**")
                cont = df["canal"].value_counts()
                plot_obj = gerar_bar_plot(cont, "Interações por canal - Geral")
                show_plot = True
                tabela_para_baixar = df.sort_values("data_hora", ascending=False)[["data_hora","segurado","canal","tipo_evento","integracao","conteudo"]]

            return {"text": "\n".join(resp_lines), "plot": plot_obj, "show_plot": show_plot, "table": tabela_para_baixar}

        # Intenção: integração mais usada
        integration_intents = [
            "qual integração", "integração que eu mais tenho", "qual integracao", "integração mais usada",
            "qual integração eu mais tenho interação", "qual integracao mais usada", "me mostra integração mais usada"
        ]
        if any(k in t for k in integration_intents):
            cliente_detectado = None
            for nome in df["segurado"].unique():
                if nome.lower() in t:
                    cliente_detectado = nome
                    break
            if cliente_detectado:
                filtro_c = df[df["segurado"].str.lower() == cliente_detectado.lower()]
                if filtro_c.empty:
                    resp_lines.append(f"ℹ️ Não encontrei interações para {cliente_detectado}.")
                else:
                    inte = filtro_c["integracao"].mode().iloc[0] if not filtro_c["integracao"].mode().empty else "—"
                    resp_lines.append(f"🔗 Integração mais utilizada com **{cliente_detectado}**: **{inte}**")
                    cont = filtro_c["integracao"].value_counts()
                    plot_obj = gerar_bar_plot(cont, f"Interações por integração - {cliente_detectado}")
                    show_plot = True
                    tabela_para_baixar = filtro_c.sort_values("data_hora", ascending=False)[["data_hora","segurado","canal","tipo_evento","integracao","conteudo"]]
            else:
                inte = df["integracao"].mode().iloc[0] if not df["integracao"].mode().empty else "—"
                resp_lines.append(f"🔗 Integração mais utilizada no geral: **{inte}**")
                cont = df["integracao"].value_counts()
                plot_obj = gerar_bar_plot(cont, "Interações por integração - Geral")
                show_plot = True
                tabela_para_baixar = df.sort_values("data_hora", ascending=False)[["data_hora","segurado","canal","tipo_evento","integracao","conteudo"]]

            return {"text": "\n".join(resp_lines), "plot": plot_obj, "show_plot": show_plot, "table": tabela_para_baixar}

        # Intenção: mostrar gráfico específico por comando
        if "gráfico" in t or "grafico" in t or "me mostra um gráfico" in t or "me mostra gráfico" in t:
            # tenta identificar dimensão
            if "canal" in t:
                cont = df["canal"].value_counts()
                plot_obj = gerar_bar_plot(cont, "Interações por canal - Geral")
                resp_lines.append("📊 Aqui está o gráfico de interações por canal.")
                tabela_para_baixar = df.sort_values("data_hora", ascending=False)[["data_hora","segurado","canal","tipo_evento","integracao","conteudo"]]
                return {"text": "\n".join(resp_lines), "plot": plot_obj, "show_plot": True, "table": tabela_para_baixar}
            if "integração" in t or "integracao" in t:
                cont = df["integracao"].value_counts()
                plot_obj = gerar_bar_plot(cont, "Interações por integração - Geral")
                resp_lines.append("📊 Aqui está o gráfico de interações por integração.")
                tabela_para_baixar = df.sort_values("data_hora", ascending=False)[["data_hora","segurado","canal","tipo_evento","integracao","conteudo"]]
                return {"text": "\n".join(resp_lines), "plot": plot_obj, "show_plot": True, "table": tabela_para_baixar}
            if "mês" in t or "mensal" in t:
                cont = df.groupby(df["data_hora"].dt.to_period("M")).size().sort_index()
                cont.index = cont.index.astype(str)
                plot_obj = gerar_bar_plot(cont, "Interações por mês")
                resp_lines.append("📆 Aqui está o gráfico de interações por mês.")
                tabela_para_baixar = df.sort_values("data_hora", ascending=False)[["data_hora","segurado","canal","tipo_evento","integracao","conteudo"]]
                return {"text": "\n".join(resp_lines), "plot": plot_obj, "show_plot": True, "table": tabela_para_baixar}

        # Intenção: últimas interações / o que foi feito com cliente X
        if "o que foi feito" in t or "últimas interações" in t or "ultimas interacoes" in t or "o que foi feito com" in t:
            cliente_detectado = None
            for nome in df["segurado"].unique():
                if nome.lower() in t:
                    cliente_detectado = nome
                    break
            if not cliente_detectado:
                resp_lines.append("ℹ️ Para mostrar interações informe o nome do cliente na pergunta.")
                return {"text": "\n".join(resp_lines), "show_plot": False, "table": None}
            filtro_c = df[df["segurado"].str.lower() == cliente_detectado.lower()].sort_values("data_hora", ascending=False)
            if filtro_c.empty:
                resp_lines.append(f"ℹ️ Nenhuma interação encontrada para {cliente_detectado}.")
                return {"text": "\n".join(resp_lines), "show_plot": False, "table": None}
            resp_lines.append(f"🕒 Últimas interações com **{cliente_detectado}**:")
            tabela_para_baixar = filtro_c[["data_hora","segurado","canal","tipo_evento","integracao","conteudo"]]
            # inclui primeiras 10 linhas no texto
            for _, row in tabela_para_baixar.head(10).iterrows():
                data_str = row["data_hora"].strftime("%d/%m/%Y %H:%M") if pd.notna(row["data_hora"]) else "s/d"
                resp_lines.append(f"- {data_str} | {row['canal']} | {row['tipo_evento']} | {row['integracao']} | {row['conteudo'][:150]}")
            return {"text": "\n".join(resp_lines), "show_plot": False, "table": tabela_para_baixar}

        # Intenção: quantas cobranças
        if "cobrança" in t or "cobrancas" in t or "quantas cobranças" in t:
            filtro_cobr = df[df["tipo_evento"].str.lower().str.contains("cobrança|cobranca")]
            if filtro_cobr.empty:
                resp_lines.append("ℹ️ Não foram encontradas entradas de cobrança.")
                return {"text": "\n".join(resp_lines), "show_plot": False, "table": None}
            cont = filtro_cobr.groupby(filtro_cobr["data_hora"].dt.to_period("M")).size().sort_index()
            cont.index = cont.index.astype(str)
            plot_obj = gerar_bar_plot(cont, "Cobranças por mês")
            resp_lines.append("📆 Quantidade de cobranças por mês:")
            for per, qtd in cont.items():
                resp_lines.append(f"- {per}: {qtd}")
            tabela_para_baixar = filtro_cobr[["data_hora","segurado","canal","tipo_evento","integracao","conteudo"]]
            return {"text": "\n".join(resp_lines), "plot": plot_obj, "show_plot": True, "table": tabela_para_baixar}

        # Caso não entenda
        resp_lines.append("🤖 Ainda estou aprendendo a entender esse tipo de pergunta. Tente incluir palavras como 'status', 'últimas interações', 'canal', 'integração', 'gráfico', ou 'cobranças'.")
        return {"text": "\n".join(resp_lines), "show_plot": False, "table": None}

    if executar and pergunta.strip():
        result = responde_pergunta(pergunta.strip())
        st.markdown(result["text"])

        if result.get("show_plot") and result.get("plot") is not None:
            st.pyplot(result["plot"])

        if result.get("table") is not None:
            st.subheader("Tabela de dados resultante")
            tabela = result["table"].reset_index(drop=True)
            st.dataframe(tabela, height=300)
            csv_bytes = baixar_csv(tabela)
            st.download_button("📥 Download desses dados (CSV)", data=csv_bytes, file_name="resultado_pergunta.csv", mime="text/csv")

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
st.sidebar.write("- No Modo Conversacional, mencione o nome do cliente para respostas específicas.")
st.sidebar.write("- Termos úteis: canal, integração, gráfico, últimas interações, cobranças, status.")
