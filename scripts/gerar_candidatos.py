#!/usr/bin/env python3
"""Lista rubricas candidatas para revisao HUMANA. Nunca altera escopos.csv."""
import csv
import re
from collections import defaultdict
from pathlib import Path
from atualizar import ROOT,archive_rows,field

PAT=re.compile(r"sa[uú]de digital|tecnologia da informa|informatiza|informatica|sistema.{0,15}informa|interoperabil|rede nacional de dados|processamento de dados|plataforma digital|transforma.{0,9}digital|dados em sa[uú]de", re.I)


def candidates(root=ROOT):
    grouped=defaultdict(set)
    for group,patt,variants in [
      ('orcamento','*_OrcamentoDespesa.zip',['OrcamentoDespesa']),
      ('execucao','*_DespesasExecucao.zip',['DespesasExecucao'])]:
        for p in (root/'cache'/group).glob(patt):
            year=int(p.name[:4])
            for row in archive_rows(p,variants):
                if field(row,'Código Órgão Superior')!='36000':continue
                name=field(row,'Nome Ação')
                po_name=field(row,'Plano Orçamentário')
                sub=field(row,'Nome Órgão Subordinado')
                if not PAT.search(' '.join([name,po_name,sub])):continue
                action=field(row,'Código Ação');po=field(row,'Código Plano Orçamentário')
                grouped[(year,action,po,name,po_name,sub)].add(group)
    path=root/'data/candidatos_escopos.csv'
    path.parent.mkdir(exist_ok=True,parents=True)
    with path.open('w',encoding='utf8',newline='') as f:
        w=csv.writer(f)
        w.writerow(['ano','codigo_acao','codigo_po','nome_acao','nome_po','orgao_subordinado','origens','validar_com_siop'])
        for row in sorted(grouped):w.writerow([*row,','.join(sorted(grouped[row])),'PENDENTE'])
    print(f'{len(grouped)} candidatos: {path}. NAO foram incorporados ao painel automaticamente.')

if __name__=='__main__':candidates()
