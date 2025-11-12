import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# Autenticação via segredo do Streamlit
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
gcp_key = json.loads(st.secrets["gcp_key"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(gcp_key, scope)
client = gspread.authorize(creds)

# Abre a planilha
sheet = client.open_by_key("1331BNS5F0lOsIT9fNDds4Jro_nMYvfeWGVeqGhgj_BE").sheet1
dados = sheet.get_all_records()

# Interface web
st.title("🔍 Consulta de Interações com Segurados")
pergunta = st.text_input("Digite sua pergunta:")

def buscar_interacoes(pergunta, dados):
    pergunta = pergunta.lower()
    resultados = []
    for linha in dados:
        texto = f"{linha['segurado']} {linha['canal']} {linha['data_hora']} {linha['conteudo']} {linha['tipo_evento']} {linha['integracao']}".lower()
        if any(p in texto for p in pergunta.split()):
            resultados.append(linha)
    if resultados:
        ult = sorted(resultados, key=lambda x: x['data_hora'], reverse=True)[0]
        return f"🗓️ {ult['data_hora']}\n📨 {ult['canal']}\n💬 {ult['conteudo']}"
    else:
        return "⚠️ Nenhuma interação encontrada."

if st.button("Buscar"):
    resposta = buscar_interacoes(pergunta, dados)
    st.markdown(resposta)
