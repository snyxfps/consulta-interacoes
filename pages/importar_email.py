import streamlit as st
import email
from email import policy
from email.parser import BytesParser
import re
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from transformers import pipeline
import json

# Fallback extractivo
from sumy.parsers.plaintext import PlainTextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.text_rank import TextRankSummarizer

st.set_page_config(page_title="Importar E-mail", layout="centered")
st.title("📩 Importador de E-mail (.eml) — Alimentar Planilha")

MEU_NOME = "Silas Soares da Silva"
MEU_EMAIL = ""  # opcional

# -------------------------
# Ler .eml
# -------------------------
def ler_eml(file):
    raw = file.read()
    msg = BytesParser(policy=policy.default).parsebytes(raw)

    subject = msg.get("Subject", "") or ""
    sender = msg.get("From", "") or ""
    to = msg.get("To", "") or ""
    date_str = msg.get("Date")

    try:
        dt = email.utils.parsedate_to_datetime(date_str)
    except:
        dt = datetime.now()

    body = ""
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
        try:
            body = msg.get_content().strip()
        except:
            body = ""

    return subject, sender, to, dt, body

# -------------------------
# Direção
# -------------------------
def detectar_direcao(sender, to):
    s = sender.lower()
    t = to.lower()
    if MEU_EMAIL and MEU_EMAIL.lower() in s:
        return "Enviado"
    if MEU_NOME and MEU_NOME.lower() in s:
        return "Enviado"
    if MEU_EMAIL and MEU_EMAIL.lower() in t:
        return "Recebido"
    if MEU_NOME and MEU_NOME.lower() in t:
        return "Recebido"
    return "Recebido"

# -------------------------
# Extrair nome do segurado
# -------------------------
def extrair_nome_segurado(assunto):
    padrao = r"\|\s*(.*?)\s*-\s*\d"
    m = re.search(padrao, assunto)
    if m:
        return m.group(1).strip()
    padrao2 = r"-\s*\d+\s*-\s*(.*)"
    m2 = re.search(padrao2, assunto)
    if m2:
        nome = m2.group(1).strip()
        nome = re.sub(r"\d{11,14}", "", nome).strip()
        return nome
    if "|" in assunto:
        return assunto.split("|")[-1].strip()
    return assunto.strip()

# -------------------------
# IA de sumarização + fallback
# -------------------------
@st.cache_resource
def get_summarizer():
    return pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")

def resumo_extrativo(texto, sentencas=2):
    parser = PlainTextParser.from_string(texto, Tokenizer("portuguese"))
    summarizer = TextRankSummarizer()
    summary = summarizer(parser.document, sentencas)
    return " ".join(str(s) for s in summary)

def resumir_conteudo(body):
    texto = (body or "").strip()
    if len(texto) == 0:
        return "Informações recebidas por e-mail."
    if len(texto.split()) <= 3:
        return f"Mensagem breve: “{texto}”."

    texto = " ".join(texto.split())
    try:
        summarizer = get_summarizer()
        out = summarizer(texto, max_length=45, min_length=18, do_sample=False)
        resumo = out[0]["summary_text"]
        # se o resumo for igual ao original, usa fallback
        if resumo.lower() in texto.lower():
            return resumo_extrativo(texto)
        return resumo
    except Exception:
        return resumo_extrativo(texto)

# -------------------------
# Google Sheets
# -------------------------
SHEET_ID = "1331BNS5F0lOsIT9fNDds4Jro_nMYvfeWGVeqGhgj_BE"
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def append_to_sheet(linha):
    gcp_key = json.loads(st.secrets["gcp_key"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(gcp_key, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1
    sheet.append_row(linha, value_input_option="USER_ENTERED")

# -------------------------
# Upload EML
# -------------------------
uploaded = st.file_uploader("Envie um arquivo .eml", type=["eml"])

if uploaded:
    assunto, sender, to, data_hora, corpo = ler_eml(uploaded)

    st.subheader("📌 Assunto detectado")
    st.write(assunto)

    st.subheader("📧 Remetente")
    st.write(sender)

    st.subheader("📨 Destinatário(s)")
    st.write(to)

    st.subheader("📆 Data detectada")
    st.write(str(data_hora))

    st.subheader("📝 Corpo (prévia)")
    st.write(corpo[:600] if corpo else "")

    segurado = extrair_nome_segurado(assunto)
    canal = "E-mail"
    dt_fmt = data_hora.strftime("%d/%m/%Y %H:%M")

    resumo_ia = resumir_conteudo(corpo)

    direcao_detectada = detectar_direcao(sender, to)
    direcao = st.selectbox("Direção:", ["Recebido", "Enviado"], index=["Recebido", "Enviado"].index(direcao_detectada))

    conteudo_resumido = f"{direcao} e-mail: {resumo_ia}"

    st.subheader("✏️ Ajustar conteúdo antes de enviar")
    conteudo_editado = st.text_area("Conteúdo resumido (pode editar):", value=conteudo_resumido, height=150)

    tipo_evento = st.selectbox("Tipo do evento:", ["Outros", "Inicio", "Cobrança", "Retorno", "Questionamento"])
    integracao = st.selectbox("Integração:", ["RCV", "APP", "OUTRO"])

    st.subheader("📄 Linha final que será enviada")
    df = pd.DataFrame([{
        "segurado": segurado,
        "canal": canal,
        "data_hora": dt_fmt,
        "conteudo": conteudo_editado,
        "tipo_evento": tipo_evento,
        "integracao": integracao
    }])
    st.table(df)

    if st.button("Enviar para planilha"):
        append_to_sheet([segurado, canal, dt_fmt, conteudo_editado, tipo_evento, integracao])
        st.success("✔ Linha enviada para a planilha com sucesso!")
