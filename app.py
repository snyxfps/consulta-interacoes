import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd
import json

# Autenticação com Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    gcp_key = json.loads(st.secrets["gcp_key"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(gcp_key, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key("1331BNS5F0lOsIT9fNDds4Jro_nMYvfeWGVeqGhgj_BE").sheet1
    dados = sheet.get_all_records()
except Exception as e:
    st.error("❌ Erro ao conectar com a planilha.")
    st.stop()

df = pd.DataFrame(dados)
try:
    df["data_hora"] = pd.to_datetime(df["data_hora"], format="%d/%m/%Y %H:%M")
except:
    st.error("⚠️ Erro ao interpretar datas.")
    st.stop()

def interpretar_status(texto):
    texto = texto.lower()
    if "reunião marcada" in texto or "agendada" in texto:
        return "✅ Reunião já foi marcada."
    elif "solicitei retorno" in texto or "cobrando disponibilidade" in texto:
        return "⏳ Aguardando retorno para agendar."
    elif "enviei e-mail" in texto or "contato inicial" in texto:
        return "📨 Contato inicial realizado, aguardando resposta."
    elif "finalizado" in texto:
        return "🏁 Processo finalizado."
    else:
        return "ℹ️ Interação em andamento, sem definição clara ainda."

aba = st.sidebar.radio("Escolha uma aba:", ["📊 Análise por filtros", "🗣️ Modo Conversacional"])

if aba == "📊 Análise por filtros":
    st.title("📊 Análise de Interações com Segurados")

    col1, col2 = st.columns(2)
    with col1:
        cliente = st.text_input("Filtrar por cliente (nome exato):").strip().upper()
    with col2:
        integracao = st.text_input("Filtrar por integração (ex: RCV):").strip().upper()

    if st.button("Analisar"):
        filtro = df.copy()
        if cliente:
            filtro = filtro[filtro["segurado"].str.upper() == cliente]
        if integracao:
            filtro = filtro[filtro["integracao"].str.upper() == integracao]

        if filtro.empty:
            st.warning("⚠️ Nenhuma interação encontrada com esses filtros.")
        else:
            total = len(filtro)
            primeira = filtro["data_hora"].min()
            ultima = filtro["data_hora"].max()
            dias_desde_primeira = (datetime.now() - primeira).days
            canal_mais_usado = filtro["canal"].value_counts().idxmax()

            canais_pct = (filtro["canal"].value_counts(normalize=True) * 100).round(1).astype(str) + "%"
            tipos_pct = (filtro["tipo_evento"].value_counts(normalize=True) * 100).round(1).astype(str) + "%"
            integracoes_pct = (filtro["integracao"].value_counts(normalize=True) * 100).round(1).astype(str) + "%"
            por_mes = filtro.groupby(filtro["data_hora"].dt.to_period("M")).size()

            st.markdown(f"""
🔎 **Total de interações:** {total}  
📅 **Primeira interação:** {primeira.strftime('%d/%m/%Y %H:%M')}  
📅 **Última interação:** {ultima.strftime('%d/%m/%Y %H:%M')}  
⏳ **Tempo desde a primeira:** {dias_desde_primeira} dias  
📨 **Canal mais utilizado:** {canal_mais_usado}
""")

            st.subheader("📌 Status atual da interação" if cliente else "📌 Top 3 status mais comuns")
            ultimas = filtro.sort_values(by="data_hora", ascending=False).head(3)
            if cliente:
                conteudos = " ".join(ultimas["conteudo"].astype(str))
                status = interpretar_status(conteudos)
                st.markdown(f"**{status}**")
            else:
                todos_status = filtro["conteudo"].astype(str).apply(interpretar_status)
                top_status = todos_status.value_counts().head(3)
                for s, count in top_status.items():
                    st.markdown(f"- {s} ({count} ocorrências)")

            st.subheader("🕒 Últimas 3 interações")
            colunas = ["data_hora", "canal", "conteudo"]
            if not cliente:
                colunas.insert(1, "segurado")
            st.dataframe(ultimas[colunas])

            st.subheader("📈 Percentual por tipo de evento")
            st.dataframe(tipos_pct)

            st.subheader("📬 Percentual por canal")
            st.dataframe(canais_pct)

            st.subheader("📆 Interações por mês")
            st.dataframe(por_mes)

            st.subheader("🔗 Percentual por integração")
            st.dataframe(integracoes_pct)

elif aba == "🗣️ Modo Conversacional":
    st.title("🗣️ Modo Conversacional")
    pergunta = st.text_input("Digite sua pergunta:")

    if pergunta:
        pergunta_lower = pergunta.lower()
        resposta = ""

        if "status" in pergunta_lower:
            for nome in df["segurado"].unique():
                if nome.lower() in pergunta_lower:
                    filtro = df[df["segurado"].str.lower() == nome.lower()]
                    ultimas = filtro.sort_values(by="data_hora", ascending=False).head(3)
                    conteudos = " ".join(ultimas["conteudo"].astype(str))
                    status = interpretar_status(conteudos)
                    resposta = f"📌 Status atual para **{nome}**:\n\n{status}"
                    break
            if not resposta:
                resposta = "ℹ️ Para responder sobre status, inclua o nome do cliente na pergunta."

        elif "o que foi feito" in pergunta_lower or "últimas interações" in pergunta_lower:
            for nome in df["segurado"].unique():
                if nome.lower() in pergunta_lower:
                    filtro = df[df["segurado"].str.lower() == nome.lower()]
                    ultimas = filtro.sort_values(by="data_hora", ascending=False).head(3)
                    resposta = f"🕒 Últimas interações com **{nome}**:\n\n"
                    for _, row in ultimas.iterrows():
                        resposta += f"- {row['data_hora'].strftime('%d/%m/%Y %H:%M')} via {row['canal']}: {row['conteudo']}\n"
                    break
            if not resposta:
                resposta = "ℹ️ Para mostrar interações, inclua o nome do cliente na pergunta."

        elif any(frase in pergunta_lower for frase in [
            "canal mais usado", "canal que eu mais utilizo", "canal mais utilizado",
            "qual canal eu uso mais", "canal utilizo para tratar", "canal que uso para tratar"
        ]):
            for nome in df["segurado"].unique():
                if nome.lower() in pergunta_lower:
                    filtro = df[df["segurado"].str.lower() == nome.lower()]
                    canal = filtro["canal"].value_counts().idxmax()
                    resposta = f"📨 Canal mais utilizado com **{nome}**: {canal}"
                    break
            if not resposta:
                canal = df["canal"].value_counts().idxmax()
                resposta = f"📨 Canal mais utilizado no geral: {canal}"

        elif "quantas cobranças" in pergunta_lower:
            filtro = df[df["tipo_evento"].str.lower() == "cobrança"]
            por_mes = filtro.groupby(filtro["data_hora"].dt.to_period("M")).size()
            resposta = "📆 Cobranças por mês:\n\n"
            for periodo, qtd in por_mes.items():
                resposta += f"- {periodo.strftime('%b/%Y')}: {qtd}\n"

        else:
            resposta = "🤖 Ainda estou aprendendo a entender esse tipo de pergunta. Tente incluir palavras como 'status', 'últimas interações', 'canal mais usado', ou 'quantas cobranças'."

        st.markdown(resposta)
