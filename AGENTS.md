# AGENTS.md — CHATBOT de emplacamentos (PoC local)

Este arquivo orienta agentes de código (Codex, Claude Code, Copilot etc.). Se a sua ferramenta usa outro nome de arquivo de instrução (por exemplo `CLAUDE.md`), basta renomeá-lo.

Itens marcados com **[PREENCHER]** dependem do dono da base. Nunca invente o conteúdo deles: pare e peça a informação.

---

## 1. Objetivo

Construir uma PoC local de um CHATBOT que responde, em português do Brasil, perguntas quantitativas sobre emplacamentos de caminhões pesados e semi-pesados, para uso de diretoria e gerência.

A PoC existe para validar a **camada semântica**. O LLM é só a interface de linguagem: ele entende a pergunta e redige a resposta, mas **não calcula nada de memória**. Todo número vem de uma consulta executada sobre a base.

Ordem de prioridade: **correção, depois cobertura, depois elegância.** Uma resposta errada dita com confiança é o pior resultado possível. Quando houver dúvida, recuse ou peça esclarecimento.

---

## 2. Escopo de conhecimento

- A **única fonte** de informação é a base de emplacamentos descrita na seção 3.
- Nunca responda números com base em conhecimento geral. Se a base não contém a informação, diga isso.
- Perguntas fora do escopo (outras bases, previsões, opiniões, dados de pessoas, assuntos gerais) recebem uma recusa educada e uma sugestão do que o CHATBOT consegue responder.
- O CHATBOT responde sobre **agregados**, nunca sobre indivíduos. Dados que identifiquem pessoas ou contatos não fazem parte da camada que o CHATBOT enxerga.

---

## 3. A base de emplacamentos

**Descrição:** base relacional com o sistema de emplacamentos de veículos novos. Registra modelos, clientes (pessoa jurídica), marcas e datas de emplacamento.

**Cobertura:** todos os emplacamentos desde 2019 da categoria de caminhões pesados e semi-pesados, de **todas as marcas** (não apenas a da empresa). Isso permite calcular participação de mercado a partir da própria base.

**Tabelas e volumes de referência** (o gerador sintético deve respeitar a mesma proporção):

| Tabela | Linhas |
|---|---|
| chassi | 776.701 |
| cidade | 5.573 |
| cliente | 109.358 |
| dealer_montadora | 215 |
| dealer_emplacamento | 1.237 |
| emplacamento | 777.365 |
| modelo | 1.161 |

**Relacionamentos conhecidos:**

- emplacamento → cliente, por `idcliente`
- chassi → modelo, pelo id do modelo
- chassi → emplacamento, pelo id do chassi
- cliente → cidade, por `idcidade`
- A tabela de emplacamento tem município (de emplacamento), e o cliente também tem município. São conceitos diferentes e não podem ser confundidos.
- `dealer_montadora` e `dealer_emplacamento` existem, mas a relação com emplacamento **ainda não foi descrita**. [PREENCHER]

**Fatos e regras conhecidos:**

- Só há emplacamentos de chassis **novos**. A base de transferências (usados) está fora de escopo.
- Segmento é definido por **PBT** e já vem estruturado na tabela de modelo. Os cortes de cada segmento: [PREENCHER]
- Os modelos seguem a nomenclatura da ANFAVEA.
- A tabela de cidade tem registros "Não informado" e variações antigas de nome. Trate isso nas dimensões geográficas.
- A diferença entre linhas de chassi e de emplacamento vem de registros anteriores a 2019, que já foram tratados.
- Não há grupos econômicos definidos. Não tente inferi-los.
- Futuro (não implementar agora): um De-Para de modelos por linha ou família, por exemplo todos os modelos XF numa linha XF.

**Colunas:** este arquivo não as lista. **Não presuma nomes de colunas.** Inspecione o schema real (ou o SQLite local) e gere `docs/SCHEMA.md` antes de escrever qualquer consulta.

---

## 4. Ambiente de desenvolvimento

