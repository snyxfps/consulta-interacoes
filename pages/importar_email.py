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

st.set_page_config(page_title="Importar E-mail", layout="centered")

st.title("📩 Importador de E-mail (.eml) — Alimentar Planilha")

# -------------------------
# Ler .eml
# -------------------------
def ler_eml(file):
    raw = file.read()
    msg = BytesParser(policy=policy.default).parsebytes(raw)

    subject = msg.get("Subject", "")
    date_str = msg.get("Date")

    try:
        dt = email.utils.parsedate_to_datetime(date_str)
    except:
        dt = datetime.now()

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

    return subject, dt, body


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
# Resumir conteúdo com IA local (Transformers)
# -------------------------
@st.cache_resource
def get_summarizer():
    # modelo gratuito de sumarização
    return pipeline("summarization", model="facebook/bart-large-cnn")

def resumir_conteudo(body):
    texto = body.strip()
    if len(texto) == 0:
        return "Informações recebidas por e-mail."

    summarizer = get_summarizer()

    # Limpeza simples
    texto = " ".join(texto.split())

    # Quebra em blocos para textos longos
    max_chars = 1500
    blocos = [texto[i:i+max_chars] for i in range(0, len(texto), max_chars)]

    resumos = []
    for b in blocos:
        try:
            out = summarizer(
                b,
                max_length=60,
                min_length=20,
                do_sample=False
            )
            resumos.append(out[0]["summary_text"])
        except Exception:
            resumos.append(b[:200] + ("..." if len(b) > 200 else ""))

    texto_resumido = " ".join(resumos)
    if len(resumos) > 1:
        try:
            out_final = summarizer(
                texto_resumido,
                max_length=60,
                min_length=20,
                do_sample=False
            )
            texto_resumido = out_final[0]["summary_text"]
        except Exception:
            pass

    # Ajuste para casos frequentes
    low = texto.lower()
    if any(k in low for k in ["agenda", "reuni", "horário", "disponibilidade"]):
        return "Enviado e-mail solicitando disponibilidade de horários para agendar reunião inicial."
    if any(k in low for k in ["dúvida", "confirmar", "esclarecimento"]):
        return "Enviado e-mail questionando se ficou dúvida sobre a integração ou documentação."

    return texto_resumido


# -------------------------
# Conectar Google Sheets
# -------------------------
SHEET_ID = "1331BNS5F0lOsIT9fNDds4Jro_nMYvfeWGVeqGhgj_BE"
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

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

    # gera resumo automático
    conteudo_resumido = resumir_conteudo(corpo)

    st.subheader("✏️ Ajustar conteúdo antes de enviar")
    conteudo_editado = st.text_area(
        "Conteúdo resumido (pode editar):",
        value=conteudo_resumido,
        height=150
    )

    tipo_evento = st.selectbox("Tipo do evento:", ["Outros", "Aporte", "Aviso", "Solicitação"])
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
        append_to_sheet([
            segurado,
            canal,
            dt_fmt,
            conteudo_editado,
            tipo_evento,
            integracao
        ])
        st.success("✔ Linha enviada para a planilha com sucesso!")
