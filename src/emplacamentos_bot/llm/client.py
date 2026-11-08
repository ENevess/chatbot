"""Interface LLMClient, MockLLMClient (offline) e ClaudeLLMClient (Anthropic API).

Cumpre rigorosamente a Secao 5 do AGENTS.md e a restricao do usuario:
- O LLM recebe SOMENTE a pergunta do usuario e o resumo de metadados da camada semantica
  (nomes de metricas, dimensoes, descricoes e regras de ambiguidade).
- NENHUM dado do banco (nem mesmo sintetico ou agregado) e enviado para a API do Claude.
- A redacao final com os numeros retornados do SQLite e feita 100% localmente pelo
  ResponseFormatter (em formatter.py).
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

from emplacamentos_bot.compiler.sql_compiler import FilterSpec, PeriodSpec, QuerySpec
from emplacamentos_bot.config import load_dotenv_file
from emplacamentos_bot.semantic.loader import SemanticCatalog

KNOWN_BRANDS = [
    "MERCEDEZ-BENZ",
    "VOLKSWAGEN",
    "SCANIA",
    "VOLVO",
    "AGRALE",
    "IVECO",
    "DAF",
]

BRAND_ALIASES = {
    "MERCEDES": "MERCEDEZ-BENZ",
    "MERCEDES-BENZ": "MERCEDEZ-BENZ",
    "MERCEDEZ": "MERCEDEZ-BENZ",
    "MERCEDEZ-BENZ": "MERCEDEZ-BENZ",
    "VW": "VOLKSWAGEN",
    "VOLKS": "VOLKSWAGEN",
    "VOLKSWAGEN": "VOLKSWAGEN",
    "SCANIA": "SCANIA",
    "VOLVO": "VOLVO",
    "DAF": "DAF",
    "IVECO": "IVECO",
    "AGRALE": "AGRALE",
}

OUT_OF_SCOPE_KEYWORDS = [
    "previsão",
    "previsao",
    "prever",
    "futuro",
    "2027",
    "2028",
    "usado",
    "usados",
    "seminovo",
    "transferência",
    "transferencia",
    "cpf",
    "cnpj do cliente",
    "telefone",
    "email",
    "e-mail",
    "endereço",
    "endereco",
    "sócio",
    "socio",
    "quadro societário",
    "quadro societario",
    "opinião",
    "opiniao",
    "melhor caminhão",
    "melhor marca",
    "clima",
    "futebol",
    "cotação",
    "dolar",
]

UNSUPPORTED_METRIC_KEYWORDS = [
    "lucro",
    "margem",
    "faturamento",
    "receita",
    "ticket médio",
    "ticket medio",
    "preço médio",
    "preco medio",
    "desconto",
    "inadimplência",
    "custo",
    "estoque",
]


class LLMClient(ABC):
    """Interface abstrata para interpretacao de perguntas em QuerySpec estruturado."""

    @abstractmethod
    def interpret_question(self, question: str, catalog: SemanticCatalog) -> QuerySpec:
        """Converte uma pergunta em portugues em um QuerySpec validado contra o catalogo."""


class MockLLMClient(LLMClient):
    """Implementacao deterministica local para testes sem rede (Secao 5 e 10)."""

    def interpret_question(self, question: str, catalog: SemanticCatalog) -> QuerySpec:
        """Interpreta perguntas em PT-BR de forma deterministica sem usar rede."""
        q_raw = question.strip()
        q_lower = q_raw.lower()

        # 1. Verifica fora do escopo (Secao 2: previsoes, usados, dados pessoais, opinioes)
        for kw in OUT_OF_SCOPE_KEYWORDS:
            if kw in q_lower:
                return QuerySpec(
                    intent="refuse",
                    refusal_reason=(
                        "Esta solicitação está fora do escopo do chatbot. "
                        "A base contempla exclusivamente dados históricos agregados de emplacamentos "
                        "de caminhões novos (pesados e semi-pesados) desde 2019, sem dados individuais "
                        "de clientes/sócios, veículos usados ou previsões."
                    ),
                )

        # 2. Verifica metricas inexistentes na camada semantica (Secao 6)
        for kw in UNSUPPORTED_METRIC_KEYWORDS:
            if kw in q_lower:
                return QuerySpec(
                    intent="refuse",
                    refusal_reason=(
                        f"A métrica solicitada ('{kw}') não existe na camada semântica v0. "
                        "Posso responder sobre: Volume de Emplacamentos, Participação de Mercado por Marca, "
                        "Participação por Segmento, Ranking de Modelos e Variação entre Períodos."
                    ),
                )

        # 3. Verifica ambiguidade de Dealer (Regra 6 do dono da base)
        if ("dealer" in q_lower or "concessionária" in q_lower or "concessionaria" in q_lower):
            has_daf = (
                "dealer daf" in q_lower
                or "dealer da daf" in q_lower
                or "concessionária daf" in q_lower
                or "concessionaria daf" in q_lower
                or "rede daf" in q_lower
            )
            has_emp = (
                bool(re.search(r"(?:dealer|concession[aá]ria)\s+d[eo]\s+emplacamento", q_lower))
                or "dealer emplacamento" in q_lower
            )
            if not has_daf and not has_emp:
                return QuerySpec(
                    intent="clarify",
                    ambiguous_reason=catalog.governance.ambiguity_rules["dealer_type_ambiguous"],
                )

        # 4. Verifica ambiguidade de Cidade/Municipio quando nao especifica se e emplacamento ou cliente
        if ("município" in q_lower or "municipio" in q_lower or "cidade" in q_lower):
            has_emp_city = "emplacamento" in q_lower or "emplacado" in q_lower or "emplacados" in q_lower
            has_cli_city = "cliente" in q_lower or "comprador" in q_lower or "domicílio" in q_lower
            if not has_emp_city and not has_cli_city:
                return QuerySpec(
                    intent="clarify",
                    ambiguous_reason=catalog.governance.ambiguity_rules["city_type_ambiguous"],
                )

        # 5. Identifica a metrica
        metric = self._detect_metric(q_lower)

        # 6. Extrai periodo (Regra 2: se nao houver periodo claro, pede esclarecimento)
        period = self._extract_period(q_lower, is_variation=(metric == "variacao_periodos"))
        if period is None:
            return QuerySpec(
                intent="clarify",
                ambiguous_reason=catalog.governance.ambiguity_rules["period_missing"],
            )

        if metric == "variacao_periodos" and not period.comparison_value:
            return QuerySpec(
                intent="clarify",
                ambiguous_reason=(
                    "Para calcular a variação entre períodos, preciso que você informe os dois períodos "
                    "a comparar (por exemplo: 'variação de 2025 contra 2024' ou '2026-10 contra 2026-09')."
                ),
            )

        # 7. Extrai dimensoes e filtros
        dimensions = self._extract_dimensions(q_lower, metric)
        filters = self._extract_filters(q_raw, q_lower)
        limit = self._extract_limit(q_lower, metric)

        return QuerySpec(
            intent="query",
            metric=metric,
            dimensions=dimensions,
            filters=filters,
            period=period,
            limit=limit,
        )

    def _detect_metric(self, q_lower: str) -> str:
        if any(w in q_lower for w in ["variação", "variacao", "crescimento", "queda", "contra", "comparado", "compare", "comparar", "vs", "versus", "mom", "yoy"]):
            return "variacao_periodos"
        if any(w in q_lower for w in ["ranking", "mais emplacados", "top ", "campeões", "campeoes"]):
            return "ranking_modelos"
        if any(w in q_lower for w in ["market share", "participação", "participacao", "fatia", "share"]):
            has_brand = any(
                re.search(rf"\b{re.escape(alias.lower())}\b", q_lower)
                for alias in BRAND_ALIASES
            ) or "por marca" in q_lower or "da marca" in q_lower or "por fabricante" in q_lower
            if has_brand:
                return "participacao_mercado_marca"
            if "por segmento" in q_lower or "de cada segmento" in q_lower or "dos segmentos" in q_lower or "segmento" in q_lower:
                return "participacao_segmento"
            return "participacao_mercado_marca"
        return "volume_emplacamentos"

    def _extract_period(self, q_lower: str, is_variation: bool = False) -> PeriodSpec | None:
        # Variacao entre dois trimestres por extenso (ex.: janeiro e marco de 2025 e janeiro e marco de 2026)
        years_found = re.findall(r"\b(20(?:19|2[0-6]))\b", q_lower)
        if is_variation and len(years_found) >= 2:
            # Ordena do mais recente (value) para o anterior (comparison_value)
            y_sorted = sorted(set(years_found), reverse=True)
            if len(y_sorted) >= 2:
                y_curr, y_prev = y_sorted[0], y_sorted[1]
            else:
                y_curr, y_prev = years_found[-1], years_found[0]

            if ("janeiro" in q_lower or "jan" in q_lower) and ("março" in q_lower or "marco" in q_lower):
                return PeriodSpec(kind="quarter", value=f"{y_curr}-T1", comparison_value=f"{y_prev}-T1")
            if "abril" in q_lower and "junho" in q_lower:
                return PeriodSpec(kind="quarter", value=f"{y_curr}-T2", comparison_value=f"{y_prev}-T2")
            if "julho" in q_lower and "setembro" in q_lower:
                return PeriodSpec(kind="quarter", value=f"{y_curr}-T3", comparison_value=f"{y_prev}-T3")
            if "outubro" in q_lower and "dezembro" in q_lower:
                return PeriodSpec(kind="quarter", value=f"{y_curr}-T4", comparison_value=f"{y_prev}-T4")

        # Variacao entre 2 meses explicitos (YYYY-MM vs YYYY-MM)
        months_found = re.findall(r"\b(20(?:19|2[0-6])-(?:0[1-9]|1[0-2]))\b", q_lower)
        if is_variation and len(months_found) >= 2:
            return PeriodSpec(kind="month", value=months_found[0], comparison_value=months_found[1])

        # Variacao entre 2 anos explicitos (YYYY vs YYYY)
        if is_variation and len(years_found) >= 2:
            y_sorted = sorted(set(years_found), reverse=True)
            if len(y_sorted) >= 2:
                return PeriodSpec(kind="year", value=y_sorted[0], comparison_value=y_sorted[1])
            return PeriodSpec(kind="year", value=years_found[0], comparison_value=years_found[1])

        # Regra 2 do dono da base: 'ultimo mes' = ultimo mes fechado; 'este mes' = mes corrente
        if any(p in q_lower for p in ["último mês", "ultimo mes", "mês passado", "mes passado"]):
            return PeriodSpec(kind="last_closed_month")
        if any(p in q_lower for p in ["este mês", "este mes", "neste mês", "neste mes", "mês corrente", "mes corrente", "mês atual", "mes atual"]):
            return PeriodSpec(kind="current_month")

        # Trimestre ex: 2025-T1 ou 1º trimestre de 2025
        q_match = re.search(r"\b(20(?:19|2[0-6]))-t([1-4])\b", q_lower)
        if q_match:
            return PeriodSpec(kind="quarter", value=f"{q_match.group(1)}-T{q_match.group(2)}")

        # Mes no formato YYYY-MM
        if len(months_found) == 1:
            return PeriodSpec(kind="month", value=months_found[0])

        # Mes por extenso + ano (ex: outubro de 2026)
        month_names = {
            "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
            "abril": "04", "maio": "05", "junho": "06", "julho": "07",
            "agosto": "08", "setembro": "09", "outubro": "10", "novembro": "11", "dezembro": "12",
        }
        for m_name, m_num in month_names.items():
            if m_name in q_lower and len(years_found) == 1:
                return PeriodSpec(kind="month", value=f"{years_found[0]}-{m_num}")

        # Ano isolado (ex: em 2025)
        if len(years_found) == 1:
            return PeriodSpec(kind="year", value=years_found[0])

        return None

    def _extract_dimensions(self, q_lower: str, metric: str) -> list[str]:
        dims: list[str] = []
        if "por região do cliente" in q_lower or "região do cliente" in q_lower:
            dims.append("regiao_cliente")
        elif "por região" in q_lower or "por regiao" in q_lower or "regiões" in q_lower or "regioes" in q_lower:
            dims.append("regiao_emplacamento")

        if "por uf do cliente" in q_lower or "por estado do cliente" in q_lower:
            dims.append("uf_cliente")
        elif "por uf" in q_lower or "por estado" in q_lower:
            dims.append("uf_emplacamento")

        if "município do cliente" in q_lower or "municipio do cliente" in q_lower or "cidade do cliente" in q_lower:
            dims.append("municipio_cliente")
        elif "por município" in q_lower or "por municipio" in q_lower or "por cidade" in q_lower:
            dims.append("municipio_emplacamento")

        if "dealer daf" in q_lower or "dealer da daf" in q_lower or "concessionária daf" in q_lower or "concessionaria daf" in q_lower or "rede daf" in q_lower:
            dims.append("dealer_daf")
        elif (
            "dealer de emplacamento" in q_lower
            or "dealer do emplacamento" in q_lower
            or "dealer emplacamento" in q_lower
            or "concessionária de emplacamento" in q_lower
            or "concessionaria de emplacamento" in q_lower
        ):
            dims.append("dealer_emplacamento")

        if "por segmento" in q_lower and metric == "volume_emplacamentos":
            dims.append("segmento")
        if (
            "por marca" in q_lower
            or "por fabricante" in q_lower
            or "quais fabricantes" in q_lower
            or "quais marcas" in q_lower
        ):
            dims.append("marca")
        if "por modelo" in q_lower and metric == "volume_emplacamentos":
            dims.append("modelo")

        return dims

    def _extract_filters(self, q_raw: str, q_lower: str) -> list[FilterSpec]:
        filters: list[FilterSpec] = []

        # Filtro de marca
        for alias, official in sorted(BRAND_ALIASES.items(), key=lambda x: -len(x[0])):
            if re.search(rf"\b{re.escape(alias.lower())}\b", q_lower):
                filters.append(FilterSpec(dimension="marca", operator="=", value=official))
                break

        # Filtro de segmento
        if "semi-pesado" in q_lower or "semipesado" in q_lower or "semi-pesados" in q_lower:
            filters.append(FilterSpec(dimension="segmento", operator="=", value="SEMI-PESADO"))
        elif re.search(r"\bpesados?\b", q_lower) and "pesados e semi-pesados" not in q_lower:
            filters.append(FilterSpec(dimension="segmento", operator="=", value="PESADO"))

        # Filtro de modelo especifico (ex: modelo '14000-S 4X2 V29' entre aspas)
        quoted_model = re.search(r"modelo\s+['\"]([^'\"]+)['\"]", q_raw, flags=re.IGNORECASE)
        if quoted_model:
            filters.append(FilterSpec(dimension="modelo", operator="=", value=quoted_model.group(1)))

        return filters

    def _extract_limit(self, q_lower: str, metric: str) -> int | None:
        top_match = re.search(r"\btop\s+(\d+)\b", q_lower)
        if top_match:
            return int(top_match.group(1))
        if metric == "ranking_modelos":
            return 10
        return None


class ClaudeLLMClient(LLMClient):
    """Cliente que utiliza a API da Anthropic (Claude) APENAS para traduzir a pergunta em QuerySpec.

    GARANTIA DE PRIVACIDADE E ISOLAMENTO:
    - O Claude recebe SOMENTE a pergunta textual do usuario e os metadados de `catalog.to_llm_summary()`.
    - Nenhum registro, contagem ou linha do banco SQLite (mesmo sintetico) e enviado ao Claude.
    """

    ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        reference_date: str = "2026-11-08",
    ) -> None:
        load_dotenv_file()
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY") or os.getenv("LLM_API_KEY")
        self.model = model or os.getenv("LLM_MODEL", "claude-haiku-5-5")
        self.reference_date = reference_date

    def build_messages_payload(self, question: str, catalog: SemanticCatalog) -> dict[str, Any]:
        """Monta o payload da requisicao Anthropic garantindo que apenas metadados semanticos subam."""
        semantic_summary = catalog.to_llm_summary()
        system_prompt = (
            "Você é o interpretador semântico de um chatbot corporativo de emplacamentos de caminhões "
            "(pesados e semi-pesados novos desde 2019).\n"
            f"Data de referência do sistema: {self.reference_date}.\n\n"
            "REGRAS INEGOCIÁVEIS:\n"
            "1. Você NÃO escreve SQL e NÃO calcula números.\n"
            "2. Converta a pergunta do usuário estritamente em um objeto JSON correspondente ao schema QuerySpec:\n"
            "   {\n"
            '     "intent": "query" | "clarify" | "refuse",\n'
            '     "metric": string | null,\n'
            '     "dimensions": [string],\n'
            '     "filters": [{"dimension": string, "operator": "=" | "IN" | "LIKE", "value": any}],\n'
            '     "period": {"kind": "year"|"month"|"quarter"|"date_range"|"current_month"|"last_closed_month", "value": string|null, "comparison_value": string|null} | null,\n'
            '     "limit": int | null,\n'
            '     "ambiguous_reason": string | null,\n'
            '     "refusal_reason": string | null\n'
            "   }\n"
            "3. Se o usuário NÃO informar o período na pergunta, retorne intent='clarify' pedindo o período. Não assuma período padrão.\n"
            "4. Se o usuário disser 'último mês', use period.kind='last_closed_month'. Se disser 'este mês', use period.kind='current_month'.\n"
            "5. Se o usuário comparar períodos como 'janeiro a março de 2025 e janeiro a março de 2026', use metric='variacao_periodos', period={'kind':'quarter', 'value':'2026-T1', 'comparison_value':'2025-T1'}. Se também pedir participação por marca/fabricante, adicione dimensions=['marca'].\n"
            "6. Se o usuário pedir 'por dealer/concessionária' sem especificar 'Dealer DAF' vs 'Dealer de emplacamento', retorne intent='clarify'.\n"
            "7. Se o usuário pedir 'por cidade/município' sem especificar se é do emplacamento ou do cliente, retorne intent='clarify'.\n"
            "8. Se pedir métrica que não existe no catálogo ou assunto fora do escopo (previsões, usados, dados pessoais/sócios), retorne intent='refuse'.\n"
            "9. Retorne SEMPRE um ÚNICO objeto JSON válido (nunca retorne texto fora do JSON).\n\n"
            f"CATÁLOGO SEMÂNTICO DISPONÍVEL:\n{json.dumps(semantic_summary, ensure_ascii=False, indent=2)}"
        )

        return {
            "model": self.model,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": question},
            ],
        }

    def interpret_question(self, question: str, catalog: SemanticCatalog) -> QuerySpec:
        """Envia apenas a pergunta e o catalogo para o Claude e valida o QuerySpec retornado."""
        if not self.api_key:
            raise RuntimeError(
                "Chave da API do Claude não configurada. Defina ANTHROPIC_API_KEY no ambiente "
                "ou use LLM_PROVIDER=mock."
            )

        payload = self.build_messages_payload(question, catalog)
        data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            self.ANTHROPIC_API_URL,
            data=data,
            headers={
                "content-type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                resp_body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            err_detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Erro na chamada à API Claude ({exc.code}): {err_detail}") from exc

        text_blocks = [
            block.get("text", "")
            for block in resp_body.get("content", [])
            if block.get("type") == "text"
        ]
        raw_text = "\n".join(text_blocks).strip()

        parsed = extract_json_object(raw_text)
        if parsed is None:
            # Fallback deterministico local caso o modelo retorne formato nao-JSON
            return MockLLMClient().interpret_question(question, catalog)
        return QuerySpec.model_validate(parsed)


def extract_json_object(raw_text: str) -> dict[str, Any] | None:
    """Extrai de forma resiliente o primeiro objeto JSON valido de uma resposta de texto do LLM."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text.strip(), flags=re.IGNORECASE).strip()
    if not cleaned:
        return None
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # Procura o primeiro bloco { ... } balanceado dentro do texto
    start_idx = cleaned.find("{")
    if start_idx == -1:
        return None

    depth = 0
    in_str = False
    escape = False
    for idx in range(start_idx, len(cleaned)):
        ch = cleaned[idx]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if not in_str:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = cleaned[start_idx : idx + 1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        return None
    return None


def create_llm_client(provider: str | None = None) -> LLMClient:
    """Fabrica de LLMClient configuravel por variavel de ambiente (LLM_PROVIDER)."""
    load_dotenv_file()
    chosen = (provider or os.getenv("LLM_PROVIDER", "mock")).strip().lower()
    if chosen in ("claude", "anthropic"):
        return ClaudeLLMClient()
    if chosen == "mock":
        return MockLLMClient()
    raise ValueError(f"Provedor LLM desconhecido: '{chosen}'. Use 'mock' ou 'claude'.")