- Use um banco **SQLite local** com a mesma estrutura da base. Se já existir um arquivo com dados importados, o caminho é: **[PREENCHER]**.
- Se não houver dados, gere **dados sintéticos** com o mesmo schema, as mesmas chaves e volumes proporcionais. O gerador deve incluir de propósito as armadilhas conhecidas: cidades "Não informado", nomes antigos de cidade, modelos com grafias variadas e emplacamentos de várias marcas.
- **Nunca** coloque dados reais, credenciais ou segredos no repositório. Não tente conectar a nenhum banco corporativo. A conexão real será feita depois, por pessoas, com as aprovações necessárias.
- Toda conexão de dados é **somente leitura**.

---

## 5. Arquitetura

Fluxo de cada pergunta:

1. Interpretar a pergunta e identificar a intenção.
2. Mapear para uma **especificação de consulta estruturada** (JSON com métrica, dimensões, filtros e período), escolhida **dentre os itens que existem na camada semântica**.
3. Um **compilador determinístico** converte a especificação em SQL. O LLM **não escreve SQL livre** na v0.
4. Executar o SQL com as proteções da seção 7.
5. Devolver ao LLM apenas o **resultado agregado**, para redigir a resposta no formato da seção 8.

**Minimização de dados:** o LLM nunca recebe linhas de dados. Ele recebe somente a pergunta, o catálogo da camada semântica (nomes, descrições, sinônimos) e o resultado agregado.

**Cliente de LLM:** implemente uma interface `LLMClient` com uma implementação **mock** (respostas fixas, para testes sem rede) e uma implementação de provedor configurável por variável de ambiente. O código não pode depender de um provedor específico.

**Interface:** primeiro uma **CLI**. Depois, uma interface web mínima (Streamlit, ou FastAPI com HTML simples). Nada de interface elaborada antes de a camada semântica passar nos testes.

---

## 6. Camada semântica

Fica em `semantic/emplacamentos.yaml`, **versionada**, com histórico em `semantic/CHANGELOG.md`. Toda mudança de definição exige uma entrada no changelog.

Conteúdo:

- **Entidades** e relacionamentos permitidos.
- **Dimensões:** tempo (mês, trimestre, ano), geografia (município, UF, região, pelo IBGE), segmento (por PBT), marca, modelo. Linha ou família só quando o De-Para existir.
- **Medidas (métricas).** Cada uma com: nome, definição em texto, fórmula, filtros padrão, exceções, sinônimos e um exemplo numérico.
- **Filtros padrão** e o tratamento de "Não informado".
- Dono e versão da camada.

Métricas iniciais sugeridas (definições exatas: **[PREENCHER pelo dono da base]**):

- volume de emplacamentos
- participação de mercado por marca
- participação por segmento
- ranking de modelos
- variação entre períodos (mês contra mês, ano contra ano)

Se uma pergunta pede algo que **não existe como métrica**, o CHATBOT recusa e diz o que falta. Ele nunca improvisa uma definição.

---

## 7. Segurança e privacidade

- O SQL gerado é **somente SELECT**, sobre uma lista de tabelas ou views permitidas (allowlist). Qualquer outra coisa é rejeitada.
- Limite de linhas, tempo máximo de execução e tamanho do resultado, todos configuráveis.
- **Contagem mínima:** se um resultado agregado tiver menos de **k** registros (k configurável, valor inicial 5), suprima ou agrupe o valor e avise que foi omitido por privacidade.
- Campos que identifiquem pessoas ou contatos **não entram na camada semântica**.
- Registre em log cada pergunta, a especificação gerada, o SQL e o status da resposta (sem dados pessoais).
- Nunca registre chaves de API, tokens ou senhas.

---

## 8. Comportamento do CHATBOT

Idioma: português do Brasil, tom profissional e direto.

Toda resposta com número traz:

1. a resposta direta, em uma ou duas frases;
2. o **período** e os **filtros** aplicados;
3. a **definição da métrica** usada, em uma linha;
4. se o resultado foi omitido ou agrupado por privacidade.

**Quando a pergunta é ambígua**, faça **uma** pergunta de esclarecimento (por exemplo: "mês corrente ou o último mês fechado?"). Não escolha em silêncio.

**Quando não puder responder**, diga com clareza o motivo: fora do escopo, métrica inexistente, dado indisponível ou resultado suprimido por privacidade. Ofereça uma alternativa que ele consiga responder.

