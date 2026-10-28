# Fichas de Qualificação dos Indicadores (FQI)

**Escopo**: União (CGU/SIAFI), MS, rubricas TI identificadas e SEIDIGI institucional. Não confundir unidade administrativa com unidade orçamentária.

## FQI-01 — Autorização orçamentária
- Numeradores: orçamento inicial e orçamento atualizado (R$), por ano e escopo.
- Crédito líquido: atualizado − inicial.
- Fonte: CGU `OrcamentoDespesa` (conferência: SIOP/SIGA Brasil).
- Periodicidade: consulta semanal; orçamento é estoque autorizado em data de corte, não soma de snapshots.
- Cautela: ano corrente aberto; revisões durante o exercício. LOA não equivale a empenho.

## FQI-02 — Execução orçamentária
- Empenhado, liquidado e pago das despesas do próprio exercício (R$).
- Indicadores: cada estágio / orçamento atualizado × 100.
- Fonte preferencial: CGU `DespesasExecucao` mensal; reserva alternativa para empenhado e pago no arquivo anual de orçamento, devidamente sinalizada.
- Periodicidade: semanal; datas-base da execução podem divergir das da dotação.
- Cautela: ausência de meses é dado ausente; não é despesa zero. Não somar mês acumulado sem confirmar granularidade.

## FQI-03 — Execução financeira e restos a pagar
- Pagamentos do exercício, restos a pagar pagos e total desembolsado, em R$.
- Desembolso total = pago do exercício + restos a pagar pagos (sem duplicar as naturezas).
- Fonte: execução mensal consolidada da CGU; colunas de RAP pagos, inscritos e cancelados.
- Cautela: pagamentos de exercícios anteriores não devem integrar a taxa de execução da dotação corrente.

## FQI-04 — Participação relativa
- Participação da SEIDIGI no MS = métrica SEIDIGI / mesma métrica MS × 100.
- Comparação histórica de gasto SUS subnacional: SIOPS, somente exercícios encerrados com base consolidada e cobertura especificada.
- Cautela: soma União+UF+Municípios sem expurgo de transferências pode duplicar valores; sem regra validada, não apresentar uma falsa participação consolidada no SUS.

## FQI-05 — TI versus SEIDIGI
- Métrica TI-MS e SEIDIGI, ambas por estágio, nominal e relativas.
- TI-MS: SOMENTE ações identificadas e homologadas por regra explícita no `config/escopos.csv`; falta de homologação vira indisponível, não zero.
- SEIDIGI: mesmas regras de atribuição, com registro da fonte e justificativa da correspondência entre ação/plano orçamentário e secretaria.
- Antes de 2023: zero **estrutural institucional**, não despesa total de saúde digital zero.
- Na fonte anual de orçamento da CGU, não há campo PO. Regras com PO só valem para execução mensal; o orçamento anual do respectivo escopo fica indisponível se exigir PO.
- O percentual TI-MS / SEIDIGI depende do estágio; não é inferido por busca textual casual.

## FQI-06 — Ajustes reais, populacionais e mandatos
- Deflator: IPCA nacional número-índice, tabela 1737, variável 2266, SIDRA/IBGE; arquivo local anexado como contingência.
- Método anual: comparação a preços da última competência disponível, usando média dos índices mensais do exercício com dados disponíveis; aproximação para totais orçamentários anuais, não deflação operação a operação.
- População: série RIPSA/DATASUS 2000–2025 cedida para este projeto, não equivalente automaticamente à série SIDRA.
- Per capita = valor em R$ / população nacional correspondente; anos sem denominador permanecem NA.
- Mandatos: 2003–2006, 2007–2010, ..., 2027–2030; linhas serrilhadas no início de cada mandato a partir de 2007, visíveis quando há dados nos dois lados. Períodos incompletos marcados como parciais.
- Quatro anos: soma dos fluxos monetários anuais; razão sobre somas da mesma métrica; não somar porcentagens. Não somar o total autorizado como se fosse desembolso num ano.
