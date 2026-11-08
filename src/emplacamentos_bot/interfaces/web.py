"""Interface Web Responsiva (Mobile-First) e Servidor HTTP para o Chatbot (Tarefa 8 - Secao 5 e 10).

Projetada para:
1. Funcionar em celulares (layout mobile-first com viewport, safe-area e chips de perguntas rapidas);
2. Ser facilmente hospedada em qualquer plataforma cloud (Railway, Render, Fly.io, Docker) escutando
   em 0.0.0.0:$PORT sem exigir dependencias pesadas;
3. Garantir que nenhum dado do banco suba para o LLM (mesma pipeline deterministica do EmplacamentosChatbot).
"""

from __future__ import annotations

import json
import os
import socket
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from emplacamentos_bot.bot import EmplacamentosChatbot
from emplacamentos_bot.llm.client import create_llm_client
from emplacamentos_bot.semantic.loader import load_semantic_catalog

MOBILE_FIRST_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <title>Chatbot de Emplacamentos — Diretoria & Gerência</title>
  <style>
    :root {
      --bg: #0f172a;
      --surface: #1e293b;
      --surface-light: #334155;
      --primary: #2563eb;
      --primary-hover: #1d4ed8;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --border: #334155;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100dvh;
      overflow: hidden;
    }
    header {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 12px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      flex-shrink: 0;
    }
    .brand-title {
      font-size: 1rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .badge {
      font-size: 0.7rem;
      background: rgba(16, 185, 129, 0.15);
      color: var(--success);
      border: 1px solid rgba(16, 185, 129, 0.4);
      padding: 2px 8px;
      border-radius: 999px;
      font-weight: 600;
    }
    .provider-select {
      background: var(--bg);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 6px 10px;
      font-size: 0.8rem;
    }
    .disclaimer-banner {
      background: rgba(245, 158, 11, 0.12);
      border-bottom: 1px solid rgba(245, 158, 11, 0.35);
      color: #fcd34d;
      font-size: 0.78rem;
      padding: 6px 16px;
      text-align: center;
      font-weight: 500;
      flex-shrink: 0;
    }
    .chips-section {
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding: 10px 16px;
      background: rgba(30, 41, 59, 0.6);
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }
    .chips-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }
    .chips-label {
      font-size: 0.72rem;
      color: var(--text-muted);
      font-weight: 600;
      text-transform: uppercase;
      margin-right: 4px;
    }
    .chip {
      background: var(--surface-light);
      color: var(--text);
      border: 1px solid var(--border);
      padding: 5px 11px;
      border-radius: 999px;
      font-size: 0.76rem;
      cursor: pointer;
      transition: background 0.15s;
    }
    .chip:hover, .chip:active { background: var(--primary); }
    #chat-container {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .msg {
      max-width: 92%;
      padding: 12px 14px;
      border-radius: 14px;
      line-height: 1.45;
      font-size: 0.92rem;
      word-wrap: break-word;
    }
    .msg.user {
      background: var(--primary);
      color: white;
      align-self: flex-end;
      border-bottom-right-radius: 4px;
    }
    .msg.bot {
      background: var(--surface);
      border: 1px solid var(--border);
      align-self: flex-start;
      border-bottom-left-radius: 4px;
      width: 100%;
      max-width: 720px;
    }
    .status-pill {
      display: inline-block;
      font-size: 0.72rem;
      font-weight: 700;
      text-transform: uppercase;
      padding: 2px 8px;
      border-radius: 6px;
      margin-bottom: 8px;
    }
    .status-responder { background: rgba(16, 185, 129, 0.2); color: var(--success); }
    .status-esclarecer { background: rgba(245, 158, 11, 0.2); color: var(--warning); }
    .status-recusar { background: rgba(239, 68, 68, 0.2); color: var(--danger); }
    .answer-line { margin-bottom: 6px; }
    details {
      margin-top: 10px;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px 10px;
      font-size: 0.8rem;
    }
    summary {
      cursor: pointer;
      color: var(--text-muted);
      font-weight: 600;
    }
    pre {
      margin-top: 8px;
      white-space: pre-wrap;
      font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
      color: #cbd5e1;
      font-size: 0.76rem;
    }
    footer {
      background: var(--surface);
      border-top: 1px solid var(--border);
      padding: 10px 12px env(safe-area-inset-bottom, 10px);
      display: flex;
      gap: 8px;
      flex-shrink: 0;
    }
    #question-input {
      flex: 1;
      background: var(--bg);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px 14px;
      font-size: 0.95rem;
      outline: none;
    }
    #question-input:focus { border-color: var(--primary); }
    #send-btn {
      background: var(--primary);
      color: white;
      border: none;
      border-radius: 10px;
      padding: 0 18px;
      font-weight: 600;
      font-size: 0.92rem;
      cursor: pointer;
    }
    #send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  </style>