**Nunca** apresente um número sem a consulta que o gerou.

Regra para "período não informado" (por exemplo, "neste mês"): **[PREENCHER]**.

---

## 9. Testes e avaliação

Crie `tests/reference_questions.yaml` com este formato por pergunta:

```yaml
- id: Q001
  pergunta: "Quantos caminhões foram emplacados no último mês fechado?"
  nivel: facil          # facil | media | ambigua
  central: true         # pergunta central da diretoria
  resposta_esperada: [PREENCHER]
  sql_gabarito: [PREENCHER]
  comportamento_esperado: responder   # responder | esclarecer | recusar
```

Escreva o runner de avaliação com três indicadores separados:

- **acerto** (respondeu e acertou);
- **recusa ou esclarecimento correto** (não sabia e disse);
- **erro confiante** (respondeu errado sem avisar). Este é o indicador mais importante.

Metas provisórias (a confirmar pelo responsável): pelo menos 90% de acerto no conjunto para liberar a v0; 100% nas perguntas centrais; zero erro confiante nas perguntas centrais.

Mantenha pelo menos 10 perguntas iniciais cobrindo: volume por período, por região, por segmento, por marca, por modelo, participação de mercado, comparação entre períodos, uma pergunta ambígua, uma fora do escopo e uma que exija contagem mínima. As respostas esperadas **vêm do dono da base**, não do agente.

---

## 10. Plano de tarefas (nesta ordem)

1. **Inspecionar o schema** e gerar `docs/SCHEMA.md`. *Pronto quando:* todas as tabelas, colunas e chaves estiverem documentadas.
2. **Gerador de dados sintéticos** com as armadilhas da seção 4. *Pronto quando:* o banco sintético tiver as proporções da seção 3.
3. **Camada semântica v0** (YAML) e o **compilador** de especificação para SQL. *Pronto quando:* cada métrica inicial compilar e rodar.
4. **Executor seguro** (allowlist, limites, contagem mínima). *Pronto quando:* testes mostrarem que consultas fora da allowlist são bloqueadas.
5. **Interface `LLMClient`** com o mock. *Pronto quando:* o fluxo completo rodar sem rede.
6. **CLI.** *Pronto quando:* dá para perguntar e receber a resposta no formato da seção 8.
7. **Runner de avaliação** e o conjunto de perguntas. *Pronto quando:* o relatório mostrar os três indicadores.
8. **Interface web mínima.**

Faça commits pequenos, um por tarefa. Ao terminar cada tarefa, resuma o que foi feito e o que ficou pendente.

**Se encontrar ambiguidade em regra de negócio, pare e pergunte. Não adivinhe.**

---

## 11. Convenções

- Python 3.11 ou superior, com tipagem; `pytest` para testes; `ruff` para estilo.
- Identificadores de código em inglês. Textos exibidos ao usuário em português do Brasil.
- Configuração por variáveis de ambiente. Nenhum segredo no código.
- Cada função pública com teste.

---

## 12. O que NÃO fazer

- Não inventar colunas, métricas, regras de negócio ou respostas esperadas.
- Não escrever SQL livre a partir do LLM na v0.
- Não enviar linhas de dados ao LLM.
- Não usar conhecimento externo para preencher números.
- Não tentar acessar bancos reais, credenciais ou redes corporativas.
- Não adicionar dependências pesadas ou interface sofisticada antes da camada semântica passar nos testes.
- Não inferir grupos econômicos nem agrupar modelos sem o De-Para oficial.

---

## 13. Pontos em aberto (para o dono da base)

1. Definição exata de cada métrica inicial. [PREENCHER]
2. Cortes de segmento por PBT. [PREENCHER]
3. Relação entre `dealer_montadora`, `dealer_emplacamento` e emplacamento. [PREENCHER]
4. Regra para "mês corrente" e "último mês fechado". [PREENCHER]
5. Hierarquia geográfica oficial (município, UF, região). [PREENCHER]
6. Respostas esperadas do conjunto de perguntas de referência. [PREENCHER]
7. Valor de k para a contagem mínima e metas finais de acerto. [PREENCHER]
