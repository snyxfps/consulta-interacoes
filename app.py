import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from difflib import SequenceMatcher
from datetime import datetime
import json
import unicodedata
import re

# 🔧 Função para normalizar texto
def limpar(texto):
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ASCII", "ignore").decode("utf-8")
    texto = re.sub(r"[^\w\s]", "", texto)
    return texto.lower().strip()

# 🔐 Autenticação com Google Sheets via segredo
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

# 🎯 Interface Streamlit
st.title("🔍 Consulta de Interações com Segurados")
pergunta = st.text_input("Digite o nome do cliente:")

# 🔍 Busca inteligente e flexível
def buscar_interacoes(pergunta, dados):
    if not pergunta.strip():
        return "⚠️ Digite um nome para buscar."

    pergunta_limpa = limpar(pergunta)
    resultados = []

    for linha in dados:
        nome = linha.get('segurado', '')
        nome_limpo = limpar(nome)

        # Verifica se todas as palavras da pergunta estão no nome
        palavras = pergunta_limpa.split()
        if all(p in nome_limpo for p in palavras):
            resultados.append(linha)

    if not resultados:
        return "⚠️ Nenhuma interação encontrada para esse cliente."

    try:
        resultados.sort(key=lambda x: datetime.strptime(x['data_hora'], "%d/%m/%Y %H:%M"), reverse=True)
    except Exception:
        return "⚠️ Erro ao interpretar datas. Verifique o formato na planilha."

    ult = resultados[0]
    return f"""
🗓️ **{ult['data_hora']}**
📨 **{ult['canal']}**
💬 **{ult['conteudo']}**
"""

# 🧠 Botão de busca
if st.button("Buscar"):
    resposta = buscar_interacoes(pergunta, dados)
    st.markdown(resposta)
