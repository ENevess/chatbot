"""Pagina HTML de Arquitetura da PoC (/arquitetura e /arquitetura.html)."""

from __future__ import annotations

ARCHITECTURE_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Arquitetura da PoC — Chatbot de Emplacamentos</title>
  <style>
    :root {
      --bg: #0f172a;
      --surface: #1e293b;
      --surface-light: #334155;
      --primary: #3b82f6;
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
      line-height: 1.6;
      padding-bottom: 48px;
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
    .brand {
      font-size: 1.05rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .badge {
      font-size: 0.72rem;
      background: rgba(16, 185, 129, 0.15);
      color: var(--accent);
      border: 1px solid rgba(16, 185, 129, 0.4);
      padding: 2px 9px;
      border-radius: 999px;
      font-weight: 600;
    }
    .back-btn {
      background: var(--primary);
      color: white;
      text-decoration: none;
      padding: 7px 14px;
      border-radius: 8px;
      font-size: 0.84rem;
      font-weight: 600;
    }
    .disclaimer {
      background: rgba(245, 158, 11, 0.12);
      border-bottom: 1px solid rgba(245, 158, 11, 0.35);
      color: #fcd34d;
      font-size: 0.8rem;
      padding: 8px 20px;
      text-align: center;
    }
    .container {
      max-width: 1040px;
      margin: 24px auto;
      padding: 0 16px;
      display: flex;
      flex-direction: column;
      gap: 22px;
    }
    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 20px;
    }
    h1 { font-size: 1.45rem; margin-bottom: 6px; }
    h2 {
      font-size: 1.12rem;
      color: #60a5fa;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    h3 { font-size: 0.96rem; margin: 12px 0 6px; color: #e2e8f0; }
    p { color: #cbd5e1; font-size: 0.92rem; margin-bottom: 10px; }
    .grid-2 {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 14px;
      margin-top: 10px;
    }
    .subcard {
      background: rgba(15, 23, 42, 0.65);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px;
    }
    .subcard-ok { border-left: 4px solid var(--accent); }
    .subcard-no { border-left: 4px solid var(--danger); }
    .flow-steps {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(175px, 1fr));
      gap: 12px;
      margin-top: 12px;
    }
    .step-box {
      background: rgba(15, 23, 42, 0.75);
      border: 1px solid var(--border);
      border-top: 3px solid var(--primary);
      border-radius: 10px;
      padding: 12px;
      font-size: 0.85rem;
    }
    .step-num {
      font-size: 0.72rem;
      font-weight: 700;
      color: #60a5fa;
      text-transform: uppercase;
      margin-bottom: 4px;
    }
    .step-title { font-weight: 700; margin-bottom: 6px; color: var(--text); }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 10px;
      font-size: 0.86rem;
    }
    th, td {
      text-align: left;
      padding: 9px 10px;
      border-bottom: 1px solid var(--border);
    }
    th { color: var(--text-muted); font-weight: 600; background: rgba(15, 23, 42, 0.5); }
    ul { padding-left: 18px; color: #cbd5e1; font-size: 0.88rem; }
    li { margin-bottom: 5px; }
    code {
      background: rgba(15, 23, 42, 0.8);
      padding: 2px 6px;
      border-radius: 4px;
      font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
      font-size: 0.82rem;
      color: #93c5fd;
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <span>📐 Arquitetura da PoC — Emplacamentos Bot</span>
      <span class="badge">Camada Semântica v0.1.0</span>
    </div>
    <a class="back-btn" href="/">← Voltar para o Chatbot</a>
  </header>

  <div class="disclaimer">
    ⚠️ <strong>AMBIENTE DE VALIDAÇÃO (DADOS SINTÉTICOS):</strong> Todos os dados de emplacamentos, clientes, chassis e concessionárias desta PoC são 100% sintéticos.
  </div>

  <main class="container">
    <!-- 1. Objetivo e Principios -->
    <section class="card">
      <h1>1. Objetivo e Princípios Arquiteturais</h1>
      <p>
        Esta Prova de Conceito (PoC) valida uma <strong>Camada Semântica determinística</strong> para consultas quantitativas sobre
        emplacamentos de caminhões novos (pesados e semi-pesados, desde 2019), voltada para Diretoria e Gerência.
      </p>
      <div class="grid-2">
        <div class="subcard">
          <h3>🎯 Papel do LLM (Claude Haiku 5.5)</h3>
          <p>
            O LLM atua exclusivamente como <strong>tradutor de intenção semântica</strong>. Ele não escreve SQL livre na v0,
            não acessa o banco de dados e não calcula números de memória.
          </p>
        </div>
        <div class="subcard">
          <h3>⚖️ Ordem de Prioridade</h3>
          <p>
            <strong>1º Correção → 2º Cobertura → 3º Elegância.</strong><br/>
            Meta inegociável: <strong>Zero Erro Confiante</strong>. Quando uma pergunta omite período ou apresenta ambiguidade, o bot para e pede esclarecimento.
          </p>
        </div>
      </div>
    </section>

    <!-- 2. Pipeline em 5 Etapas -->
    <section class="card">
      <h2>🔄 2. Fluxo de Execução de Cada Pergunta (5 Etapas)</h2>
      <p>Toda pergunta percorre um pipeline isolado em 5 estágios auditáveis:</p>
      <div class="flow-steps">
        <div class="step-box">
          <div class="step-num">Etapa 1</div>
          <div class="step-title">Intenção & Desambiguação</div>
          <p>Recebe a pergunta em PT-BR e identifica se é uma consulta válida, ambígua (ex.: sem período ou sem tipo de dealer) ou fora do escopo.</p>
        </div>
        <div class="step-box">
          <div class="step-num">Etapa 2</div>
          <div class="step-title">Especificação (QuerySpec JSON)</div>
          <p>O interpretador (<code>Claude Haiku 5.5</code> ou <code>Mock</code>) mapeia a pergunta para um JSON estruturado usando apenas itens do catálogo semântico.</p>
        </div>
        <div class="step-box">
          <div class="step-num">Etapa 3</div>
          <div class="step-title">Compilador Determinístico</div>
          <p>O <code>SQLCompiler</code> valida a especificação contra <code>semantic/emplacamentos.yaml</code> e compila um comando <code>SELECT</code> parametrizado.</p>
        </div>
        <div class="step-box">
          <div class="step-num">Etapa 4</div>
          <div class="step-title">Executor Seguro & Privacidade</div>
          <p>Executa em SQLite <em>read-only</em> validando <em>allowlist</em> de tabelas, bloqueio de PII, limites de tempo/bytes e <strong>k-anonimato (k=5)</strong>.</p>
        </div>
        <div class="step-box">
          <div class="step-num">Etapa 5</div>
          <div class="step-title">Formatador Local (Seção 8)</div>
          <p>Redige localmente a resposta padronizada em 4 blocos (Resposta direta, Período/Filtros, Definição da métrica e Status de privacidade).</p>
        </div>
      </div>
    </section>

    <!-- 3. Fronteira de Privacidade e Isolamento do LLM -->
    <section class="card">
      <h2>🔒 3. Isolamento de Dados e Fronteira com a LLM (Anthropic Claude Haiku 5.5)</h2>
      <p>Mesmo utilizando dados sintéticos nesta PoC, a arquitetura aplica <strong>minimização estrita de dados</strong>:</p>
      <div class="grid-2">
        <div class="subcard subcard-ok">
          <h3>✅ O que É enviado para a API da LLM</h3>
          <ul>
            <li>O texto da pergunta feita pelo usuário;</li>
            <li>A data de referência do sistema;</li>
            <li>O resumo conceitual do catálogo semântico (nomes das 5 métricas, nomes das dimensões, sinônimos e regras de ambiguidade).</li>
          </ul>
        </div>
        <div class="subcard subcard-no">
          <h3>🚫 O que NUNCA é enviado para a API da LLM</h3>
          <ul>
            <li>Nenhuma linha ou tabela do banco de dados SQLite;</li>
            <li>Nenhum resultado numérico ou contagem retornada pela consulta;</li>
            <li>Nenhum dado de cliente (CNPJ, razão social, endereço, e-mail, sócios), chassi (VIN) ou placa;</li>
            <li>O resultado SQL vai direto do <code>SafeSQLExecutor</code> para o <code>ResponseFormatter</code> local em Python.</li>
          </ul>
        </div>
      </div>
    </section>

    <!-- 4. Camada Semantica -->
    <section class="card">
      <h2>📚 4. Camada Semântica Versionada (<code>semantic/emplacamentos.yaml</code>)</h2>
      <p>Ativo governado e versionado com histórico em <code>semantic/CHANGELOG.md</code>.</p>
      <table>
        <thead>
          <tr>
            <th>Métrica Oficial</th>
            <th>Fórmula Determinística</th>
            <th>Regras e Exceções</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Volume de Emplacamentos</strong><br/>(<code>volume_emplacamentos</code>)</td>
            <td><code>COUNT(e.id_emplacamento)</code></td>
            <td>Exige período explícito. Suprimido quando contagem &lt; 5.</td>
          </tr>
          <tr>
            <td><strong>Participação de Mercado por Marca</strong><br/>(<code>participacao_mercado_marca</code>)</td>
            <td><code>COUNT(marca) / SUM(COUNT(todas_marcas)) OVER () * 100</code></td>
            <td>Preserva o denominador total do mercado no período (e no segmento filtrado, quando aplicável).</td>
          </tr>
          <tr>
            <td><strong>Participação por Segmento</strong><br/>(<code>participacao_segmento</code>)</td>
            <td><code>COUNT(segmento) / SUM(COUNT(total)) OVER () * 100</code></td>
            <td>Usa diretamente a classificação oficial de <code>modelo.segmento</code> (<code>PESADO</code>, <code>SEMI-PESADO</code>).</td>
          </tr>
          <tr>
            <td><strong>Ranking de Modelos</strong><br/>(<code>ranking_modelos</code>)</td>
            <td><code>COUNT(e.id_emplacamento) ORDER BY valor DESC</code></td>
            <td>Agrupa por <code>modelo.modelo</code> e <code>modelo.fabricante</code>.</td>
          </tr>
          <tr>
            <td><strong>Variação entre Períodos</strong><br/>(<code>variacao_periodos</code>)</td>
            <td><code>((Vol_atual - Vol_ant) / NULLIF(Vol_ant, 0)) * 100</code></td>
            <td>Exige dois períodos explícitos (MoM ou YoY).</td>
          </tr>
        </tbody>
      </table>

      <h3>Regras de Governança e Desambiguação Ativas:</h3>
      <ul>
        <li><strong>Período Obrigatório:</strong> O bot nunca assume período padrão. <em>"Último mês"</em> = último mês fechado; <em>"Este mês"</em> = mês corrente.</li>
        <li><strong>Concessionárias (Dealers):</strong> Diferencia <code>dealer_daf</code> (rede DAF) de <code>dealer_emplacamento</code> (concessionária multimarca onde ocorreu o emplacamento). Se o usuário disser apenas "por dealer", o bot pede esclarecimento mantendo o contexto da pergunta.</li>
        <li><strong>Geografia e 6ª Região:</strong> Separa município/UF/região do emplacamento vs. do cliente. Mapeia as 5 macrorregiões do IBGE + a <strong>6ª região <code>"Não informado"</code></strong> para apoiar a qualificação cadastral.</li>
      </ul>
    </section>

    <!-- 5. Base de Dados Sintetica -->
    <section class="card">
      <h2>🗄️ 5. Modelo de Dados e Volumes de Referência (SQLite Read-Only)</h2>
      <p>A base sintética reproduz fielmente o DDL físico (<code>scripts/schema.sql</code>), as proporções reais e as armadilhas de dados:</p>
      <table>
        <thead>
          <tr>
            <th>Tabela Física</th>
            <th>Registros</th>
            <th>Papel na Arquitetura / Governança</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><code>emplacamento</code></td>
            <td>777.365</td>
            <td>Fato central de veículos novos (desde 2019). Coluna <code>placa</code> bloqueada por PII.</td>
          </tr>
          <tr>
            <td><code>chassi</code></td>
            <td>776.701</td>
            <td>Vínculo entre emplacamento e modelo (diferença de 664 linhas refere-se a histórico pré-2019 tratado).</td>
          </tr>
          <tr>
            <td><code>cliente</code></td>
            <td>109.358</td>
            <td>Usada apenas para join geográfico/CNAE agregado. Colunas de CNPJ, razão social, endereço e e-mail bloqueadas.</td>
          </tr>
          <tr>
            <td><code>cidade</code></td>
            <td>5.573</td>
            <td>Municípios IBGE + armadilhas propositais (<code>"Não informado"</code> e grafias históricas como <em>Mogi-Mirim, Parati, Embu</em>).</td>
          </tr>
          <tr>
            <td><code>dealer_emplacamento</code></td>
            <td>1.237</td>
            <td>Concessionárias multimarcas vinculadas ao emplacamento.</td>
          </tr>
          <tr>
            <td><code>modelo</code></td>
            <td>1.161</td>
            <td>Modelos ANFAVEA distribuídos nas 7 marcas: <code>VOLKSWAGEN</code>, <code>MERCEDEZ-BENZ</code>, <code>VOLVO</code>, <code>SCANIA</code>, <code>DAF</code>, <code>IVECO</code> e <code>AGRALE</code>.</td>
          </tr>
          <tr>
            <td><code>dealer_daf</code></td>
            <td>215</td>
            <td>Concessionárias da rede DAF (<code>dealer_montadora</code>).</td>
          </tr>
          <tr>
            <td><code>quadro_societario</code> / <code>cnpj_cnae</code></td>
            <td>Bloqueadas</td>
            <td><strong>Fora da allowlist:</strong> qualquer tentativa de consulta é rejeitada por <code>SecurityViolationError</code>.</td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- 6. Avaliacao e Qualidade -->
    <section class="card">
      <h2>✅ 6. Segurança, Auditoria e Avaliação Automatizada</h2>
      <div class="grid-2">
        <div class="subcard">
          <h3>🛡️ Proteções do Executor Seguro</h3>
          <ul>
            <li>Conexão SQLite URI <code>?mode=ro</code> + <code>PRAGMA query_only = ON</code>;</li>
            <li>Rejeição de qualquer comando não-<code>SELECT</code>, múltiplos statements ou comentários SQL;</li>
            <li>Supressão automática por <strong>k-anonimato (k = 5)</strong>;</li>
            <li>Log de auditoria estruturado em <code>logs/audit.jsonl</code> sem segredos ou PII.</li>
          </ul>
        </div>
        <div class="subcard">
          <h3>📊 Runner de Avaliação (<code>tests/reference_questions.yaml</code>)</h3>
          <ul>
            <li><strong>1. Acerto:</strong> respondeu e bateu com o SQL gabarito;</li>
            <li><strong>2. Recusa ou Esclarecimento Correto:</strong> identificou ambiguidade ou fora de escopo;</li>
            <li><strong>3. Erro Confiante:</strong> <strong>0 (Zero)</strong> nas perguntas centrais e gerais (100% de aprovação no gate da v0).</li>
          </ul>
        </div>
      </div>
    </section>
  </main>
</body>
</html>
"""
