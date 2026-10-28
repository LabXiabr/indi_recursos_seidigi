# INDI — Recursos da SEIDIGI

Painel HTML autoportante do ecossistema LabX. Uma única execução Python obtém ZIPs públicos de orçamento e execução da CGU e IPCA/SIDRA, combina a população RIPSA/DATASUS e publica `public/index.html` de maneira **atômica**. Roda semanalmente no Bequer com cron. Não necessita banco de dados nem serviço web de terceiros para exibir o HTML.

## Situação da primeira entrega

- **Implementado:** orçamento inicial/atualizado, empenhado, liquidado, pago, restos a pagar, participação no MS, IPCA, população, análise anual e quadrienal, linha serrilhada nos limites de mandatos federais e fichas FQI 01–06.
- **Obrigatório antes de interpretar a SEIDIGI:** homologar ações/planos em `config/escopos.csv`. A classificação por texto é somente uma lista de candidatos. Não inferir que toda ação de TI está na SEIDIGI.
- **SIOPS:** documentação e fonte previstas; a razão União+Estados+Municípios **ainda não está publicada**, pois precisará deduplicar transferências e definir o denominador financeiro comparável.
- **Identidade:** HTML usa a linguagem tipográfica da Vidraria (Averia Sans Libre + Inter) e tokens básicos de contingência. Passe o CSS compilado oficial para incorporar os tokens verdadeiros. Logos e fontes externas não são exigidos na visualização.
- **HTML inicial:** `public/index.html` contém a interface **sem valores orçamentários**. Não é um painel populado com números fabricados. A primeira coleta no Bequer conectará as fontes.

## 1. Repositório criado manualmente no GitHub

Crie **LabXiabr/indi_recursos_seidigi** vazio (não marque `Add README`/`.gitignore`), com branch inicial `main`. No **Bequer**, use:

```bash
mkdir -p "$HOME/git/LabXiabr"
cd "$HOME/git/LabXiabr"
git clone git@github.com:LabXiabr/indi_recursos_seidigi.git
cd indi_recursos_seidigi
# Descompacte aqui o ZIP disponibilizado junto a esta resposta:
unzip -o "$HOME/Downloads/indi_recursos_seidigi_v0.1.0.zip" -d .
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v

git add .
git commit -m 'feat: implanta INDI Recursos da SEIDIGI v0.1.0'
git branch -M main
git push -u origin main
```

Se sua cópia local da Vidraria estiver em outro diretório, ajuste `VIDRARIA_CSS`. Consulte `scripts/atualizar_publicar.sh` para os caminhos tentados automaticamente.

## 2. Primeira carga dos dados oficiais

```bash
cd "$HOME/git/LabXiabr/indi_recursos_seidigi"
# LOA/orcamento anual historico 2013-2026 + execucao mensal corrente:
./scripts/atualizar_publicar.sh --backfill --from-year 2013
# Opcional (consome mais tempo e espaco): historico completo dos meses 2013-2026:
./scripts/atualizar_publicar.sh --backfill-exec --from-year 2013

# Inspecionar rubricas candidatas: NAO homologadas automaticamente:
.venv/bin/python scripts/gerar_candidatos.py
column -s, -t < data/candidatos_escopos.csv | less -S
```

**Regra fundamental:** por padrão, `--backfill` traz os orçamentos anuais desde 2013, mas só baixa a execução mensal do exercício corrente. Sem a execução mensal completa dos anos passados, o painel apresenta empenho e pago da fonte anual, com rótulo *reserva CGU anual*, e não inventa liquidação/RP históricos. `--backfill-exec` completa as informações (volumoso, executar uma vez).

O CGI do Portal da Transparência disponibiliza os ZIPs de orçamento e execução. Alguns downloads podem sofrer indisponibilidade/limitação. O coletor **falha fechado**, mantém o HTML anterior e escreve o motivo no stderr/logs. Se o padrão de URL da CGU mudar, ajuste `config/fontes.json` somente após consultar a origem.

## 3. Homologação da abrangência de TI e SEIDIGI

O arquivo `config/escopos.csv` tem colunas:

```csv
ano,codigo_acao,codigo_po,escopo,status,justificativa
```

Adicione uma linha para cada ação/PO confirmada **sem inventar códigos**. Use `escopo=seidigi` e/ou `escopo=ti_ms`, `status=homologado` e uma justificativa que cite SIOP, portaria ou documentação institucional. Uma ação pode pertencer aos dois escopos. A cada exercício, revise os códigos.

