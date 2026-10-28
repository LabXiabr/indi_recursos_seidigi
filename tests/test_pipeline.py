import csv
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

BUDGET_FIELDS=["Exercício","Código Órgão Superior","Código Ação","Código Unidade Orçamentária","Orçamento Inicial (R$)","Orçamento Atualizado (R$)","Orçamento Empenhado (R$)","Orçamento Realizado (R$)"]
EXEC_FIELDS=["Ano e mês do lançamento","Código Órgão Superior","Código Ação","Código Plano Orçamentário","Valor Empenhado (R$)","Valor Liquidado (R$)","Valor Pago (R$)","Valor Restos a Pagar Pagos (R$)","Valor Restos a Pagar Inscritos (R$)","Valor Restos a Pagar Cancelado (R$)"]


def make_zip(path,headers,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    content=';'.join(headers)+'\n'
    for r in rows:
        content+=';'.join(r)+'\n'
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(path.stem+'.csv',content.encode('latin-1'))


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        for d in ['config','data','templates','public','cache/orcamento','cache/execucao']:(self.root/d).mkdir(parents=True,exist_ok=True)
        for rel in ['config/fontes.json','data/ipca_inicial_usuario.csv','data/populacao_ripsa_2000_2025.csv','templates/index.html','templates/style.css','templates/app.js']:
            shutil.copy(ROOT/rel,self.root/rel)
        with (self.root/'config/escopos.csv').open('w',encoding='utf8',newline='') as f:
            writer=csv.writer(f);writer.writerow(['ano','codigo_acao','codigo_po','escopo','status','justificativa'])
            writer.writerow([2026,'AA01','','seidigi','homologado','TESTE apenas'])
            writer.writerow([2026,'AA01','','ti_ms','homologado','TESTE apenas'])
        make_zip(self.root/'cache/orcamento/2026_OrcamentoDespesa.zip',BUDGET_FIELDS,[
          ['2026','36000','AA01','36001','1.000,00','1.200,00','600,00','400,00'],
          ['2026','36000','BB02','36001','9.000,00','10.000,00','5.000,00','3.000,00'],
          ['2026','37000','AA01','36001','70.000,00','70.000,00','70.000,00','70.000,00']])
        for m in (1,2,3):
            make_zip(self.root/f'cache/execucao/2026{m:02d}_DespesasExecucao.zip',EXEC_FIELDS,[
              [f'2026{m:02d}','36000','AA01','0001','100,00','70,00','50,00','10,00','0,00','0,00'],
              [f'2026{m:02d}','36000','BB02','0001','300,00','200,00','150,00','15,00','0,00','0,00']])
    def tearDown(self):self.tmp.cleanup()
    def run_pipeline(self):
        return subprocess.run([sys.executable,str(ROOT/'scripts/atualizar.py'),'--root',str(self.root),'--offline'],capture_output=True,text=True)
    def test_pipeline_valid_and_model(self):
        result=self.run_pipeline();self.assertEqual(result.returncode,0,result.stderr)
        source=(self.root/'public/index.html').read_text()
        self.assertIn('"inicial":1000.0',source)
        self.assertIn('"atualizado":1200.0',source)
        self.assertIn('"empenhado":300.0',source)
        self.assertIn('"liquidado":210.0',source)
        self.assertIn('"pago":150.0',source)
        self.assertIn('"rp_pago":30.0',source)
        self.assertIn('"atualizado":11200.0',source)
        self.assertIn('"_status":"execucao_mensal"',source)
        self.assertIn('"_execucao_completa":true',source)
        self.assertNotIn('70000.0',source)
    def test_failed_zip_preserves_last_valid_html(self):
        self.assertEqual(self.run_pipeline().returncode,0)
        original=(self.root/'public/index.html').read_bytes()
        (self.root/'cache/orcamento/2026_OrcamentoDespesa.zip').write_bytes(b'html instead of zip')
        result=self.run_pipeline()
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(original,(self.root/'public/index.html').read_bytes())
    def test_missing_month_does_not_invent_zeros(self):
        (self.root/'cache/execucao/202602_DespesasExecucao.zip').unlink()
        self.assertEqual(self.run_pipeline().returncode,0)
        html=(self.root/'public/index.html').read_text()
        self.assertIn('"_execucao_completa":false',html)
        self.assertIn('"liquidado":null',html)
        self.assertIn('"_status":"reserva_orcamento_anual"',html)

if __name__=='__main__':unittest.main()
