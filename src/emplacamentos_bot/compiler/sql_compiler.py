"""Compilador deterministico que traduz especificacoes JSON estruturadas em SQL SELECT.

Garante as regras da Secao 5, 6, 7 e 8 do AGENTS.md:
- O LLM nunca escreve SQL livre.
- Toda metrica, dimensao e filtro precisa existir em semantic/emplacamentos.yaml.
- Se faltar periodo (quando exigido) ou houver ambiguidade (ex.: dealer sem tipo,
  municipio sem especificar emplacamento vs. cliente), levanta erro/status de esclarecimento.
- Usa query parametrizada (:param) para valores de filtro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

from emplacamentos_bot.semantic.loader import SemanticCatalog


class PeriodSpec(BaseModel):
    """Especificacao de periodo da consulta."""

    kind: Literal["year", "month", "quarter", "date_range", "current_month", "last_closed_month"]
    value: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    comparison_value: str | None = None  # Usado na metrica variacao_periodos


class FilterSpec(BaseModel):
    """Filtro sobre uma dimensao permitida na camada semantica."""

    dimension: str
    operator: Literal["=", "IN", "LIKE"] = "="
    value: str | int | list[str | int]


class QuerySpec(BaseModel):
    """Especificacao estruturada gerada a partir da intencao da pergunta."""

    intent: Literal["query", "clarify", "refuse"] = "query"
    metric: str | None = None
    dimensions: list[str] = Field(default_factory=list)
    filters: list[FilterSpec] = Field(default_factory=list)
    period: PeriodSpec | None = None
    limit: int | None = None
    ambiguous_reason: str | None = None
    refusal_reason: str | None = None


@dataclass
class CompiledQuery:
    """Resultado da compilacao deterministica para SQL."""

    sql: str
    params: dict[str, Any] = field(default_factory=dict)
    metric_key: str = ""
    metric_name: str = ""
    metric_definition: str = ""
    period_label: str = ""
    applied_filters_label: str = ""


class SemanticValidationError(ValueError):
    """Erro quando a especificacao pede metrica ou dimensao inexistente."""


class AmbiguousQueryError(ValueError):
    """Erro quando a especificacao e ambigua ou omite periodo obrigatorio."""


def resolve_relative_period(
    period: PeriodSpec,
    reference_date: str = "2026-11-08",
) -> tuple[str, str, str]:
    """Resolve um PeriodSpec em (clausula_sql, label_ptbr, valor_resolvido).

    Regra oficial definida pelo dono da base:
    - 'ultimo mes' (last_closed_month) -> ultimo mes fechado em relacao a reference_date.
    - 'este mes' (current_month) -> mes corrente de reference_date.
    """
    ref_year = int(reference_date[:4])
    ref_month = int(reference_date[5:7])

    if period.kind == "current_month":
        ym = f"{ref_year:04d}-{ref_month:02d}"
        return "strftime('%Y-%m', e.data_emplacamento) = :period_val", f"mês corrente ({ym})", ym

    if period.kind == "last_closed_month":
        if ref_month == 1:
            closed_year, closed_month = ref_year - 1, 12
        else:
            closed_year, closed_month = ref_year, ref_month - 1
        ym = f"{closed_year:04d}-{closed_month:02d}"
        return "strftime('%Y-%m', e.data_emplacamento) = :period_val", f"último mês fechado ({ym})", ym

    if period.kind == "month":
        if not period.value:
            raise AmbiguousQueryError("O mês específico não foi informado.")
        return "strftime('%Y-%m', e.data_emplacamento) = :period_val", f"mês {period.value}", period.value

    if period.kind == "year":
        if not period.value:
            raise AmbiguousQueryError("O ano específico não foi informado.")
        return "strftime('%Y', e.data_emplacamento) = :period_val", f"ano de {period.value}", str(period.value)

    if period.kind == "quarter":
        if not period.value:
            raise AmbiguousQueryError("O trimestre específico não foi informado.")
        expr = (
            "strftime('%Y', e.data_emplacamento) || '-T' || "
            "CAST(((CAST(strftime('%m', e.data_emplacamento) AS INTEGER) - 1) / 3) + 1 AS TEXT)"
        )
        return f"{expr} = :period_val", f"trimestre {period.value}", period.value

    if period.kind == "date_range":
        if not period.start_date or not period.end_date:
            raise AmbiguousQueryError("O intervalo de datas precisa de data inicial e final.")
        return (
            "e.data_emplacamento BETWEEN :period_start AND :period_end",
            f"período de {period.start_date} a {period.end_date}",
            f"{period.start_date}..{period.end_date}",
        )

    raise AmbiguousQueryError("Tipo de período não reconhecido.")


class SQLCompiler:
    """Compilador deterministico de QuerySpec para SQLite SELECT."""

    def __init__(self, catalog: SemanticCatalog, reference_date: str = "2026-11-08") -> None:
        self.catalog = catalog
        self.reference_date = reference_date

    def compile(self, spec: QuerySpec) -> CompiledQuery:
        """Valida a QuerySpec contra a camada semantica e gera o SQL SELECT deterministico."""
        if spec.intent == "clarify":
            raise AmbiguousQueryError(
                spec.ambiguous_reason
                or self.catalog.governance.ambiguity_rules.get("period_missing", "Pergunta ambígua.")
            )
        if spec.intent == "refuse":
            raise SemanticValidationError(
                spec.refusal_reason or "Solicitação fora do escopo da camada semântica."
            )

        if not spec.metric or spec.metric not in self.catalog.metrics:
            raise SemanticValidationError(
                f"Métrica '{spec.metric}' não existe na camada semântica. "
                f"Métricas disponíveis: {', '.join(self.catalog.metrics.keys())}."
            )

        # Regra inegociavel #2: O usuario e responsavel por informar o periodo
        if self.catalog.governance.require_explicit_period and spec.period is None:
            raise AmbiguousQueryError(
                self.catalog.governance.ambiguity_rules["period_missing"]
            )

        metric_def = self.catalog.metrics[spec.metric]

        # Combina dimensoes pedidas com as dimensoes obrigatorias da metrica
        all_dimensions: list[str] = list(dict.fromkeys(metric_def.required_dimensions + spec.dimensions))
        for dim_name in all_dimensions:
            if dim_name not in self.catalog.dimensions:
                raise SemanticValidationError(
                    f"Dimensão '{dim_name}' não existe na camada semântica."
                )

        for flt in spec.filters:
            if flt.dimension not in self.catalog.dimensions:
                raise SemanticValidationError(
                    f"Filtro sobre dimensão inexistente '{flt.dimension}'."
                )

        if spec.metric == "variacao_periodos":
            return self._compile_period_variation(spec, metric_def, all_dimensions)

        if spec.metric in ("participacao_mercado_marca", "participacao_segmento"):
            return self._compile_share_query(spec, metric_def, all_dimensions)

        return self._compile_standard_query(spec, metric_def, all_dimensions)

    def _collect_joins(self, dimensions: list[str], filters: list[FilterSpec]) -> list[str]:
        """Coleta os relacionamentos (JOINs) necessarios na ordem correta."""
        rel_map = self.catalog.get_relationship_map()
        needed_rel_names: list[str] = []

        for dim_name in dimensions:
            for rel_name in self.catalog.dimensions[dim_name].required_joins:
                if rel_name not in needed_rel_names:
                    needed_rel_names.append(rel_name)

        for flt in filters:
            for rel_name in self.catalog.dimensions[flt.dimension].required_joins:
                if rel_name not in needed_rel_names:
                    needed_rel_names.append(rel_name)

        join_clauses: list[str] = []
        for rel_name in needed_rel_names:
            rel = rel_map[rel_name]
            target_entity = self.catalog.entities[rel.to_entity]
            join_clauses.append(
                f"{rel.join_type} JOIN {target_entity.table} {target_entity.alias} ON {rel.join_on}"
            )
        return join_clauses

    def _build_where_clause(
        self,
        period: PeriodSpec,
        filters: list[FilterSpec],
        exclude_dimension: str | None = None,
    ) -> tuple[list[str], dict[str, Any], str, str]:
        """Constroi as condicoes WHERE, parametros e descricoes de periodo/filtros."""
        where_parts: list[str] = []
        params: dict[str, Any] = {}
        filter_labels: list[str] = []

        period_sql, period_label, resolved_val = resolve_relative_period(period, self.reference_date)
        where_parts.append(period_sql)
        if period.kind == "date_range":
            params["period_start"] = period.start_date
            params["period_end"] = period.end_date
        else:
            params["period_val"] = resolved_val

        for idx, flt in enumerate(filters):
            if exclude_dimension and flt.dimension == exclude_dimension:
                continue
            dim_def = self.catalog.dimensions[flt.dimension]
            expr = " ".join(dim_def.sql_expression.split())
            p_name = f"flt_{idx}"

            if flt.operator == "=":
                where_parts.append(f"{expr} = :{p_name}")
                upper_dims = ("marca", "segmento", "uf_emplacamento", "uf_cliente")
                params[p_name] = str(flt.value).upper().strip() if flt.dimension in upper_dims else flt.value
                filter_labels.append(f"{flt.dimension}={flt.value}")
            elif flt.operator == "LIKE":
                where_parts.append(f"{expr} LIKE :{p_name}")
                params[p_name] = f"%{str(flt.value).upper().strip()}%"
                filter_labels.append(f"{flt.dimension} contendo '{flt.value}'")
            elif flt.operator == "IN" and isinstance(flt.value, list):
                in_keys = []
                for sub_idx, val in enumerate(flt.value):
                    sub_key = f"{p_name}_{sub_idx}"
                    in_keys.append(f":{sub_key}")
                    params[sub_key] = val
                where_parts.append(f"{expr} IN ({', '.join(in_keys)})")
                filter_labels.append(f"{flt.dimension} em {flt.value}")

        filters_str = ", ".join(filter_labels) if filter_labels else "nenhum filtro adicional"
        return where_parts, params, period_label, filters_str

    def _compile_standard_query(
        self,
        spec: QuerySpec,
        metric_def: Any,
        dimensions: list[str],
    ) -> CompiledQuery:
        """Compila metricas de contagem e ranking."""
        assert spec.period is not None
        joins = self._collect_joins(dimensions, spec.filters)
        where_parts, params, period_label, filters_label = self._build_where_clause(
            spec.period, spec.filters
        )

        select_parts: list[str] = []
        group_by_parts: list[str] = []

        for dim_name in dimensions:
            dim_def = self.catalog.dimensions[dim_name]
            expr = " ".join(dim_def.sql_expression.split())
            select_parts.append(f"{expr} AS {dim_name}")
            group_by_parts.append(dim_name)

        select_parts.append(f"{metric_def.formula} AS valor")
        select_parts.append("COUNT(e.id_emplacamento) AS _row_count")

        sql_lines = [
            f"SELECT {', '.join(select_parts)}",
            "FROM emplacamento e",
        ]
        sql_lines.extend(joins)
        if where_parts:
            sql_lines.append(f"WHERE {' AND '.join(where_parts)}")
        if group_by_parts:
            sql_lines.append(f"GROUP BY {', '.join(group_by_parts)}")

        order_dir = metric_def.default_order or "DESC"
        if group_by_parts or metric_def.default_order:
            sql_lines.append(f"ORDER BY valor {order_dir}")

        limit_val = spec.limit or metric_def.default_limit
        if limit_val:
            sql_lines.append(f"LIMIT {int(limit_val)}")

        return CompiledQuery(
            sql="\n".join(sql_lines),
            params=params,
            metric_key=spec.metric or "",
            metric_name=metric_def.name,
            metric_definition=metric_def.definition,
            period_label=period_label,
            applied_filters_label=filters_label,
        )

    def _compile_share_query(
        self,
        spec: QuerySpec,
        metric_def: Any,
        dimensions: list[str],
    ) -> CompiledQuery:
        """Compila participacao de mercado (por marca ou por segmento) preservando o denominador total."""
        assert spec.period is not None
        target_dim = "marca" if spec.metric == "participacao_mercado_marca" else "segmento"
        joins = self._collect_joins(dimensions, spec.filters)
        where_all, params, period_label, base_filters_label = self._build_where_clause(
            spec.period, spec.filters, exclude_dimension=target_dim
        )

        dim_expr = " ".join(self.catalog.dimensions[target_dim].sql_expression.split())

        join_str = "\n".join(joins)
        where_str = f"WHERE {' AND '.join(where_all)}" if where_all else ""

        # Verifica se o usuario filtrou uma marca ou segmento especifico para destacar no resultado
        post_filter_sql = ""
        all_filter_labels = [] if base_filters_label == "nenhum filtro adicional" else [base_filters_label]
        for idx, flt in enumerate(spec.filters):
            if flt.dimension == target_dim:
                p_key = f"target_flt_{idx}"
                params[p_key] = str(flt.value).upper().strip()
                post_filter_sql = f"WHERE {target_dim} = :{p_key}"
                all_filter_labels.append(f"{target_dim}={flt.value}")

        filters_label = ", ".join(all_filter_labels) if all_filter_labels else "nenhum filtro adicional"

        sql = (
            "WITH base_agg AS (\n"
            f"  SELECT {dim_expr} AS {target_dim},\n"
            "         COUNT(e.id_emplacamento) AS volume\n"
            "  FROM emplacamento e\n"
            f"  {join_str}\n"
            f"  {where_str}\n"
            f"  GROUP BY {target_dim}\n"
            "),\n"
            "shares AS (\n"
            f"  SELECT {target_dim},\n"
            "         volume,\n"
            "         SUM(volume) OVER () AS volume_total_mercado,\n"
            "         ROUND(volume * 100.0 / NULLIF(SUM(volume) OVER (), 0), 2) AS valor,\n"
            "         volume AS _row_count\n"
            "  FROM base_agg\n"
            ")\n"
            f"SELECT {target_dim}, volume, volume_total_mercado, valor, _row_count\n"
            "FROM shares\n"
            f"{post_filter_sql}\n"
            "ORDER BY valor DESC"
        )

        return CompiledQuery(
            sql=sql.strip(),
            params=params,
            metric_key=spec.metric or "",
            metric_name=metric_def.name,
            metric_definition=metric_def.definition,
            period_label=period_label,
            applied_filters_label=filters_label,
        )

    def _compile_period_variation(
        self,
        spec: QuerySpec,
        metric_def: Any,
        dimensions: list[str],
    ) -> CompiledQuery:
        """Compila a variacao absoluta e percentual entre dois periodos (MoM ou YoY)."""
        assert spec.period is not None
        if not spec.period.value or not spec.period.comparison_value:
            raise AmbiguousQueryError(
                "Para calcular variação entre períodos, informe os dois períodos a comparar "
                "(por exemplo: 2025 contra 2024, ou 2026-10 contra 2026-09)."
            )

        joins = self._collect_joins(dimensions, spec.filters)
        join_str = "\n".join(joins)

        time_expr = (
            "strftime('%Y', e.data_emplacamento)"
            if spec.period.kind == "year"
            else "strftime('%Y-%m', e.data_emplacamento)"
        )

        params: dict[str, Any] = {
            "p_curr": str(spec.period.value),
            "p_prev": str(spec.period.comparison_value),
        }

        extra_where: list[str] = []
        filter_labels: list[str] = []
        for idx, flt in enumerate(spec.filters):
            dim_expr = " ".join(self.catalog.dimensions[flt.dimension].sql_expression.split())
            p_key = f"flt_{idx}"
            extra_where.append(f"{dim_expr} = :{p_key}")
            params[p_key] = str(flt.value).upper().strip()
            filter_labels.append(f"{flt.dimension}={flt.value}")

        where_clause = f"WHERE {time_expr} IN (:p_curr, :p_prev)"
        if extra_where:
            where_clause += " AND " + " AND ".join(extra_where)

        sql = (
            "WITH period_totals AS (\n"
            "  SELECT\n"
            f"    SUM(CASE WHEN {time_expr} = :p_curr THEN 1 ELSE 0 END) AS volume_atual,\n"
            f"    SUM(CASE WHEN {time_expr} = :p_prev THEN 1 ELSE 0 END) AS volume_anterior,\n"
            "    COUNT(e.id_emplacamento) AS _row_count\n"
            "  FROM emplacamento e\n"
            f"  {join_str}\n"
            f"  {where_clause}\n"
            ")\n"
            "SELECT\n"
            "  volume_atual,\n"
            "  volume_anterior,\n"
            "  (volume_atual - volume_anterior) AS variacao_absoluta,\n"
            "  ROUND(((volume_atual - volume_anterior) * 100.0) / NULLIF(volume_anterior, 0), 2) AS valor,\n"
            "  _row_count\n"
            "FROM period_totals"
        )

        period_label = f"{spec.period.value} vs. {spec.period.comparison_value}"
        filters_str = ", ".join(filter_labels) if filter_labels else "nenhum filtro adicional"

        return CompiledQuery(
            sql=sql,
            params=params,
            metric_key=spec.metric or "",
            metric_name=metric_def.name,
            metric_definition=metric_def.definition,
            period_label=period_label,
            applied_filters_label=filters_str,
        )
