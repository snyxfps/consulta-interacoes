import streamlit as st
import email
from email import policy
from email.parser import BytesParser
import re
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import pandas as pd

st.set_page_config(page_title="Importar E-mail", layout="centered")

st.title("📩 Importador de E-mail (.eml) — Alimentar Planilha")

# -------------------------
# Ler .eml
# -------------------------
def ler_eml(file):
    raw = file.read()
    msg = BytesParser(policy=policy.default).parsebytes(raw)

    # assunto
    subject = msg.get("Subject", "")

    # data
    date_str = msg.get("Date")
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
    except:
        dt = datetime.now()

    # corpo
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    parts.append(part.get_content())
                except:
                    pass
        body = "\n".join(parts).strip()
    else:
        body = msg.get_content().strip()

    return subject, dt, body


# -------------------------
# Extrair nome do segurado
# -------------------------
def extrair_nome_segurado(assunto):
    # Padrão mais comum: "APHICOR/ESSOR - RC-V | NOME SEGURADO - APOLICE"
    padrao = r"\|\s*(.*?)\s*-\s*\d"
    m = re.search(padrao, assunto)
    if m:
        return m.group(1).strip()

    # Caso "INSTALAÇÃO - 59 - Nome Segurado CNPJ"
    padrao2 = r"-\s*\d+\s*-\s*(.*)"
    m2 = re.search(padrao2, assunto)
    if m2:
        nome = m2.group(1).strip()
        # remove CNPJ, números
        nome = re.sub(r"\d{11,14}", "", nome).strip()
        return nome

    # fallback → retorna tudo após |
    if "|" in assunto:
        return assunto.split("|")[-1].strip()

    # fallback final
    return assunto.strip()


# -------------------------
# Resumo do corpo (1 linha)
# -------------------------
def resumir_conteudo(body):
    body = body.replace("\n", " ").strip()
    if len(body) == 0:
        return "Informações recebidas por e-mail."
    # retorna apenas primeiros 120 caracteres
    return body[:120] + "..." if len(body) > 120 else body


# -------------------------
# Conectar Google Sheets
# -------------------------
SHEET_ID = "1331BNS5F0lOsIT9fNDds4Jro_nMYvfeWGVeqGhgj_BE"
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def append_to_sheet(linha):
    gcp_key = st.secrets["gcp_key"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(gcp_key, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1
    sheet.append_row(linha, value_input_option="USER_ENTERED")


# -------------------------
# Upload EML
# -------------------------
uploaded = st.file_uploader("Envie um arquivo .eml", type=["eml"])

if uploaded:
    assunto, data_hora, corpo = ler_eml(uploaded)

    st.subheader("📌 Assunto detectado")
    st.write(assunto)

    st.subheader("📆 Data detectada")
    st.write(str(data_hora))

    st.subheader("📝 Corpo (prévia)")
    st.write(corpo[:500])

    # -----------------------------
    # Montar dados
    # -----------------------------
    segurado = extrair_nome_segurado(assunto)
    canal = "E-mail"
    dt_fmt = data_hora.strftime("%d/%m/%Y %H:%M")
    conteudo = resumir_conteudo(corpo)
    tipo_evento = "Outros"
    integracao = "RCV"

    st.subheader("📄 Linha gerada")
    df = pd.DataFrame([{
        "segurado": segurado,
        "canal": canal,
        "data_hora": dt_fmt,
        "conteudo": conteudo,
        "tipo_evento": tipo_evento,
        "integracao": integracao
    }])
    st.table(df)

    if st.button("Enviar para planilha"):
        append_to_sheet([
            segurado,
            canal,
            dt_fmt,
            conteudo,
            tipo_evento,
            integracao
        ])
        st.success("✔ Linha enviada para a planilha com sucesso!")