</head>
<body>
  <header>
    <div class="brand-title">
      <span>🚛 Emplacamentos Bot</span>
      <span class="badge">Camada Semântica v0.1</span>
    </div>
    <select id="provider-select" class="provider-select" title="Provedor de Interpretação">
      <option value="claude" selected>Modo: Claude (Anthropic)</option>
      <option value="mock">Modo: Mock (Offline)</option>
    </select>
  </header>

  <div class="disclaimer-banner">
    ⚠️ <strong>AVISO DE DADOS SINTÉTICOS:</strong> Todos os dados de emplacamentos, chassis, clientes e concessionárias utilizados neste ambiente são <strong>100% sintéticos (fictícios)</strong>, gerados exclusivamente para validação da camada semântica desta PoC.
  </div>

  <div class="chips-section">
    <div class="chips-row">
      <span class="chips-label">Consultas & Share:</span>
      <button class="chip" onclick="sendQuick('Quantos caminhões foram emplacados no último mês?')">📊 Volume último mês</button>
      <button class="chip" onclick="sendQuick('Qual a participação de mercado da DAF em 2026 apenas no segmento pesado?')">🎯 Share DAF Pesados 2026</button>
      <button class="chip" onclick="sendQuick('Qual o volume de emplacamentos por região em 2025?')">🗺️ Volume por Região 2025</button>
      <button class="chip" onclick="sendQuick('Qual a participação por segmento em 2025?')">⚖️ Pesado vs Semi-Pesado</button>
    </div>
    <div class="chips-row">
      <span class="chips-label">Rankings & Governança:</span>
      <button class="chip" onclick="sendQuick('Qual o top 5 ranking de modelos mais emplacados em 2025?')">🏆 Top 5 Modelos 2025</button>
      <button class="chip" onclick="sendQuick('Qual foi a variação de emplacamentos de 2025 contra 2024?')">📈 Variação 2025 vs 2024</button>
      <button class="chip" onclick="sendQuick('Quantos caminhões da VOLVO foram emplacados?')">❓ Teste Ambiguidade (Sem Período)</button>
      <button class="chip" onclick="sendQuick('Qual o volume de emplacamentos por dealer em 2025?')">🏢 Teste Ambiguidade (Dealer)</button>
    </div>
  </div>

  <main id="chat-container">
    <div class="msg bot">
      <span class="status-pill status-responder">Pronto</span>
      <div class="answer-line">
        Olá! Sou o assistente de dados agregados de <strong>emplacamentos de caminhões pesados e semi-pesados</strong> (base desde 2019).
      </div>
      <div class="answer-line" style="color: var(--text-muted); font-size: 0.83rem;">
        🔒 <em>Privacidade ativa:</em> Nenhum dado do banco é enviado ao LLM. Resultados com menos de 5 unidades são suprimidos.
      </div>
    </div>
  </main>

  <footer>
    <input id="question-input" type="text" placeholder="Pergunte sobre emplacamentos (ex: share da DAF em 2025)..." autocomplete="off" />
    <button id="send-btn" onclick="submitQuestion()">Enviar</button>
  </footer>

  <script>
    const chat = document.getElementById('chat-container');
    const input = document.getElementById('question-input');
    const btn = document.getElementById('send-btn');
    const providerSelect = document.getElementById('provider-select');
    let pendingClarificationQuestion = null;

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') submitQuestion();
    });

    function sendQuick(text) {
      pendingClarificationQuestion = null;
      input.value = text;
      submitQuestion();
    }

    function formatMarkdownBold(str) {
      return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');
    }

    async function submitQuestion() {
      const q = input.value.trim();
      if (!q) return;

      const userDiv = document.createElement('div');
      userDiv.className = 'msg user';
      userDiv.textContent = q;
      chat.appendChild(userDiv);

      input.value = '';
      btn.disabled = true;
      chat.scrollTop = chat.scrollHeight;

      try {
        const resp = await fetch('/api/ask', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question: q,
            pending_question: pendingClarificationQuestion,
            provider: providerSelect.value
          })
        });
        const data = await resp.json();

        const botDiv = document.createElement('div');
        botDiv.className = 'msg bot';

        if (!resp.ok) {
          pendingClarificationQuestion = null;
          botDiv.innerHTML = `<span class="status-pill status-recusar">Erro</span><div>${formatMarkdownBold(data.error || 'Erro ao processar solicitação.')}</div>`;
        } else {
          if (data.behavior === 'esclarecer') {
            pendingClarificationQuestion = data.question;
          } else {
            pendingClarificationQuestion = null;
          }
          const pillClass = 'status-' + (data.behavior || 'responder');
          const linesHtml = (data.answer_text || '')
            .split('\\n')
            .map(l => `<div class="answer-line">${formatMarkdownBold(l)}</div>`)
            .join('');

          let sqlBlock = '';
          if (data.sql) {
            sqlBlock = `
              <details>
                <summary>Ver consulta SQL determinística gerada</summary>
                <pre>${data.sql.replace(/</g, '&lt;')}</pre>
              </details>`;
          }
          botDiv.innerHTML = `<span class="status-pill ${pillClass}">${data.behavior}</span>${linesHtml}${sqlBlock}`;
        }
        chat.appendChild(botDiv);
      } catch (err) {
        const errDiv = document.createElement('div');
        errDiv.className = 'msg bot';
        errDiv.innerHTML = `<span class="status-pill status-recusar">Erro de Conexão</span><div>Não foi possível contatar o servidor local.</div>`;
        chat.appendChild(errDiv);
      } finally {
        btn.disabled = false;
        chat.scrollTop = chat.scrollHeight;
      }
    }
  </script>
