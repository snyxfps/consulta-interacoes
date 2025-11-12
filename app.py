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

# Filtro por integração
integracao = st.text_input("Digite o nome da integração (ex: RCV):").strip().upper()

if st.button("Analisar"):
    if not integracao:
        st.warning("Digite o nome da integração para filtrar.")
    else:
        filtro = df[df["integracao"].str.upper() == integracao]

        if filtro.empty:
            st.warning("⚠️ Nenhuma interação encontrada para essa integração.")
        else:
            total = len(filtro)
            primeira = filtro["data_hora"].min()
            ultima = filtro["data_hora"].max()
            dias_desde_primeira = (datetime.now() - primeira).days
            canal_mais_usado = filtro["canal"].value_counts().idxmax()
            tipo_por_mes = filtro.groupby([filtro["data_hora"].dt.to_period("M"), "tipo_evento"]).size().unstack(fill_value=0)
            canais = filtro["canal"].value_counts()
            tipos = filtro["tipo_evento"].value_counts()

            st.markdown(f"""
**🔎 Total de interações:** {total}  
**📅 Primeira interação:** {primeira.strftime('%d/%m/%Y %H:%M')}  
**📅 Última interação:** {ultima.strftime('%d/%m/%Y %H:%M')}  
**⏳ Tempo desde a primeira:** {dias_desde_primeira} dias  
**📨 Canal mais utilizado:** {canal_mais_usado}
""")

            st.subheader("📈 Interações por tipo de evento")
            st.dataframe(tipos)

            st.subheader("📬 Interações por canal")
            st.dataframe(canais)

            st.subheader("📆 Cobranças e Inícios por mês")
            st.dataframe(tipo_por_mes)
