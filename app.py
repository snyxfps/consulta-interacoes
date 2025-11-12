import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from difflib import SequenceMatcher
import json

# Autenticação com Google Sheets via segredo
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
gcp_key = json.loads(st.secrets["gcp_key"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(gcp_key, scope)
client = gspread.authorize(creds)

# Abre a planilha
sheet = client.open_by_key("1331BNS5F0lOsIT9fNDds4Jro_nMYvfeWGVeqGhgj_BE").sheet1
dados = sheet.get_all_records()

# Interface Streamlit
st.title("🔍 Consulta de Interações com Segurados")
pergunta = st.text_input("Digite sua pergunta:")

# Função de correspondência aproximada
def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

# Busca inteligente
def buscar_interacoes(pergunta, dados):
    pergunta = pergunta.lower()
    resultados = []

    for linha in dados:
        nome = linha['segurado'].lower()
        if similar(pergunta, nome) > 0.6 or any(p in nome for p in pergunta.split()):
            resultados.append(linha)

    if resultados:
        ult = sorted(resultados, key=lambda x: x['data_hora'], reverse=True)[0]
        return f"🗓️ {ult['data_hora']}\n📨 {ult['canal']}\n💬 {ult['conteudo']}"
    else:
        return "⚠️ Nenhuma interação encontrada."

# Botão de busca
if st.button("Buscar"):
    resposta = buscar_interacoes(pergunta, dados)
    st.markdown(resposta)
