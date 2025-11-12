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

        st.markdown(f"""
**🔎 Total de interações:** {total}  
**📅 Primeira interação:** {primeira.strftime('%d/%m/%Y %H:%M')}  
**📅 Última interação:** {ultima.strftime('%d/%m/%Y %H:%M')}  
**⏳ Tempo desde a primeira:** {dias_desde_primeira} dias  
**📨 Canal mais utilizado:** {canal_mais_usado}
""")

        st.subheader("📬 Percentual por canal")
        st.dataframe(canais_pct)

        st.subheader("📈 Percentual por tipo de evento")
        st.dataframe(tipos_pct)

        st.subheader("🔗 Percentual por integração")
        st.dataframe(integracoes_pct)

        st.subheader("📆 Interações por mês")
        st.dataframe(por_mes)
