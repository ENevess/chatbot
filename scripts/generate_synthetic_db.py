"""Gerador de dados sinteticos para o banco SQLite local de emplacamentos.

Segue estritamente as instrucoes das Secoes 3 e 4 do AGENTS.md:
- Volumes de referencia exatos (ou escalaveis mantendo a proporcao):
  * modelo: 1.161
  * cidade: 5.573
  * dealer_daf (dealer_montadora): 215
  * dealer_emplacamento: 1.237
  * cliente: 109.358
  * chassi: 776.701
  * emplacamento: 777.365
- As 7 marcas obrigatorias em modelo.fabricante:
  AGRALE, DAF, IVECO, SCANIA, MERCEDEZ-BENZ, VOLVO, VOLKSWAGEN
- Armadilhas conhecidas incluidas propositalmente:
  * Cidades com nome "Não informado" e variacoes historicas/antigas de nome
  * Modelos com grafias variadas (com/sem espaco, hifen, tracao no nome)
  * Emplacamentos distribuidos entre todas as marcas desde 2019
  * Diferenca de 664 registros entre emplacamento (777.365) e chassi (776.701)
  * Clientes com municipio diferente do municipio de emplacamento
"""

from __future__ import annotations

import argparse
import sqlite3
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT_DIR / "data" / "emplacamentos_synthetic.db"
DEFAULT_SCHEMA_PATH = ROOT_DIR / "scripts" / "schema.sql"

# Volumes oficiais da Secao 3 do AGENTS.md
TARGET_COUNTS = {
    "modelo": 1_161,
    "cidade": 5_573,
    "dealer_daf": 215,
    "dealer_emplacamento": 1_237,
    "cliente": 109_358,
    "chassi": 776_701,
    "emplacamento": 777_365,
    "cnae": 85,
}

# As 7 marcas solicitadas (mantendo exatamente a grafia pedida pelo usuario)
BRANDS_CONFIG = {
    "VOLKSWAGEN": {
        "weight": 0.24,
        "families": [
            ("CONSTELLATION 24.280", "SEMI-PESADO", "280 CV", "6X2"),
            ("CONSTELLATION 24.260", "SEMI-PESADO", "260 CV", "6X2"),
            ("CONSTELLATION 17.280", "SEMI-PESADO", "280 CV", "4X2"),
            ("CONSTELLATION 30.330", "SEMI-PESADO", "330 CV", "8X2"),
            ("METEOR 29.520", "PESADO", "520 CV", "6X4"),
            ("METEOR 28.460", "PESADO", "460 CV", "6X2"),
            ("CONSTELLATION 25.460", "PESADO", "460 CV", "6X2"),
            ("CONSTELLATION 33.460", "PESADO", "460 CV", "6X4"),
        ],
    },
    "MERCEDEZ-BENZ": {
        "weight": 0.23,
        "families": [
            ("ATEGO 2426", "SEMI-PESADO", "256 CV", "6X2"),
            ("ATEGO 1719", "SEMI-PESADO", "185 CV", "4X2"),
            ("ATEGO 2430", "SEMI-PESADO", "286 CV", "6X2"),
            ("ATEGO 3030", "SEMI-PESADO", "286 CV", "8X2"),
            ("ACTROS 2651", "PESADO", "510 CV", "6X4"),
            ("ACTROS 2548", "PESADO", "476 CV", "6X2"),
            ("ACTROS 2045", "PESADO", "449 CV", "4X2"),
            ("AXOR 2544", "PESADO", "439 CV", "6X2"),
            ("AXOR 3344", "PESADO", "439 CV", "6X4"),
            ("AROCS 3351", "PESADO", "510 CV", "6X4"),
        ],
    },
    "VOLVO": {
        "weight": 0.21,
        "families": [
            ("VM 270", "SEMI-PESADO", "270 CV", "6X2"),
            ("VM 290", "SEMI-PESADO", "290 CV", "6X2"),
            ("VM 330", "SEMI-PESADO", "330 CV", "8X2"),
            ("VM 360", "SEMI-PESADO", "360 CV", "6X4"),
            ("FH 540", "PESADO", "540 CV", "6X4"),
            ("FH 460", "PESADO", "460 CV", "6X2"),
            ("FH 500", "PESADO", "500 CV", "6X4"),
            ("FM 380", "PESADO", "380 CV", "6X2"),
            ("FMX 540", "PESADO", "540 CV", "6X4"),
        ],
    },
    "SCANIA": {
        "weight": 0.15,
        "families": [
            ("P 280", "SEMI-PESADO", "280 CV", "6X2"),
            ("P 320", "SEMI-PESADO", "320 CV", "8X2"),
            ("P 360", "PESADO", "360 CV", "6X4"),
            ("R 450", "PESADO", "450 CV", "6X2"),
            ("R 540", "PESADO", "540 CV", "6X4"),
            ("R 460", "PESADO", "460 CV", "6X2"),
            ("R 560", "PESADO", "560 CV", "6X4"),
            ("G 410", "PESADO", "410 CV", "6X4"),
            ("S 540", "PESADO", "540 CV", "6X4"),
        ],
    },
    "DAF": {
        "weight": 0.10,
        "families": [
            ("CF 310", "SEMI-PESADO", "310 CV", "6X2"),
            ("CF 310", "SEMI-PESADO", "310 CV", "8X2"),
            ("CF 410", "PESADO", "410 CV", "6X2"),
            ("CF 450", "PESADO", "450 CV", "6X4"),
            ("XF 530", "PESADO", "530 CV", "6X4"),
            ("XF 480", "PESADO", "480 CV", "6X2"),
            ("XF 105 460", "PESADO", "460 CV", "6X2"),
            ("XF 105 510", "PESADO", "510 CV", "6X4"),
        ],
    },
    "IVECO": {
        "weight": 0.05,
        "families": [
            ("TECTOR 24-280", "SEMI-PESADO", "280 CV", "6X2"),
            ("TECTOR 17-280", "SEMI-PESADO", "280 CV", "4X2"),
            ("TECTOR 31-300", "SEMI-PESADO", "300 CV", "8X2"),
            ("S-WAY 480", "PESADO", "480 CV", "6X2"),
            ("S-WAY 540", "PESADO", "540 CV", "6X4"),
            ("HI-WAY 440", "PESADO", "440 CV", "6X2"),
            ("HI-WAY 480", "PESADO", "480 CV", "6X2"),
            ("HI-ROAD 400", "PESADO", "400 CV", "6X2"),
        ],
    },
    "AGRALE": {
        "weight": 0.02,
        "families": [
            ("A10000", "SEMI-PESADO", "165 CV", "4X2"),
            ("14000 S", "SEMI-PESADO", "205 CV", "4X2"),
            ("14000 S", "SEMI-PESADO", "205 CV", "6X2"),
            ("22000 S", "SEMI-PESADO", "225 CV", "6X2"),
        ],
    },
}

