"""Carregador e validador da camada semantica (semantic/emplacamentos.yaml)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_SEMANTIC_PATH = ROOT_DIR / "semantic" / "emplacamentos.yaml"


class EntityDef(BaseModel):
    """Definicao de uma entidade/tabela permitida na camada semantica."""

    table: str
    alias: str
    primary_key: str
    description: str
    allowed_columns: list[str]


class RelationshipDef(BaseModel):
    """Relacionamento (JOIN) permitido entre duas entidades."""

    name: str
    from_entity: str
    to_entity: str
    join_type: str = "INNER"
    join_on: str


class DimensionDef(BaseModel):
    """Dimensao de corte ou filtro na camada semantica."""

    entity: str
    required_joins: list[str] = Field(default_factory=list)
    sql_expression: str
    description: str
    synonyms: list[str] = Field(default_factory=list)


class MetricDef(BaseModel):
    """Medida/metrica oficial da camada semantica."""

    name: str
    definition: str
    formula: str
    unit: str
    required_dimensions: list[str] = Field(default_factory=list)
    default_order: str | None = None
    default_limit: int | None = None
    default_filters: list[str] = Field(default_factory=list)
    exceptions: str
    synonyms: list[str] = Field(default_factory=list)
    numeric_example: str


class GovernanceDef(BaseModel):
    """Regras de governanca, privacidade e desambiguacao."""

    min_k_anonymity: int = 5
    require_explicit_period: bool = True
    ambiguity_rules: dict[str, str] = Field(default_factory=dict)


class SemanticCatalog(BaseModel):
    """Representacao validada de semantic/emplacamentos.yaml."""

    version: str
    owner: str
    updated_at: str
    description: str
    governance: GovernanceDef
    entities: dict[str, EntityDef]
    relationships: list[RelationshipDef]
    dimensions: dict[str, DimensionDef]
    metrics: dict[str, MetricDef]
    default_filters: dict[str, Any] = Field(default_factory=dict)

    def get_allowed_tables(self) -> set[str]:
        """Retorna o conjunto de nomes fisicos de tabelas permitidas (allowlist)."""
        return {entity.table for entity in self.entities.values()}

    def get_relationship_map(self) -> dict[str, RelationshipDef]:
        """Retorna os relacionamentos indexados pelo nome."""
        return {rel.name: rel for rel in self.relationships}

    def to_llm_summary(self) -> dict[str, Any]:
        """Retorna apenas metadados seguros (sem linhas de dados) para enviar ao LLM."""
        return {
            "version": self.version,
            "dimensions": {
                k: {"description": v.description, "synonyms": v.synonyms}
                for k, v in self.dimensions.items()
            },
            "metrics": {
                k: {
                    "name": v.name,
                    "definition": v.definition,
                    "unit": v.unit,
                    "synonyms": v.synonyms,
                }
                for k, v in self.metrics.items()
            },
            "ambiguity_rules": self.governance.ambiguity_rules,
        }


def load_semantic_catalog(path: Path = DEFAULT_SEMANTIC_PATH) -> SemanticCatalog:
    """Carrega e valida o arquivo YAML da camada semantica."""
    raw_data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SemanticCatalog.model_validate(raw_data)