**Atenção:** o arquivo de orçamento anual da CGU não traz o código do plano orçamentário (PO). Se a seleção de SEIDIGI/TI exigir PO, o orçamento autorizado daquele escopo fica indisponível (não usa indevidamente a dotação da ação inteira); a execução mensal ainda pode ser atribuída por ação + PO.

Até 2022, SEIDIGI aparece como zero estrutural. A partir de 2023, valores dependem de homologação de escopo — ausência de identificação NÃO é zero.

## 4. Agendamento semanal via cron

```bash
mkdir -p "$HOME/git/LabXiabr/indi_recursos_seidigi/logs"
crontab -e
```

Acrescente (exemplo: segunda-feira, 05h20, horário local da máquina):

```cron
20 5 * * 1 /usr/bin/flock -n /tmp/indi_recursos_seidigi.lock /home/ferre/git/LabXiabr/indi_recursos_seidigi/scripts/atualizar_publicar.sh >> /home/ferre/git/LabXiabr/indi_recursos_seidigi/logs/atualizacao.log 2>&1
```

Para também publicar o HTML no GitHub após **sucesso**, acrescente `GIT_PUBLISH=1` ao ambiente do cron, ou use:

```cron
20 5 * * 1 /usr/bin/flock -n /tmp/indi_recursos_seidigi.lock /usr/bin/env GIT_PUBLISH=1 /home/ferre/git/LabXiabr/indi_recursos_seidigi/scripts/atualizar_publicar.sh >> /home/ferre/git/LabXiabr/indi_recursos_seidigi/logs/atualizacao.log 2>&1
```

Para revisar manualmente depois de uma atualização:

```bash
cd "$HOME/git/LabXiabr/indi_recursos_seidigi"
git diff -- public/index.html
git add public/index.html config/escopos.csv
git commit -m "data: atualiza escopos e painel $(date +%F)"
git push origin main
```

Use **apenas um** dos dois modelos de cron. `GIT_PUBLISH=1` exige acesso SSH não interativo ao GitHub, branch `main` e repositório remoto configurado. Caso o push falhe, o HTML local permanece disponível; o publicado pelo GitHub continua sendo o anterior até um push bem-sucedido.

## 5. Hospedagem

- Nginx/Apache local: sirva a pasta `public/`, mantendo `index.html` no local permanente. O arquivo é independente de bibliotecas, fontes ou JS de CDN.
- GitHub Pages (se desejar): configurar publicação pela branch `main` e diretório raiz requer copiar `public/index.html` para raiz ou configurar uma Action; o GitHub Pages **não** oferece opção de servir subdiretório `public/` diretamente no seletor padrão. Em host próprio, a pasta `public/` é suficiente.
- Para obter o CSS oficial: `VIDRARIA_CSS=/caminho/vidraria/.../brand.css VIDRARIA_LOGO=/caminho/logo.svg ./scripts/atualizar_publicar.sh`. O compilador incorpora CSS e SVG no HTML final.

## 6. Garantias e auditoria

1. Cada ZIP é conferido como ZIP válido contendo CSV e publicado no cache de origem atomicamente.
2. Confirma esquema de colunas/órgão da CGU e integridade da série, sem converter lacunas em zeros.
3. Compõe HTML em arquivo temporário, inspeciona integridade e só então usa `os.replace` para substituir `public/index.html`.
4. Falha na fonte ou na construção não modifica o último HTML válido. O HTML contém **data e hora da última publicação bem-sucedida**; não há atualização da data em falhas.
5. `cache/` e `logs/` ficam fora do Git; o HTML final é versionado. Para auditoria, snapshots de fontes podem ser arquivados separadamente.
6. O CSV IPCA fornecido é uma contingência até **maio de 2026**; a atualização automática tenta o SIDRA em cada execução. Se não responder, a data de referência IPCA continua explícita no painel.

## 7. Fontes e FQI

- [CGU — orçamento da despesa](https://portaldatransparencia.gov.br/download-de-dados/orcamento-despesa)
- [CGU — execução mensal](https://portaldatransparencia.gov.br/download-de-dados/despesas-execucao)
- [SIOP — dados abertos](https://www1.siop.planejamento.gov.br/siopdoc/doku.php?id=acesso_publico:dados_abertos)
- [SIOPS — dados abertos](https://portalfns.saude.gov.br/siops/siops-downloads/)
- [IPCA — SIDRA tabela 1737](https://sidra.ibge.gov.br/tabela/1737)
- [População — RIPSA/DATASUS](https://svs.aids.gov.br/daent/acesso-a-informacao/acoes-e-programas/estimativas-populacionais/)

Ficha detalhada dos seis conjuntos em `docs/FQI.md`.