# Polos reais de emplacamento de caminhoes no Brasil + armadilhas da Secao 3 e 4
REAL_CITIES_SEED = [
    # (nome_cidade, UF, codigo_cidade, lat, lon, microrregiao, mesorregiao)
    ("São Paulo", "SP", 3550308, -23.5505, -46.6333, "São Paulo", "Metropolitana de São Paulo"),
    ("Curitiba", "PR", 4106902, -25.4284, -49.2733, "Curitiba", "Metropolitana de Curitiba"),
    ("Ponta Grossa", "PR", 4119905, -25.0945, -50.1633, "Ponta Grossa", "Centro Oriental Paranaense"),
    ("Rondonópolis", "MT", 5107602, -16.4673, -54.6372, "Rondonópolis", "Sudeste Mato-Grossense"),
    ("Cuiabá", "MT", 5103403, -15.6014, -56.0979, "Cuiabá", "Centro-Sul Mato-Grossense"),
    ("Sinop", "MT", 5107909, -11.8608, -55.5095, "Sinop", "Norte Mato-Grossense"),
    ("Sorriso", "MT", 5107925, -12.5425, -55.7211, "Alto Teles Pires", "Norte Mato-Grossense"),
    ("Goiânia", "GO", 5208707, -16.6869, -49.2648, "Goiânia", "Centro Goiano"),
    ("Rio Verde", "GO", 5218805, -17.7923, -50.9192, "Sudoeste de Goiás", "Sul Goiano"),
    ("Itajaí", "SC", 4208203, -26.9078, -48.6619, "Itajaí", "Vale do Itajaí"),
    ("Joinville", "SC", 4209102, -26.3045, -48.8487, "Joinville", "Norte Catarinense"),
    ("Chapecó", "SC", 4204202, -27.1004, -52.6152, "Chapecó", "Oeste Catarinense"),
    ("Porto Alegre", "RS", 4314902, -30.0346, -51.2177, "Porto Alegre", "Metropolitana de Porto Alegre"),
    ("Caxias do Sul", "RS", 4305108, -29.1678, -51.1794, "Caxias do Sul", "Nordeste Rio-Grandense"),
    ("Belo Horizonte", "MG", 3106200, -19.9167, -43.9345, "Belo Horizonte", "Metropolitana de BH"),
    ("Contagem", "MG", 3118601, -19.9320, -44.0539, "Belo Horizonte", "Metropolitana de BH"),
    ("Uberlândia", "MG", 3170206, -18.9186, -48.2772, "Uberlândia", "Triângulo Mineiro"),
    ("Campinas", "SP", 3509502, -22.9099, -47.0626, "Campinas", "Campinas"),
    ("Ribeirão Preto", "SP", 3543402, -21.1704, -47.8103, "Ribeirão Preto", "Ribeirão Preto"),
    ("Guarulhos", "SP", 3518800, -23.4543, -46.5337, "Guarulhos", "Metropolitana de São Paulo"),
    ("São Bernardo do Campo", "SP", 3548708, -23.6914, -46.5646, "São Paulo", "Metropolitana de São Paulo"),
    ("Rio de Janeiro", "RJ", 3304557, -22.9068, -43.1729, "Rio de Janeiro", "Metropolitana do Rio"),
    ("Duque de Caxias", "RJ", 3301702, -22.7856, -43.3117, "Rio de Janeiro", "Metropolitana do Rio"),
    ("Resende", "RJ", 3304201, -22.4689, -44.4467, "Vale do Paraíba Fluminense", "Sul Fluminense"),
    ("Salvador", "BA", 2927408, -12.9714, -38.5014, "Salvador", "Metropolitana de Salvador"),
    ("Luís Eduardo Magalhães", "BA", 2919553, -12.0964, -45.7869, "Barreiras", "Extremo Oeste Baiano"),
    ("Feira de Santana", "BA", 2910800, -12.2664, -38.9663, "Feira de Santana", "Centro Norte Baiano"),
    ("Recife", "PE", 2611606, -8.0476, -34.8770, "Recife", "Metropolitana do Recife"),
    ("Jaboatão dos Guararapes", "PE", 2607901, -8.1128, -35.0150, "Recife", "Metropolitana do Recife"),
    ("Fortaleza", "CE", 2304400, -3.7172, -38.5433, "Fortaleza", "Metropolitana de Fortaleza"),
    ("Belém", "PA", 1501402, -1.4558, -48.4902, "Belém", "Metropolitana de Belém"),
    ("Marabá", "PA", 1504208, -5.3686, -49.1178, "Marabá", "Sudeste Paraense"),
    ("Manaus", "AM", 1302603, -3.1190, -60.0217, "Manaus", "Centro Amazonense"),
    ("Campo Grande", "MS", 5002704, -20.4697, -54.6201, "Campo Grande", "Centro Norte de MS"),
    ("Dourados", "MS", 5003702, -22.2231, -54.8120, "Dourados", "Sudoeste de MS"),
    ("Cascavel", "PR", 4104808, -24.9578, -53.4595, "Cascavel", "Oeste Paranaense"),
    ("Londrina", "PR", 4113700, -23.3045, -51.1696, "Londrina", "Norte Central Paranaense"),
    ("Maringá", "PR", 4115200, -23.4205, -51.9333, "Maringá", "Norte Central Paranaense"),
    ("Vitória", "ES", 3205309, -20.3155, -40.3128, "Vitória", "Central Espírito-Santense"),
    ("Serra", "ES", 3205002, -20.1211, -40.3074, "Vitória", "Central Espírito-Santense"),
    ("Brasília", "DF", 5300108, -15.7801, -47.9292, "Brasília", "Distrito Federal"),
    ("Palmas", "TO", 1721000, -10.1844, -48.3336, "Porto Nacional", "Oriental do Tocantins"),
    ("São Luís", "MA", 2111300, -2.5307, -44.3068, "Aglomeração Urbana de São Luís", "Norte Maranhense"),
    ("Balsas", "MA", 2101400, -7.5325, -46.0356, "Gerais de Balsas", "Sul Maranhense"),
    ("Porto Velho", "RO", 1100205, -8.7612, -63.9039, "Porto Velho", "Madeira-Guaporé"),
    ("Vilhena", "RO", 1100304, -12.7406, -60.1458, "Vilhena", "Leste Rondoniense"),
]