</body>
</html>
"""


def handle_api_ask(payload: dict[str, Any], bot: EmplacamentosChatbot | None = None) -> tuple[int, dict[str, Any]]:
    """Processa uma requisicao JSON para /api/ask e retorna (status_code, response_dict)."""
    question = str(payload.get("question", "")).strip()
    if not question:
        return HTTPStatus.BAD_REQUEST, {"error": "O campo 'question' é obrigatório."}

    pending_question = payload.get("pending_question")
    provider = str(payload.get("provider", os.getenv("LLM_PROVIDER", "mock"))).strip().lower()

    try:
        active_bot = bot or EmplacamentosChatbot(llm_client=create_llm_client(provider))
        if pending_question and isinstance(pending_question, str) and pending_question.strip():
            active_bot.pending_clarification_question = pending_question.strip()
        turn = active_bot.ask(question)
        return HTTPStatus.OK, {
            "question": turn.question,
            "behavior": turn.behavior,
            "answer_text": turn.answer_text,
            "sql": turn.sql,
            "rows": turn.rows,
            "privacy_suppressed": turn.privacy_suppressed,
        }
    except Exception as exc:
        return HTTPStatus.BAD_REQUEST, {"error": str(exc)}


def ensure_database_initialized() -> None:
    """Garante que o banco sintético exista (útil ao subir em nuvem/containers efêmeros)."""
    from emplacamentos_bot.executor.safe_executor import DEFAULT_DB_PATH

    db_path = Path(os.getenv("DATABASE_PATH", str(DEFAULT_DB_PATH)))
    if not db_path.exists():
        from scripts.generate_synthetic_db import populate_database

        scale = float(os.getenv("SYNTHETIC_DB_SCALE", "0.1"))
        print(f"Banco não encontrado em {db_path}. Gerando base sintética (escala={scale})...")
        populate_database(db_path=db_path, scale=scale)


class ChatbotWebHandler(BaseHTTPRequestHandler):
    """Handler HTTP leve para servir a UI Mobile-First e os endpoints JSON."""

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            body = MOBILE_FIRST_HTML.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/health":
            catalog = load_semantic_catalog()
            body = json.dumps({"status": "ok", "semantic_version": catalog.version}).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Rota não encontrada.")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/ask":
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            try:
                payload = json.loads(raw_body)
            except json.JSONDecodeError:
                payload = {}

            status_code, resp_dict = handle_api_ask(payload)
            body = json.dumps(resp_dict, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Rota não encontrada.")

    def log_message(self, format: str, *args: Any) -> None:
        """Suprime logs verbosos por requisicao no stdout padrao."""
        return


def get_local_lan_ip() -> str:
    """Descobre o IP da rede local (Wi-Fi/LAN) para testar facilmente pelo celular."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return str(s.getsockname()[0])
    except OSError:
        return "127.0.0.1"


def main() -> None:
    """Inicia o servidor web escutando em 0.0.0.0 para acesso no PC, celular ou nuvem."""
    ensure_database_initialized()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    lan_ip = get_local_lan_ip()

    server = ThreadingHTTPServer((host, port), ChatbotWebHandler)
    print("======================================================================")
    print(" SERVIDOR WEB DO CHATBOT DE EMPLACAMENTOS ATIVO")
    print(f" - Acesso neste computador : http://localhost:{port}")
    print(f" - Acesso pelo Celular (Wi-Fi): http://{lan_ip}:{port}")
    print(" Pressione Ctrl+C para encerrar.")
    print("======================================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando servidor web.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
