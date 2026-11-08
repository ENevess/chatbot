"""Painel Web de Visualizacao de Logs, Avaliacoes (Positivo/Negativo) e Download do audit.jsonl (/logs.html)."""

from __future__ import annotations

LOGS_VIEWER_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Logs & Avaliações — Chatbot de Emplacamentos</title>
  <style>
    :root {
      --bg: #0f172a;
      --surface: #1e293b;
      --surface-light: #334155;
      --primary: #2563eb;
      --accent: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --border: #334155;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding-bottom: 40px;
    }
    header {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 14px 20px;
      position: sticky;
      top: 0;
      z-index: 10;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 10px;
    }
    .brand { font-size: 1.05rem; font-weight: 700; display: flex; align-items: center; gap: 10px; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .btn {
      background: var(--primary);
      color: white;
      text-decoration: none;
      border: none;
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 0.82rem;
      font-weight: 600;
      cursor: pointer;
    }
    .btn-secondary {
      background: var(--surface-light);
      border: 1px solid var(--border);
    }
    .btn-success {
      background: #059669;
    }
    .container {
      max-width: 1100px;
      margin: 20px auto;
      padding: 0 16px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
    }
    .kpi-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px;
    }
    .kpi-label { font-size: 0.76rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600; }
    .kpi-val { font-size: 1.5rem; font-weight: 700; margin-top: 4px; }
    .filter-bar {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
      background: var(--surface);
      padding: 12px 16px;
      border-radius: 12px;
      border: 1px solid var(--border);
    }
    .filter-btn {
      background: var(--bg);
      color: var(--text);
      border: 1px solid var(--border);
      padding: 6px 12px;
      border-radius: 999px;
      font-size: 0.8rem;
      cursor: pointer;
    }
    .filter-btn.active {
      background: var(--primary);
      border-color: var(--primary);
      font-weight: 600;
    }
    .log-list { display: flex; flex-direction: column; gap: 12px; }
    .log-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
    }
    .log-card.neg { border-left: 4px solid var(--danger); }
    .log-card.pos { border-left: 4px solid var(--accent); }
    .log-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 8px;
      font-size: 0.78rem;
      color: var(--text-muted);
    }
    .pill {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 0.72rem;
      font-weight: 700;
      text-transform: uppercase;
    }
    .pill-neg { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
    .pill-pos { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; }
    .pill-status { background: rgba(59, 130, 246, 0.2); color: #93c5fd; }
    .question-title { font-size: 0.98rem; font-weight: 700; margin-bottom: 6px; color: #f8fafc; }
    .comment-box {
      background: rgba(239, 68, 68, 0.12);
      border: 1px solid rgba(239, 68, 68, 0.35);
      color: #fecaca;
      padding: 8px 12px;
      border-radius: 8px;
      font-size: 0.85rem;
      margin: 8px 0;
    }
    details {
      margin-top: 8px;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px 12px;
      font-size: 0.8rem;
    }
    summary { cursor: pointer; color: var(--text-muted); font-weight: 600; }
    pre {
      margin-top: 8px;
      white-space: pre-wrap;
      font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
      color: #cbd5e1;
      font-size: 0.76rem;
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <span>📋 Auditoria de Logs & Avaliações de Respostas</span>
    </div>
    <div class="actions">
      <a class="btn btn-success" href="/api/logs/download" download="audit.jsonl">⬇️ Baixar audit.jsonl (Render/Local)</a>
      <a class="btn btn-secondary" href="/arquitetura.html">📐 Arquitetura</a>
      <a class="btn" href="/">← Voltar ao Chatbot</a>
    </div>
  </header>

  <main class="container">
    <section class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Total de Consultas</div>
        <div class="kpi-val" id="kpi-total">0</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label" style="color: #fca5a5;">👎 Avaliações Negativas</div>
        <div class="kpi-val" id="kpi-neg" style="color: #ef4444;">0</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label" style="color: #6ee7b7;">👍 Avaliações Positivas</div>
        <div class="kpi-val" id="kpi-pos" style="color: #10b981;">0</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label" style="color: #fcd34d;">❓ Esclarecimentos / Recusas</div>
        <div class="kpi-val" id="kpi-clarify" style="color: #f59e0b;">0</div>
      </div>
    </section>

    <section class="filter-bar">
      <span style="font-size: 0.82rem; color: var(--text-muted); font-weight: 600;">Filtrar visualização:</span>
      <button class="filter-btn active" onclick="setFilter('final_only', this)">Respostas Finais</button>
      <button class="filter-btn" onclick="setFilter('negative', this)">👎 Apenas Avaliações Negativas (Ruins)</button>
      <button class="filter-btn" onclick="setFilter('positive', this)">👍 Apenas Avaliações Positivas</button>
      <button class="filter-btn" onclick="setFilter('all', this)">Todos os Eventos (incl. Esclarecimentos)</button>
    </section>

    <section id="log-list" class="log-list">
      <div class="log-card">Carregando registros do log...</div>
    </section>
  </main>

  <script>
    let allEntries = [];
    let currentFilter = 'final_only';

    function escapeHtml(str) {
      return String(str || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    }

    function setFilter(flt, btnEl) {
      currentFilter = flt;
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btnEl.classList.add('active');
      renderLogs();
    }

    function renderLogs() {
      const container = document.getElementById('log-list');
      const queries = allEntries.filter(e => (e.event_type || 'query') === 'query');

      const negCount = queries.filter(q => q.feedback && q.feedback.rating === 'negative').length;
      const posCount = queries.filter(q => q.feedback && q.feedback.rating === 'positive').length;
      const clarifyCount = queries.filter(q => q.status === 'clarify' || q.status === 'refuse').length;

      document.getElementById('kpi-total').textContent = queries.length;
      document.getElementById('kpi-neg').textContent = negCount;
      document.getElementById('kpi-pos').textContent = posCount;
      document.getElementById('kpi-clarify').textContent = clarifyCount;

      const filtered = queries.filter(q => {
        if (currentFilter === 'final_only') return q.status !== 'clarify';
        if (currentFilter === 'negative') return q.feedback && q.feedback.rating === 'negative';
        if (currentFilter === 'positive') return q.feedback && q.feedback.rating === 'positive';
        return true;
      });

      if (filtered.length === 0) {
        container.innerHTML = '<div class="log-card">Nenhum registro encontrado para este filtro.</div>';
        return;
      }

      container.innerHTML = filtered.map(q => {
        const fb = q.feedback;
        const cardClass = fb ? (fb.rating === 'negative' ? 'neg' : 'pos') : '';
        let fbPill = '';
        if (fb) {
          fbPill = fb.rating === 'negative'
            ? '<span class="pill pill-neg">👎 Avaliada como Ruim</span>'
            : '<span class="pill pill-pos">👍 Avaliada como Boa</span>';
        }
        const commentHtml = (fb && fb.comment)
          ? `<div class="comment-box"><strong>Motivo anotado pelo avaliador:</strong> ${escapeHtml(fb.comment)}</div>`
          : '';

        return `
          <div class="log-card ${cardClass}">
            <div class="log-header">
              <div>
                <span class="pill pill-status">${escapeHtml(q.status)}</span>
                ${fbPill}
                <span style="margin-left: 6px;">ID: ${escapeHtml(q.interaction_id || '-')}</span>
              </div>
              <div>${escapeHtml(q.timestamp)} (${q.execution_time_ms || 0} ms)</div>
            </div>
            <div class="question-title">Pergunta: "${escapeHtml(q.question)}"</div>
            ${commentHtml}
            ${q.error ? `<div style="font-size:0.84rem; color:#fcd34d; margin-top:4px;">Mensagem: ${escapeHtml(q.error)}</div>` : ''}
            <details>
              <summary>Ver Especificação Semântica (QuerySpec) e SQL Gerado</summary>
              <pre><strong>Especificação JSON:</strong>\n${escapeHtml(JSON.stringify(q.specification || {}, null, 2))}\n\n<strong>SQL Executado:</strong>\n${escapeHtml(q.sql || '(Nenhum SQL executado)')}</pre>
            </details>
          </div>
        `;
      }).join('');
    }

    async function loadLogs() {
      const resp = await fetch('/api/logs');
      const data = await resp.json();
      allEntries = data.entries || [];
      renderLogs();
    }

    loadLogs();
  </script>
</body>
</html>
"""