# Armadilhas obrigatorias de cidade (Secao 3 e 4: "Não informado" e nomes antigos/variacoes)
TRAP_CITIES_SEED = [
    ("Não informado", None, None, None, None, "Não informado", "Não informado"),
    ("NAO INFORMADO", "NI", 0, None, None, "Não informado", "Não informado"),
    ("Mogi-Mirim", "SP", 3530805, -22.4319, -46.9578, "Mogi Mirim", "Campinas"),  # grafia antiga c/ hifen
    ("Embu", "SP", 3515004, -23.6489, -46.8522, "Itapecerica da Serra", "Metropolitana de São Paulo"),  # antigo nome de Embu das Artes
    ("Parati", "RJ", 3303807, -23.2178, -44.7131, "Baía da Ilha Grande", "Sul Fluminense"),  # grafia antiga de Paraty
    ("Presidente Juscelino", "RN", 2410306, -6.1353, -35.6917, "Macaíba", "Leste Potiguar"),  # antigo nome de Serra Caiada
    (" Campo Grande ", "MS", 5002704, -20.4697, -54.6201, "Campo Grande", "Centro Norte de MS"),  # espacos extras
]

UFS_BY_REGION = [
    ("SP", 35, "Sudeste", "Interior Paulista"),
    ("MG", 31, "Sudeste", "Interior Mineiro"),
    ("RJ", 33, "Sudeste", "Interior Fluminense"),
    ("ES", 32, "Sudeste", "Interior Capixaba"),
    ("PR", 41, "Sul", "Interior Paranaense"),
    ("SC", 42, "Sul", "Interior Catarinense"),
    ("RS", 43, "Sul", "Interior Gaúcho"),
    ("MT", 51, "Centro-Oeste", "Interior Mato-Grossense"),
    ("MS", 50, "Centro-Oeste", "Interior Sul-Mato-Grossense"),
    ("GO", 52, "Centro-Oeste", "Interior Goiano"),
    ("BA", 29, "Nordeste", "Interior Baiano"),
    ("PE", 26, "Nordeste", "Interior Pernambucano"),
    ("CE", 23, "Nordeste", "Interior Cearense"),
    ("MA", 21, "Nordeste", "Interior Maranhense"),
    ("PI", 22, "Nordeste", "Interior Piauiense"),
    ("RN", 24, "Nordeste", "Interior Potiguar"),
    ("PB", 25, "Nordeste", "Interior Paraibano"),
    ("AL", 27, "Nordeste", "Interior Alagoano"),
    ("SE", 28, "Nordeste", "Interior Sergipano"),
    ("PA", 15, "Norte", "Interior Paraense"),
    ("TO", 17, "Norte", "Interior Tocantinense"),
    ("RO", 11, "Norte", "Interior Rondoniense"),
    ("AM", 13, "Norte", "Interior Amazonense"),
    ("AC", 12, "Norte", "Interior Acreano"),
    ("RR", 14, "Norte", "Interior Roraimense"),
    ("AP", 16, "Norte", "Interior Amapaense"),
]

