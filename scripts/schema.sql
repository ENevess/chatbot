PRAGMA foreign_keys = ON;

CREATE TABLE modelo (
    id_modelo INTEGER NOT NULL PRIMARY KEY,
    modelo TEXT NOT NULL,
    fabricante TEXT NOT NULL,
    segmento TEXT NOT NULL,
    subsegmento TEXT NOT NULL,
    combustivel TEXT NOT NULL,
    potencia TEXT,
    tracao_anfavea TEXT,
    segmento_anfavea TEXT
);

CREATE TABLE cidade (
    id_cidade INTEGER NOT NULL PRIMARY KEY,
    nome_cidade TEXT NOT NULL,
    UF TEXT,
    codigo_cidade INTEGER,
    latitude REAL,
    longitude REAL,
    microrregiao TEXT,
    mesorregiao TEXT
);

CREATE TABLE cnae (
    id_cnae INTEGER NOT NULL PRIMARY KEY,
    nome_cnae TEXT NOT NULL
);

CREATE TABLE dealer_daf (
    id_dealer_daf INTEGER NOT NULL PRIMARY KEY,
    nome_dealer TEXT NOT NULL,
    loja TEXT
);

CREATE TABLE dealer_emplacamento (
    id_dealer_emplacamento INTEGER NOT NULL PRIMARY KEY,
    nome_dealer TEXT NOT NULL,
    cnpj TEXT
);

CREATE TABLE chassi (
    id_chassi INTEGER NOT NULL PRIMARY KEY,
    chassi TEXT NOT NULL,
    id_modelo INTEGER NOT NULL REFERENCES modelo (id_modelo),
    situacao_chassi TEXT,
    ano_modelo INTEGER NOT NULL,
    ano_fabricacao INTEGER NOT NULL
);

CREATE TABLE cliente (
    id_cliente INTEGER NOT NULL PRIMARY KEY,
    numero_documento TEXT NOT NULL,
    tipo_pessoa TEXT NOT NULL,
    razao_social TEXT NOT NULL,
    nome_fantasia TEXT,
    endereco TEXT NOT NULL,
    complemento TEXT,
    bairro TEXT,
    id_cidade INTEGER NOT NULL REFERENCES cidade (id_cidade),
    email TEXT NOT NULL,
    id_cnae INTEGER REFERENCES cnae (id_cnae),
    natureza_juridica TEXT,
    cep TEXT,
    data_abertura DATE,
    situacao_empresa TEXT,
    data_situacao DATE,
    tipo_empresa TEXT,
    porte_empresa TEXT,
    ultima_atualizacao DATE,
    capital_social_empresa DECIMAL(18, 2),
    numero_documento_valido TEXT
);

CREATE TABLE emplacamento (
    id_emplacamento INTEGER NOT NULL PRIMARY KEY,
    data_emplacamento DATE NOT NULL,
    id_chassi INTEGER NOT NULL REFERENCES chassi (id_chassi),
    id_cidade INTEGER NOT NULL REFERENCES cidade (id_cidade),
    preco NUMERIC(10, 2),
    preco_validado TEXT,
    id_cliente INTEGER NOT NULL REFERENCES cliente (id_cliente),
    id_dealer_emplacamento INTEGER NOT NULL REFERENCES dealer_emplacamento (id_dealer_emplacamento),
    data_atualizacao DATE NOT NULL,
    placa TEXT NOT NULL,
    id_dealer_daf INTEGER REFERENCES dealer_daf (id_dealer_daf)
);

CREATE TABLE cnpj_cnae (
    numero_documento TEXT NOT NULL,
    id_cnae INTEGER NOT NULL,
    descricao_cnae TEXT NOT NULL,
    principal TEXT NOT NULL
);

CREATE TABLE quadro_societario (
    numero_documento TEXT NOT NULL,
    nome_socio TEXT,
    qualificacao TEXT,
    pais_origem TEXT,
    nome_representante_legal TEXT,
    qualificacao_representante_legal TEXT
);

CREATE INDEX idx_chassi_modelo ON chassi (id_modelo);
CREATE INDEX idx_cliente_cidade ON cliente (id_cidade);
CREATE INDEX idx_cliente_cnae ON cliente (id_cnae);
CREATE INDEX idx_emplacamento_data ON emplacamento (data_emplacamento);
CREATE INDEX idx_emplacamento_chassi ON emplacamento (id_chassi);
CREATE INDEX idx_emplacamento_cidade ON emplacamento (id_cidade);
CREATE INDEX idx_emplacamento_cliente ON emplacamento (id_cliente);
CREATE INDEX idx_emplacamento_dealer ON emplacamento (id_dealer_emplacamento);
CREATE INDEX idx_emplacamento_dealer_daf ON emplacamento (id_dealer_daf);