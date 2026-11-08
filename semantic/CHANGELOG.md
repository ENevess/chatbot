# Changelog da Camada Semântica

Todas as alterações de definições, métricas, dimensões, filtros padrão ou relacionamentos em [semantic/emplacamentos.yaml](file:///e:/testeChat/semantic/emplacamentos.yaml) devem ser registradas neste arquivo (conforme Seção 6 do [AGENTS.md](file:///e:/testeChat/AGENTS.md)).

## [0.1.0] - 2026-11-08
### Adicionado
- **Integração LLM Homologada:** Configurado suporte ao provedor Anthropic utilizando o modelo **Claude Haiku 5.5** esclusivamente para tradução de intenção em `QuerySpec` (sem envio de dados do banco e sem parâmetro `temperature`).
- **Entidades e Relacionamentos:** Mapeamento oficial de `emplacamento`, `chassi`, `modelo`, `cidade_emplacamento`, `cliente`, `cidade_cliente`, `dealer_daf`, `dealer_emplacamento` e `cnae`, excluindo colunas de PII e tabelas sensíveis (`quadro_societario`, `cnpj_cnae`).
- **Dimensões:**
  - Tempo: `ano`, `mes`, `trimestre`.
  - Produto: `marca` (`modelo.fabricante`), `modelo`, `segmento` (`modelo.segmento`), `subsegmento`, `tracao`.
  - Geografia separada entre local do emplacamento (`municipio_emplacamento`, `uf_emplacamento`, `regiao_emplacamento`) e domicílio do cliente (`municipio_cliente`, `uf_cliente`, `regiao_cliente`).
  - Mapeamento das 5 macrorregiões do IBGE + **6ª região `"Não informado"`** para permitir qualificação de dados incompletos.
  - Concessionárias separadas em `dealer_daf` (Dealer DAF / Dealer da DAF) e `dealer_emplacamento` (concessionária do emplacamento).
- **Métricas Oficiais (aprovadas pelo dono da base):**
  1. `volume_emplacamentos`: `COUNT(id_emplacamento)`
  2. `participacao_mercado_marca`: participação percentual da marca sobre o total de emplacamentos do período (`2` casas decimais).
  3. `participacao_segmento`: participação percentual do segmento (`PESADO`, `SEMI-PESADO`) sobre o total do período.
  4. `ranking_modelos`: ordenação decrescente de modelos por `COUNT(id_emplacamento)`.
  5. `variacao_periodos`: variação absoluta e percentual entre dois períodos explícitos (MoM / YoY).
- **Regras de Governança e Ambiguidade:**
  - Exigência obrigatória de período explícito (sem suposições pelo bot).
  - `"último mês"` = último mês fechado; `"este mês"` = mês corrente.
  - Pedido de esclarecimento obrigatório se "dealer" ou "cidade/município" forem mencionados sem especificar o tipo.
  - Contagem mínima $k = 5$ para privacidade.