CNAE_SEED = [
    (4930202, "Transporte rodoviário de carga, exceto produtos perigosos e mudanças, intermunicipal, interestadual e internacional"),
    (4930201, "Transporte rodoviário de carga, exceto produtos perigosos e mudanças, municipal"),
    (4930203, "Transporte rodoviário de produtos perigosos"),
    (115600, "Cultivo de soja"),
    (111301, "Cultivo de arroz"),
    (111302, "Cultivo de milho"),
    (113000, "Cultivo de cana-de-açúcar"),
    (4623108, "Comércio atacadista de matérias-primas agrícolas"),
    (4639701, "Comércio atacadista de produtos alimentícios em geral"),
    (5211701, "Armazéns gerais - emissão de warrant"),
    (5250803, "Agenciamento de cargas, exceto para o transporte marítimo"),
    (7711000, "Locação de automóveis e veículos pesados sem condutor"),
    (4120400, "Construção de edifícios"),
    (4211101, "Construção de rodovias e ferrovias"),
    (810006, "Extração de minério de ferro"),
]

DAF_GROUPS = [
    "Barigui Caminhões",
    "Caminho Concessionária",
    "Caiobá Trucks",
    "Eldorado Caminhões",
    "Fournier Trucks",
    "MacPonta Caminhões",
    "Norte Sul Caminhões",
    "Planeta Caminhões",
    "Posto 10 Trucks",
    "Rodobens Caminhões",
    "Somov Caminhões",
    "Via Trucks",
    "Vitoria Caminhões",
]


