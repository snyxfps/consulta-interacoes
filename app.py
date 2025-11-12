import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd
import json

# Autenticação com Google Sheets via segredo
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    gcp_key = json.loads(st.secrets["gcp_key"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(gcp_key, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key("1331BNS5F0lOsIT9fNDds4Jro_nMYvfeWGVeqGhgj_BE").sheet1
    dados = sheet.get_all_records()
except Exception as e:
    st.error("❌ Erro ao conectar com a planilha. Verifique a chave e permissões.")
    st.stop()

# Converte para DataFrame
df = pd.DataFrame(dados)

# Converte data_hora para datetime
try:
    df["data_hora"] = pd.to_datetime(df["data_hora"], format="%d/%m/%Y %H:%M")
except:
    st.error("⚠️ Erro ao interpretar datas. Verifique o formato na planilha.")
    st.stop()

# Interface
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

        # 🔝 Informações principais no topo
        st.markdown(f"""
🔎 **Total de interações:** {total}  
📅 **Primeira interação:** {primeira.strftime('%d/%m/%Y %H:%M')}  
📅 **Última interação:** {ultima.strftime('%d/%m/%Y %H:%M')}  
⏳ **Tempo desde a primeira:** {dias_desde_primeira} dias  
📨 **Canal mais utilizado:** {canal_mais_usado}
""")

        # 📌 Status atual ou top 3 status
        st.subheader("📌 Status atual da interação" if cliente else "📌 Top 3 status mais comuns")

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

        # 🕒 Últimas 3 interações
        st.subheader("🕒 Últimas 3 interações")
        colunas = ["data_hora", "canal", "conteudo"]
        if not cliente:
            colunas.insert(1, "segurado")
        st.dataframe(ultimas[colunas])

        # 📈 Percentual por tipo de evento
        st.subheader("📈 Percentual por tipo de evento")
        st.dataframe(tipos_pct)

        # 📬 Percentual por canal
        st.subheader("📬 Percentual por canal")
        st.dataframe(canais_pct)

        # 📆 Interações por mês
        st.subheader("📆 Interações por mês")
        st.dataframe(por_mes)

        # 🔗 Percentual por integração
        st.subheader("🔗 Percentual por integração")
        st.dataframe(integracoes_pct)
