"""
Verifica a página de Avisos do Portugal 2030 (https://portugal2030.pt/avisos/)
e envia um email quando deteta avisos novos face à última verificação.

Este script foi desenhado para correr dentro do GitHub Actions (ver
.github/workflows/check_avisos.yml), mas também pode ser corrido localmente.

Lógica de horário:
    O workflow corre TODAS AS HORAS, mas este script só faz a verificação
    real (scraping + email) quando a hora local em Lisboa está dentro de
    TARGET_HOURS. Isto evita ter de gerir manualmente a mudança de hora
    (DST) — o fuso "Europe/Lisbon" trata disso automaticamente.

Estado:
    A lista de avisos da última verificação fica guardada em
    avisos_state.json. O workflow faz commit deste ficheiro de volta ao
    repositório a cada execução, para que o histórico persista entre runs.

IMPORTANTE — seletores de HTML:
    A página de avisos é carregada via JavaScript, por isso usamos o
    Playwright (browser automatizado) em vez de um simples pedido HTTP.
    A extração abaixo usa uma heurística genérica (todos os links cujo
    href contém "/avisos/"). É muito provável que precises de afinar isto
    depois de veres o HTML real — corre uma vez com DEBUG_DUMP_HTML=1 para
    gerar debug_page.html e inspecionar a estrutura real dos cartões de
    aviso (classe do contentor, título, data limite, etc.).
"""

import json
import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

URL = "https://portugal2030.pt/avisos/"
STATE_FILE = "avisos_state.json"
TARGET_HOURS = {8, 13, 18}  # horas locais de Lisboa em que queremos verificar


def should_run_now() -> bool:
    if os.environ.get("FORCE_RUN"):
        return True
    now_lisbon = datetime.now(ZoneInfo("Europe/Lisbon"))
    return now_lisbon.hour in TARGET_HOURS


def fetch_avisos() -> dict:
    """Devolve um dicionário {link: título} com os avisos encontrados na página."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)  # margem extra para conteúdo carregado por JS

        if os.environ.get("DEBUG_DUMP_HTML"):
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(page.content())

        anchors = page.query_selector_all("a[href*='/avisos/']")

        avisos = {}
        base = URL.rstrip("/")
        for a in anchors:
            href = a.get_attribute("href") or ""
            title = (a.inner_text() or "").strip()
            if not href or not title:
                continue
            full_href = href if href.startswith("http") else f"https://portugal2030.pt{href}"
            if full_href.rstrip("/") == base:
                continue  # ignora o próprio link para a página de listagem
            avisos[full_href] = title

        browser.close()
        return avisos


def load_previous_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(avisos: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(avisos, f, ensure_ascii=False, indent=2)


def send_email(new_avisos: dict) -> None:
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    email_to = os.environ["EMAIL_TO"]

    linhas = [f"- {titulo}\n  {link}" for link, titulo in new_avisos.items()]
    corpo = (
        f"Foram detetados {len(new_avisos)} novo(s) aviso(s) em {URL}:\n\n"
        + "\n\n".join(linhas)
    )

    msg = MIMEText(corpo, "plain", "utf-8")
    msg["Subject"] = f"[Portugal 2030] {len(new_avisos)} novo(s) aviso(s) aberto(s)"
    msg["From"] = smtp_user
    msg["To"] = email_to

    with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [email_to], msg.as_string())


def main() -> None:
    if not should_run_now():
        print("Fora da janela horária (08h/13h/18h Lisboa). A terminar sem verificar.")
        return

    current = fetch_avisos()
    previous = load_previous_state()

    if not previous:
        # Primeira execução: só cria a baseline, para não mandar um email
        # gigante com TODOS os avisos atualmente abertos.
        save_state(current)
        print(f"Baseline criada com {len(current)} avisos. Nenhum email enviado.")
        return

    novos_links = set(current) - set(previous)
    novos_avisos = {link: current[link] for link in novos_links}

    if novos_avisos:
        send_email(novos_avisos)
        print(f"Email enviado com {len(novos_avisos)} novo(s) aviso(s).")
    else:
        print("Sem avisos novos nesta verificação.")

    save_state(current)


if __name__ == "__main__":
    main()