def generate_cities(total: int) -> list[tuple]:
    """Gera exatamente 5.573 cidades combinando polos reais, armadilhas e municipios do IBGE."""
    rows: list[tuple] = []
    city_id = 1

    for name, uf, code, lat, lon, micro, meso in REAL_CITIES_SEED:
        rows.append((city_id, name, uf, code, lat, lon, micro, meso))
        city_id += 1

    for name, uf, code, lat, lon, micro, meso in TRAP_CITIES_SEED:
        rows.append((city_id, name, uf, code, lat, lon, micro, meso))
        city_id += 1

    prefixes = [
        "Santa Maria", "São José", "Santo Antônio", "Boa Vista", "Nova Esperança",
        "Vila Nova", "Monte Alto", "Serra Negra", "Rio Claro", "Campo Belo",
        "Lagoa Grande", "Bela Vista", "Ouro Verde", "Água Boa", "Pouso Alegre",
        "São João", "São Pedro", "Bom Jesus", "Alto Paraíso", "Porto Rico",
    ]
    suffixes = [
        "do Sul", "do Norte", "do Oeste", "da Serra", "do Vale",
        "dos Campos", "das Flores", "do Rio Verde", "da Prata", "Novo",
    ]

    idx = 0
    while len(rows) < total:
        uf, uf_code, _region, meso = UFS_BY_REGION[idx % len(UFS_BY_REGION)]
        prefix = prefixes[(idx // len(UFS_BY_REGION)) % len(prefixes)]
        suffix = suffixes[(idx // (len(UFS_BY_REGION) * len(prefixes))) % len(suffixes)]
        city_name = f"{prefix} {suffix} ({city_id})"
        ibge_code = uf_code * 100000 + (city_id % 99999)
        lat = round(-5.0 - (idx % 25) * 1.1, 4)
        lon = round(-38.0 - (idx % 20) * 1.1, 4)
        micro = f"Microrregião {uf}-{(idx % 18) + 1:02d}"
        rows.append((city_id, city_name, uf, ibge_code, lat, lon, micro, meso))
        city_id += 1
        idx += 1

    return rows


def generate_models(total: int) -> tuple[list[tuple], dict[str, list[int]]]:
    """Gera 1.161 modelos das 7 marcas obrigatorias, com variacoes de grafia realistas."""
    rows: list[tuple] = []
    brand_to_model_ids: dict[str, list[int]] = {brand: [] for brand in BRANDS_CONFIG}

    # Variacoes de sufixos/grafias para simular dados ANFAVEA e armadilhas de grafia
    spelling_variants = [
        lambda base, tracao: f"{base} {tracao}",
        lambda base, tracao: f"{base} {tracao} EURO 5",
        lambda base, tracao: f"{base} {tracao} EURO 6",
        lambda base, tracao: f"{base.replace(' ', '')} {tracao}",  # armadilha: sem espaco (ex. FH540, XF530)
        lambda base, tracao: f"{base.replace(' ', '-')} {tracao}",  # armadilha: com hifen (ex. XF-530, R-450)
        lambda base, tracao: f"{base} {tracao.lower()}",            # armadilha: tracao minuscula (6x4)
        lambda base, tracao: f"{base}  {tracao}",                   # armadilha: espaco duplo
    ]

    subsegments = {
        "PESADO": ["RODOVIÁRIO LONGA DISTÂNCIA", "AGRO / GRANELEIRO", "FORA DE ESTRADA / OFF-ROAD", "BITREM / RODOTREM"],
        "SEMI-PESADO": ["DISTRIBUIÇÃO REGIONAL", "VOCACIONAL / CONSTRUÇÃO", "CARGA GERAL", "BEBIDAS / FRIGORÍFICO"],
    }

    model_id = 1
    brands_cycle = list(BRANDS_CONFIG.keys())

    while len(rows) < total:
        brand = brands_cycle[(model_id - 1) % len(brands_cycle)]
        families = BRANDS_CONFIG[brand]["families"]
        base_name, seg, power, tracao = families[(model_id // len(brands_cycle)) % len(families)]
        variant_fn = spelling_variants[(model_id // 17) % len(spelling_variants)]
        version_tag = f"V{(model_id // 40) + 1}" if model_id > 250 else ""
        model_name = variant_fn(base_name, tracao)
        if version_tag:
            model_name = f"{model_name} {version_tag}".strip()

        subseg_list = subsegments[seg]
        subseg = subseg_list[model_id % len(subseg_list)]
        seg_anfavea = "CAMINHÕES PESADOS (> 40T PBT/PBTC)" if seg == "PESADO" else "CAMINHÕES SEMI-PESADOS (16T A 40T PBT)"

        rows.append(
            (
                model_id,
                model_name,
                brand,
                seg,
                subseg,
                "DIESEL",
                power,
                tracao,
                seg_anfavea,
            )
        )
        brand_to_model_ids[brand].append(model_id)
        model_id += 1

    return rows, brand_to_model_ids


def generate_cnaes(total: int) -> list[tuple]:
    """Gera catalogo de CNAEs."""
    rows: list[tuple] = []
    for idx in range(total):
        if idx < len(CNAE_SEED):
            code, desc = CNAE_SEED[idx]
            rows.append((idx + 1, f"{code} - {desc}"))
        else:
            rows.append((idx + 1, f"49302{idx:02d} - Atividade Logística e Transporte Setorial {idx}"))
    return rows


def generate_dealers_daf(total: int) -> list[tuple]:
    """Gera 215 concessionarias na tabela dealer_daf."""
    rows: list[tuple] = []
    for dealer_id in range(1, total + 1):
        group = DAF_GROUPS[(dealer_id - 1) % len(DAF_GROUPS)]
        uf, _, _, _ = UFS_BY_REGION[(dealer_id - 1) % len(UFS_BY_REGION)]
        loja = f"Filial {uf} {(dealer_id // len(DAF_GROUPS)) + 1:02d}"
        rows.append((dealer_id, group, loja))
    return rows


def generate_dealers_emplacamento(total: int) -> list[tuple]:
    """Gera 1.237 concessionarias multimarca na tabela dealer_emplacamento."""
    rows: list[tuple] = []
    dealer_brands = ["AutoTruck", "ViaPesados", "RodoCenter", "BrasilCaminhões", "SulTruck", "AgroDiesel", "TransMaq"]
    for dealer_id in range(1, total + 1):
        prefix = dealer_brands[(dealer_id - 1) % len(dealer_brands)]
        cnpj = f"{10 + (dealer_id % 89):02d}.{(dealer_id * 137) % 1000:03d}.{(dealer_id * 293) % 1000:03d}/0001-{(dealer_id * 7) % 100:02d}"
        rows.append((dealer_id, f"{prefix} Concessionária {dealer_id:04d} LTDA", cnpj))
    return rows


def populate_database(
    db_path: Path = DEFAULT_DB_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    scale: float = 1.0,
    seed: int = 42,
) -> dict[str, int]:
    """Recria e popula o banco SQLite com dados sinteticos nas proporcoes da Secao 3."""
    t0 = time.perf_counter()
    _ = seed

    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    counts = {
        k: max(10, int(round(v * scale))) if k in ("cliente", "chassi", "emplacamento") else v
        for k, v in TARGET_COUNTS.items()
    }
    if scale == 1.0:
        counts = dict(TARGET_COUNTS)

    conn = sqlite3.connect(db_path)
    try:
        # Otimizacoes de bulk insert para SQLite
        conn.execute("PRAGMA synchronous = OFF;")
        conn.execute("PRAGMA journal_mode = MEMORY;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        conn.execute("PRAGMA cache_size = -128000;")
        conn.execute("PRAGMA foreign_keys = OFF;")

        # Executa apenas os CREATE TABLE primeiro e cria os indices no final para velocidade
        schema_sql = schema_path.read_text(encoding="utf-8")
        table_lines = [
            line for line in schema_sql.splitlines()
            if not line.strip().upper().startswith("CREATE INDEX")
            and not line.strip().upper().startswith("PRAGMA FOREIGN_KEYS")
        ]
        index_lines = [
            line for line in schema_sql.splitlines()
            if line.strip().upper().startswith("CREATE INDEX")
        ]
        conn.executescript("\n".join(table_lines))

        # 1. Cidades (5.573)
        cities = generate_cities(counts["cidade"])
        conn.executemany(
            "INSERT INTO cidade VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
            cities,
        )

        # 2. Modelos (1.161) com as 7 marcas obrigatorias
        models, brand_to_model_ids = generate_models(counts["modelo"])
        conn.executemany(
            "INSERT INTO modelo VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
            models,
        )

        # 3. CNAE
        cnaes = generate_cnaes(counts["cnae"])
        conn.executemany("INSERT INTO cnae VALUES (?, ?);", cnaes)

        # 4. Dealers DAF (215) e Dealers Emplacamento (1.237)
        dealers_daf = generate_dealers_daf(counts["dealer_daf"])
        conn.executemany("INSERT INTO dealer_daf VALUES (?, ?, ?);", dealers_daf)

        dealers_emp = generate_dealers_emplacamento(counts["dealer_emplacamento"])
        conn.executemany("INSERT INTO dealer_emplacamento VALUES (?, ?, ?);", dealers_emp)
        conn.commit()

        # 5. Clientes (109.358) - 100% sinteticos
        total_clientes = counts["cliente"]
        total_cities = counts["cidade"]
        total_cnaes = counts["cnae"]
        hub_city_limit = len(REAL_CITIES_SEED) + len(TRAP_CITIES_SEED)

        portes = ["DEMAIS", "GRANDE PORTE", "MEDIO PORTE", "EPP", "ME"]
        naturezas = ["206-2 - Sociedade Empresária Limitada", "205-4 - Sociedade Anônima Fechada", "230-5 - EIRELI"]

        batch_size = 50_000
        for start_id in range(1, total_clientes + 1, batch_size):
            end_id = min(start_id + batch_size - 1, total_clientes)
            client_batch = []
            for cid in range(start_id, end_id + 1):
                # 75% dos clientes concentrados nos polos + armadilhas, 25% espalhados no Brasil
                if cid % 4 != 0:
                    id_cidade = ((cid * 13) % hub_city_limit) + 1
                else:
                    id_cidade = ((cid * 37) % total_cities) + 1

                doc = f"{10000000 + cid:08d}0001{(cid * 11) % 100:02d}"
                porte = portes[cid % len(portes)]
                natureza = naturezas[cid % len(naturezas)]
                id_cnae = (cid % total_cnaes) + 1
                ano_abert = 1995 + (cid % 25)
                mes_abert = (cid % 12) + 1
                capital = float(((cid % 50) + 1) * 50_000)

                client_batch.append(
                    (
                        cid,
                        doc,
                        "PJ",
                        f"TRANSPORTADORA SINTETICA {cid:06d} LTDA",
                        f"TRANS-SINT {cid:06d}",
                        f"RODOVIA BR-{101 + (cid % 300)}, KM {(cid % 500) + 1}",
                        "GALPAO LOGISTICO",
                        "DISTRITO INDUSTRIAL",
                        id_cidade,
                        f"contato{cid}@transsintetica.com.br",
                        id_cnae,
                        natureza,
                        f"{10000 + (cid % 89999):05d}-{(cid * 3) % 1000:03d}",
                        f"{ano_abert:04d}-{mes_abert:02d}-10",
                        "ATIVA",
                        f"{ano_abert:04d}-{mes_abert:02d}-10",
                        "MATRIZ",
                        porte,
                        "2026-01-15",
                        capital,
                        "SIM",
                    )
                )
            conn.executemany(
                "INSERT INTO cliente VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
                client_batch,
            )
            conn.commit()

        # 6. Chassis (776.701) - distribuicao realista por marca e anos 2019..2026
        # Construir tabela ponderada de modelos para amostragem ultrarrapida
        weighted_models: list[tuple[int, str]] = []
        for brand, cfg in BRANDS_CONFIG.items():
            weight_slots = int(cfg["weight"] * 1000)
            m_ids = brand_to_model_ids[brand]
            for slot in range(weight_slots):
                m_id = m_ids[slot % len(m_ids)]
                weighted_models.append((m_id, brand))

        # Garantir tambem alguns modelos com < 5 emplacamentos (para testar k-anonimato = 5 da Secao 7!)
        rare_model_id = brand_to_model_ids["AGRALE"][-1]

        total_chassis = counts["chassi"]
        years = [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]
        n_weighted = len(weighted_models)

        for start_id in range(1, total_chassis + 1, batch_size):
            end_id = min(start_id + batch_size - 1, total_chassis)
            chassi_batch = []
            for ch_id in range(start_id, end_id + 1):
                if ch_id <= 3:
                    # Apenas 3 unidades deste modelo especifico para testes de contagem minima (k < 5)
                    id_modelo = rare_model_id
                else:
                    id_modelo, _ = weighted_models[(ch_id * 31 + (ch_id // 7)) % n_weighted]
                    if id_modelo == rare_model_id:
                        id_modelo = brand_to_model_ids["VOLKSWAGEN"][0]

                ano_fab = years[(ch_id * 17) % len(years)]
                ano_mod = ano_fab if (ch_id % 3 != 0) else min(2026, ano_fab + 1)
                vin = f"9BW{ano_fab % 100:02d}SINT{ch_id:08d}"
                chassi_batch.append((ch_id, vin, id_modelo, "EMPLACADO", ano_mod, ano_fab))

            conn.executemany(
                "INSERT INTO chassi VALUES (?, ?, ?, ?, ?, ?);",
                chassi_batch,
            )
            conn.commit()

        # 7. Emplacamentos (777.365)
        # Nota Secao 3: A diferenca de 664 linhas entre emplacamento (777.365) e chassi (776.701)
        # vem de registros historicos tratados.
        total_emplacamentos = counts["emplacamento"]
        total_dealers_emp = counts["dealer_emplacamento"]
        total_dealers_daf = counts["dealer_daf"]
        daf_model_set = set(brand_to_model_ids["DAF"])

        for start_id in range(1, total_emplacamentos + 1, batch_size):
            end_id = min(start_id + batch_size - 1, total_emplacamentos)
            emp_batch = []
            for emp_id in range(start_id, end_id + 1):
                ch_id = emp_id if emp_id <= total_chassis else (emp_id - total_chassis)

                # Descobre o modelo do chassi de forma deterministica (mesma formula do passo 6)
                if ch_id <= 3:
                    id_modelo = rare_model_id
                    brand = "AGRALE"
                else:
                    id_modelo, brand = weighted_models[(ch_id * 31 + (ch_id // 7)) % n_weighted]
                    if id_modelo == rare_model_id:
                        id_modelo = brand_to_model_ids["VOLKSWAGEN"][0]
                        brand = "VOLKSWAGEN"

                ano = years[(ch_id * 17) % len(years)]
                # Para 2026, geramos dados ate outubro (2026-10) como ultimo mes fechado e alguns em 2026-11
                if ano == 2026:
                    mes = ((emp_id * 7) % 10) + 1  # meses 01 a 10 fechados
                    if emp_id % 50 == 0:
                        mes = 11  # mes corrente parcial (novembro/2026)
                        dia = (emp_id % 7) + 1
                    else:
                        dia = (emp_id % 28) + 1
                else:
                    mes = ((emp_id * 7) % 12) + 1
                    dia = (emp_id % 28) + 1

                data_emp = f"{ano:04d}-{mes:02d}-{dia:02d}"

                # Municipio de emplacamento propositalmente distinto do municipio do cliente na maioria dos casos
                if emp_id % 5 != 0:
                    id_cidade_emp = ((emp_id * 19) % hub_city_limit) + 1
                else:
                    id_cidade_emp = ((emp_id * 43) % total_cities) + 1

                id_cliente = ((emp_id * 23) % total_clientes) + 1
                id_dealer_emp = ((emp_id * 11) % total_dealers_emp) + 1
                id_dealer_daf = ((emp_id * 7) % total_dealers_daf) + 1 if id_modelo in daf_model_set else None

                preco = round(480000.0 + ((emp_id % 45) * 12500.0), 2)
                placa = f"SNT{emp_id % 10:1d}{chr(65 + (emp_id % 26))}{(emp_id // 26) % 100:02d}"

                emp_batch.append(
                    (
                        emp_id,
                        data_emp,
                        ch_id,
                        id_cidade_emp,
                        preco,
                        "SIM",
                        id_cliente,
                        id_dealer_emp,
                        data_emp,
                        placa,
                        id_dealer_daf,
                    )
                )

            conn.executemany(
                "INSERT INTO emplacamento VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
                emp_batch,
            )
            conn.commit()

        # Recria os indices definidos no DDL
        for idx_sql in index_lines:
            conn.execute(idx_sql)
        conn.commit()

        # Restaura pragmas seguros
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = DELETE;")
        conn.execute("PRAGMA synchronous = NORMAL;")

        # Verifica contagens finais
        final_counts: dict[str, int] = {}
        for table in ["modelo", "cidade", "cnae", "dealer_daf", "dealer_emplacamento", "cliente", "chassi", "emplacamento"]:
            c = conn.execute(f"SELECT COUNT(*) FROM {table};").fetchone()[0]
            final_counts[table] = c

        elapsed = time.perf_counter() - t0
        print(f"População concluída em {elapsed:.2f}s. Contagens finais: {final_counts}")
        return final_counts
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Popula o banco SQLite local com dados sinteticos.")
    parser.add_argument("--scale", type=float, default=1.0, help="Escala de volume (1.0 = 100%% dos volumes do AGENTS.md)")
    args = parser.parse_args()
    populate_database(scale=args.scale)
