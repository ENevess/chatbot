"""Formatador local deterministico de respostas em PT-BR (Secao 8 do AGENTS.md).

GARANTIA DE PRIVACIDADE:
- Nenhum resultado do banco de dados sobe para o LLM (Claude).
- Toda resposta com numero e redigida localmente por este modulo trazendo:
  1. A resposta direta, em uma ou duas frases;
  2. O periodo e os filtros aplicados;
  3. A definicao da metrica usada, em uma linha;
  4. Se o resultado foi omitido ou agrupado por privacidade.
"""

from __future__ import annotations

from typing import Any

from emplacamentos_bot.compiler.sql_compiler import CompiledQuery
from emplacamentos_bot.executor.safe_executor import ExecutionResult


def _fmt_int(val: Any) -> str:
    """Formata inteiros no padrao brasileiro (ex: 777.365)."""
    if val is None:
        return "[Suprimido por privacidade]"
    return f"{int(val):,}".replace(",", ".")


def _fmt_pct(val: Any) -> str:
    """Formata percentuais no padrao brasileiro (ex: 24,00%)."""
    if val is None:
        return "[Suprimido por privacidade]"
    return f"{float(val):.2f}%".replace(".", ",")


class ResponseFormatter:
    """Formata respostas de sucesso, esclarecimento e recusa segundo a Secao 8."""

    def format_query_response(
        self,
        compiled: CompiledQuery,
        result: ExecutionResult,
        min_k: int = 5,
    ) -> str:
        """Gera o texto completo da resposta com os 4 blocos obrigatorios da Secao 8."""
        direct_answer = self._build_direct_answer(compiled, result, min_k)

        privacy_note = (
            f"Sim — {result.suppressed_count} registro(s) com contagem inferior a {min_k} "
            "unidades foram suprimidos por privacidade (contagem mínima)."
            if result.privacy_suppressed
            else f"Não — todos os grupos atendem à contagem mínima de privacidade (k >= {min_k})."
        )

        clean_def = " ".join(compiled.metric_definition.split())

        lines = [
            f"1. **Resposta direta:** {direct_answer}",
            f"2. **Período e filtros aplicados:** Período: {compiled.period_label} | Filtros: {compiled.applied_filters_label}.",
            f"3. **Definição da métrica ({compiled.metric_name}):** {clean_def}",
            f"4. **Privacidade:** {privacy_note}",
        ]
        return "\n".join(lines)

    def format_clarification(self, reason: str) -> str:
        """Formata um pedido claro de esclarecimento quando a pergunta e ambigua."""
        clean_reason = " ".join(reason.split())
        return f"**Esclarecimento necessário:** {clean_reason}"

    def format_refusal(self, reason: str) -> str:
        """Formata uma recusa educada com sugestao do que o chatbot consegue responder."""
        clean_reason = " ".join(reason.split())
        return (
            f"**Não é possível responder a esta consulta:** {clean_reason}\n"
            "Sugestão: consulte o volume de emplacamentos, a participação de mercado por marca, "
            "a participação por segmento (PESADO / SEMI-PESADO), o ranking de modelos ou a variação "
            "entre períodos informando o período desejado (desde 2019)."
        )

    def _build_direct_answer(
        self,
        compiled: CompiledQuery,
        result: ExecutionResult,
        min_k: int,
    ) -> str:
        rows = result.rows
        if not rows:
            return "Não foram encontrados registros de emplacamentos para o período e filtros informados."

        # Se todas as linhas retornadas foram suprimidas por k-anonimato
        visible_rows = [r for r in rows if not r.get("suprimido_privacidade")]
        if not visible_rows:
            return (
                f"O resultado possui menos de {min_k} registros e foi integralmente omitido "
                "pela regra de contagem mínima de privacidade."
            )

        m_key = compiled.metric_key

        if m_key == "variacao_periodos":
            row0 = visible_rows[0]
            # Caso agrupado por dimensao (ex.: marca com share e ganho/perda de participacao)
            if "share_atual" in row0 and len(visible_rows) > 1:
                dim_col = next(
                    (k for k in row0 if k not in (
                        "volume_atual", "volume_anterior", "total_atual", "total_anterior",
                        "variacao_absoluta", "valor", "share_atual", "share_anterior",
                        "delta_share_pp", "suprimido_privacidade"
                    )),
                    "marca",
                )
                tot_atual_int = int(row0.get("total_atual") or 0)
                tot_ant_int = int(row0.get("total_anterior") or 0)
                tot_diff = tot_atual_int - tot_ant_int
                tot_pct = round((tot_diff * 100.0) / tot_ant_int, 2) if tot_ant_int else 0.0
                tot_sign = "+" if tot_diff >= 0 else ""

                brand_parts: list[str] = []
                gainers: list[str] = []
                losers: list[str] = []
                for r in visible_rows:
                    label = str(r.get(dim_col))
                    v_ant = _fmt_int(r.get("volume_anterior"))
                    v_atu = _fmt_int(r.get("volume_atual"))
                    yoy = float(r.get("valor") or 0.0)
                    yoy_sign = "+" if yoy >= 0 else ""
                    s_ant = _fmt_pct(r.get("share_anterior"))
                    s_atu = _fmt_pct(r.get("share_atual"))
                    delta_pp = float(r.get("delta_share_pp") or 0.0)
                    pp_sign = "+" if delta_pp >= 0 else ""
                    pp_str = f"{pp_sign}{delta_pp:.2f}".replace(".", ",") + " p.p."

                    brand_parts.append(
                        f"{label}: {v_ant} para {v_atu} un. (YoY {yoy_sign}{_fmt_pct(yoy)} | Share {s_ant} para {s_atu}, {pp_str})"
                    )
                    if delta_pp > 0:
                        gainers.append(f"{label} ({pp_str})")
                    elif delta_pp < 0:
                        losers.append(f"{label} ({pp_str})")

                summary_line = (
                    f"No comparativo ({compiled.period_label}), o volume total passou de "
                    f"{_fmt_int(tot_ant_int)} para {_fmt_int(tot_atual_int)} unidades "
                    f"({tot_sign}{_fmt_int(tot_diff)} un., YoY {tot_sign}{_fmt_pct(tot_pct)}). "
                    f"Por {dim_col}: {'; '.join(brand_parts)}. "
                    f"Ganharam participação: {', '.join(gainers) if gainers else 'nenhum'}. "
                    f"Perderam participação: {', '.join(losers) if losers else 'nenhum'}."
                )
                return summary_line

            row = row0
            atual = _fmt_int(row.get("volume_atual"))
            ant = _fmt_int(row.get("volume_anterior"))
            diff = int(row.get("variacao_absoluta") or 0)
            sign = "+" if diff >= 0 else ""
            pct = _fmt_pct(row.get("valor"))
            return (
                f"O volume de emplacamentos passou de {ant} para {atual} unidades no comparativo "
                f"({compiled.period_label}), uma variação de {sign}{_fmt_int(diff)} unidades ({sign}{pct})."
            )

        if m_key in ("participacao_mercado_marca", "participacao_segmento"):
            dim_col = "marca" if m_key == "participacao_mercado_marca" else "segmento"
            parts = [
                f"{r[dim_col]}: {_fmt_pct(r['valor'])} ({_fmt_int(r['volume'])} un.)"
                for r in visible_rows
            ]
            return f"A participação no período foi distribuída da seguinte forma: {'; '.join(parts)}."

        if m_key == "ranking_modelos":
            items = [
                f"{idx}º {r.get('modelo')} ({r.get('marca')}): {_fmt_int(r.get('valor'))} un."
                for idx, r in enumerate(visible_rows, start=1)
            ]
            return f"Os modelos mais emplacados no período foram: {'; '.join(items)}."

        # volume_emplacamentos (escalar ou agrupado por dimensao)
        if len(rows) == 1 and len(rows[0]) <= 2:
            total = _fmt_int(visible_rows[0].get("valor"))
            return f"Foram registrados {total} emplacamentos de caminhões novos no período consultado."

        dim_keys = [k for k in visible_rows[0] if k not in ("valor", "suprimido_privacidade")]
        breakdown = [
            f"{' / '.join(str(r[k]) for k in dim_keys)}: {_fmt_int(r['valor'])} un."
            for r in visible_rows
        ]
        return f"O volume de emplacamentos por recorte foi: {'; '.join(breakdown)}."
