#!/usr/bin/env python3
"""CGU/SIDRA -> HTML autoportante; publicacao atomica e fail-closed.

Sem dados orcamentarios validos nao cria atualizacao. Os arquivos ZIP de origem
sao cacheados no host; o HTML contem os dados agregados, CSS, JS e SVG.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import logging
import os
import re
import sys
import tempfile
import unicodedata
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BR_TIME = ZoneInfo("America/Sao_Paulo")
CAMPOS = ("inicial", "atualizado", "empenhado", "liquidado", "pago", "rp_pago", "rp_inscrito", "rp_cancelado")
SRC = {
    "orcamento": "https://portaldatransparencia.gov.br/download-de-dados/orcamento-despesa",
    "execucao": "https://portaldatransparencia.gov.br/download-de-dados/despesas-execucao",
    "populacao": "https://svs.aids.gov.br/daent/acesso-a-informacao/acoes-e-programas/estimativas-populacionais/",
    "ipca": "https://sidra.ibge.gov.br/tabela/1737",
    "siops": "https://portalfns.saude.gov.br/siops/siops-downloads/",
    "siop": "https://www1.siop.planejamento.gov.br/siopdoc/doku.php?id=acesso_publico:dados_abertos",
}


def now():
    return datetime.now(BR_TIME)


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip().replace("\ufeff", "")


def key(s):
    return re.sub(r"[^a-z0-9]", "", norm(s))


def num(value):
    s = str(value or "").strip().replace("R$", "").replace("\u00a0", "").replace(" ", "")
    if not s or s in ("-", "...", "X"): return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        v = float(s)
        if not (-1e17 < v < 1e17): return None
        return v
    except ValueError:
        return None


def normalized_row(row):
    return {key(k): (v or "").strip() for k, v in row.items() if k is not None}


def field(row, *names):
    for name in names:
        n = key(name)
        if n in row and row[n] != "": return row[n]
    return ""


def as_year(raw):
    m = re.search(r"(?:19|20)\d{2}", str(raw))
    return int(m.group()) if m else None


def archive_rows(path: Path, expected: list[str]):
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".csv") and not n.startswith("__MACOSX/")]
        if not names: raise ValueError(f"ZIP sem CSV: {path}")
        # Preferencia de nome documentada pela CGU; se so 1 CSV, admite-se.
        candidates = [n for n in names if any(e.lower() in n.lower() for e in expected)]
        if not candidates and len(names) != 1:
            raise ValueError(f"CSV inesperado no ZIP {path}: {names[:5]}")
        item = (candidates or names)[0]
        with z.open(item) as binary:
            sample = binary.read(8192)
            charset = "utf-8-sig"
            try: sample.decode(charset)
            except UnicodeError: charset = "latin-1"
        with z.open(item) as binary:
            stream = io.TextIOWrapper(binary, encoding=charset, errors="strict", newline="")
            reader = csv.DictReader(stream, delimiter=";")
            if not reader.fieldnames or len(reader.fieldnames) < 3:
                raise ValueError(f"Cabecalho do CSV invalido: {path}")
            names_norm = [key(x) for x in reader.fieldnames]
            if "codigoorgaosuperior" not in names_norm or "codigoacao" not in names_norm:
                raise ValueError(f"Schema CGU incompatível: {path}; cabecalho={reader.fieldnames[:7]}")
            for raw in reader:
                if None in raw: raise ValueError(f"CSV com colunas excedentes: {path}")
                yield normalized_row(raw)


def safe_save_bytes(dest: Path, content: bytes):
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".download-", suffix=".partial", dir=dest.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, dest)
    finally:
        if os.path.exists(name): os.unlink(name)


def verify_zip(raw: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            return any(n.lower().endswith(".csv") for n in z.namelist()) and z.testzip() is None
    except (zipfile.BadZipFile, OSError):
        return False


def download_file(url: str, target: Path, *, optional=False):
    import requests
    try:
        r = requests.get(url, timeout=(15, 120), headers={"User-Agent": "LabX-indicadores-recursos/0.1 (dados abertos)"})
        if r.status_code == 404 and optional:
            logging.info("Ainda nao disponivel (404): %s", url)
            return False
        r.raise_for_status()
        if len(r.content) < 100 or not verify_zip(r.content):
            raise ValueError(f"Resposta nao corresponde a ZIP CSV valido ({len(r.content)} bytes): {url}")
        safe_save_bytes(target, r.content)
        logging.info("OK %s -> %s (%.1f KB)", url, target, len(r.content) / 1024)
        return True
    except Exception as exc:
        if optional:
            logging.warning("Fonte opcional indisponivel: %s [%s]", url, exc)
            return False
        raise RuntimeError(f"FONTE OBRIGATORIA INDISPONIVEL: {url}: {exc}") from exc


def load_scope_rules(root):
    rules = defaultdict(list)
    p = root / "config" / "escopos.csv"
    with p.open(encoding="utf-8-sig", newline="") as f:
        for line in csv.DictReader(f):
            if not line.get("ano"): continue
            if line.get("status", "").casefold().strip() != "homologado":
                continue
            y = int(line["ano"])
            scope = line["escopo"].strip().lower()
            if scope not in ("seidigi", "ti_ms"):
                raise ValueError(f"Escopo invalido na linha: {line}")
            action = line["codigo_acao"].strip().upper()
            if not action: raise ValueError("Regra homologada sem codigo_acao")
            rules[y].append((action, line["codigo_po"].strip().upper(), scope))
    return rules


def include_scope(row, year, scope, rules, is_budget):
    action = field(row, "Código Ação", "Codigo Acao").upper()
    po = field(row, "Código Plano Orçamentário", "Codigo Plano Orcamentario").upper()
    for acao, plano, destino in rules.get(year, []):
        if destino != scope or acao != action: continue
        if plano and is_budget: continue  # No arquivo de orcamento CGU nao ha PO.
        if plano and plano != po: continue
        return True
    return False


def available_scope(year, scope, rules, is_budget):
    if scope == "ms": return True
    if scope == "seidigi" and year < 2023: return True
    selected = [x for x in rules.get(year, []) if x[2] == scope]
    if not selected: return False
    if is_budget and any(x[1] for x in selected): return False
    return True


def empty_vals():
    return {f: 0.0 for f in CAMPOS}


def read_budget(path, year, cfg, rules):
    grouped = defaultdict(empty_vals)
    count = 0
    for row in archive_rows(path, ["OrcamentoDespesa"]):
        y = as_year(field(row, "Exercício", "Exercicio")) or year
        if y != year: raise ValueError(f"Ano inconsistente no orcamento {path}: {y}")
        if field(row, "Código Órgão Superior") not in cfg["ministerio_saude_codigos"]:
            continue
        count += 1
        v = {
            "inicial": num(field(row, "Orçamento Inicial (R$)", "Orcamento Inicial")),
            "atualizado": num(field(row, "Orçamento Atualizado (R$)", "Orcamento Atualizado")),
            "empenhado": num(field(row, "Orçamento Empenhado (R$)", "Orcamento Empenhado")),
            "pago": num(field(row, "Orçamento Realizado (R$)", "Orcamento Realizado")),
        }
        if v["inicial"] is None or v["atualizado"] is None:
            raise ValueError(f"Valores obrigatorios ausentes em {path}")
        for scope in ("ms", "ti_ms", "seidigi"):
            if scope != "ms" and not include_scope(row, year, scope, rules, is_budget=True):
                continue
            a = grouped[scope]
            for k, amount in v.items():
                if amount is not None: a[k] += amount
    if count == 0: raise ValueError(f"Nenhuma linha MS no orcamento de {year}. Verifique codigo do orgao.")
    if grouped["ms"]["atualizado"] <= 0:
        raise ValueError(f"Orcamento do MS inesperadamente nao positivo em {year}")
    return grouped, count


def read_monthly(path, year, month, cfg, rules):
    grouped = defaultdict(empty_vals)
    count = 0
    for row in archive_rows(path, ["DespesasExecucao", "Despesas_Execucao"]):
        raw_date = field(row, "Ano e mês do lançamento", "Ano e mes do lancamento")
        digits = re.sub(r"\D", "", raw_date)
        if len(digits) == 6 and digits[:4] == str(year) and digits[4:] == f"{month:02d}": pass
        elif len(digits) == 6 and digits[-4:] == str(year) and digits[:2] == f"{month:02d}": pass
        else: raise ValueError(f"Data mensal inesperada {raw_date!r} em {path}")
        if field(row, "Código Órgão Superior") not in cfg["ministerio_saude_codigos"]:
            continue
        count += 1
        v = {
            "empenhado": num(field(row, "Valor Empenhado (R$)")),
            "liquidado": num(field(row, "Valor Liquidado (R$)")),
            "pago": num(field(row, "Valor Pago (R$)")),
            "rp_pago": num(field(row, "Valor Restos a Pagar Pagos (R$)")),
            "rp_inscrito": num(field(row, "Valor Restos a Pagar Inscritos (R$)")),
            "rp_cancelado": num(field(row, "Valor Restos a Pagar Cancelado (R$)")),
        }
        if all(v[x] is None for x in ("empenhado", "liquidado", "pago")):
            raise ValueError(f"Sem colunas de execucao identificadas: {path}")
        for scope in ("ms", "ti_ms", "seidigi"):
            if scope != "ms" and not include_scope(row, year, scope, rules, is_budget=False):
                continue
            acc = grouped[scope]
            for k, amt in v.items():
                if amt is not None: acc[k] += amt
    if count == 0: raise ValueError(f"Nenhuma linha MS em {path}")
    return grouped, count


def load_population(root):
    result = {}
    with (root / "data/populacao_ripsa_2000_2025.csv").open(encoding="utf8", newline="") as f:
        for row in csv.DictReader(f):
            result[int(row["ano"])] = {"valor": int(row["populacao"]), "fonte": row["fonte"]}
    return result


def load_ipca_csv(root):
    result = {}
    with (root / "data/ipca_inicial_usuario.csv").open(encoding="utf8", newline="") as f:
        for row in csv.DictReader(f):
            value = num(row.get("ipca"))
            period = str(row.get("cmp", ""))
            if len(period) == 6 and value and value > 0: result[period] = value
    return result


def sidra_ipca(root, cfg, offline):
    history = load_ipca_csv(root)
    update_path = root / "cache/ipca_sidra.json"
    if update_path.exists():
        try:
            cached = json.loads(update_path.read_text(encoding="utf8"))
            history.update({str(k): float(v) for k, v in cached.items()})
        except Exception as e: logging.warning("Cache IPCA invalido: %s", e)
    if not offline:
        import requests
        try:
            r = requests.get(cfg["ibge_ipca_sidra"], timeout=(15, 75), headers={"Accept": "application/json", "User-Agent": "LabX-IPCA/0.1"})
            r.raise_for_status()
            rows = r.json()
            latest = {}
            for row in rows:
                p = str(row.get("D1C", ""))
                v = num(row.get("V"))
                if len(p) == 6 and p.isdigit() and v and v > 0: latest[p] = v
            if not latest: raise ValueError("SIDRA retornou serie vazia")
            history.update(latest)
            safe_save_bytes(update_path, json.dumps(history, sort_keys=True).encode("utf8"))
            logging.info("IPCA SIDRA atualizado: ate %s", max(history))
        except Exception as e:
            logging.warning("IPCA SIDRA sem acesso; contingencia local: %s", e)
    return dict(sorted(history.items()))


def build_data(root, args):
    cfg = json.loads((root / "config/fontes.json").read_text(encoding="utf8"))
    rules = load_scope_rules(root)
    cache = root / "cache"
    current = now()
    limit_year = current.year
    limit_month = current.month
    cache.mkdir(exist_ok=True)
    if not args.offline:
        if args.backfill:
            years = range(args.from_year, limit_year + 1)
        else:
            years = (limit_year,)
        for y in years:
            url = cfg["orcamento_template"].format(base=cfg["cgu_base"], year=y)
            target = cache / f"orcamento/{y}_OrcamentoDespesa.zip"
            if not target.exists() or y == limit_year or args.refresh_all:
                download_file(url, target)
        if args.backfill_exec:
            exec_start = args.from_year
            exec_years = range(exec_start, limit_year + 1)
        else:
            exec_years = (limit_year,)
        for y in exec_years:
            for m in range(1, (limit_month if y == limit_year else 12) + 1):
                target = cache / f"execucao/{y}{m:02d}_DespesasExecucao.zip"
                if target.exists() and (y < limit_year or m < limit_month - 1) and not args.refresh_all:
                    continue
                url = cfg["execucao_template"].format(base=cfg["cgu_base"], year=y, month=m)
                # Ausencia do mes ainda nao publicado e permitida; meses passados no corrente, nao.
                optional = y == limit_year and m == limit_month
                download_file(url, target, optional=optional)
    budget_files = [] if args.empty else sorted((cache / "orcamento").glob("*_OrcamentoDespesa.zip"))
    if not budget_files and not args.empty:
        raise RuntimeError("Nenhum ZIP de orcamento oficial disponivel. Execute --backfill ou copie arquivos para cache/orcamento/.")
    if not args.empty and not any(int(p.name[:4]) == limit_year for p in budget_files):
        # A excecao e o modo offline para backfills/testes.
        if not args.offline:
            raise RuntimeError(f"Orcamento corrente {limit_year} ausente; preservada ultima publicacao")
    years = {}
    provenance = []
    for budget_file in budget_files:
        y = int(budget_file.name[:4])
        if y > limit_year: continue
        a, n = read_budget(budget_file, y, cfg, rules)
        years[y] = {s: {k: None for k in CAMPOS} for s in ("ms", "ti_ms", "seidigi")}
        for scope in years[y]:
            if available_scope(y, scope, rules, is_budget=True):
                for k in ("inicial", "atualizado"):
                    years[y][scope][k] = a.get(scope, empty_vals())[k]
        for scope in years[y]:
            # Reserva, apenas se nao houver execucao mensal completa, explicitada no status.
            years[y][scope]["_reserva_empenhado"] = a.get(scope, empty_vals())["empenhado"] if available_scope(y, scope, rules, True) else None
            years[y][scope]["_reserva_pago"] = a.get(scope, empty_vals())["pago"] if available_scope(y, scope, rules, True) else None
            years[y][scope]["_status"] = "orcamento_sem_execucao"
        provenance.append({"tipo":"orcamento", "ref":str(y), "sha256":sha256(budget_file), "linhas_ms":n})
    monthly = defaultdict(dict)
    for p in sorted((cache / "execucao").glob("*_DespesasExecucao.zip")):
        try: y, m = int(p.name[:4]), int(p.name[4:6])
        except ValueError: continue
        if y not in years or not 1 <= m <= 12: continue
        row, n = read_monthly(p, y, m, cfg, rules)
        monthly[y][m] = row
        provenance.append({"tipo":"execucao", "ref":f"{y}-{m:02d}", "sha256":sha256(p), "linhas_ms":n})
    for y, scopes in years.items():
        months = monthly.get(y, {})
        cut = (max(months) if months else 0)
        complete = cut > 0 and set(range(1,cut+1)).issubset(months.keys()) and (y == limit_year or cut == 12)
        for scope, record in scopes.items():
            known = available_scope(y, scope, rules, False)
            if scope == "seidigi" and y < 2023:
                for k in CAMPOS: record[k] = 0.0
                record["_status"] = "zero_estrutural"
            elif complete and known:
                for k in ("empenhado", "liquidado", "pago", "rp_pago", "rp_inscrito", "rp_cancelado"):
                    record[k] = sum(months[m].get(scope, empty_vals())[k] for m in range(1,cut+1))
                record["_status"] = "execucao_mensal"
            else:
                record["empenhado"] = record.pop("_reserva_empenhado")
                record["pago"] = record.pop("_reserva_pago")
                if not known and scope != "ms": record["_status"] = "sem_homologacao"
                else: record["_status"] = "reserva_orcamento_anual" if record["pago"] is not None else "indisponivel"
            record.pop("_reserva_empenhado", None)
            record.pop("_reserva_pago", None)
        scopes["_meses_execucao"] = sorted(months)
        scopes["_mes_referencia"] = cut if complete else None
        scopes["_execucao_completa"] = complete
    population = load_population(root)
    indices = sidra_ipca(root, cfg, args.offline)
    if not indices: raise RuntimeError("Serie IPCA indisponivel")
    current_ref = max(indices)
    ref_val = indices[current_ref]
    ipca_annual = {}
    for yr in sorted(years):
        values = [value for period, value in indices.items() if period[:4] == str(yr)]
        ipca_annual[yr] = sum(values) / len(values) if values else None
    return {
        "title": "INDI · Recursos da SEIDIGI",
        "updated_at": current.isoformat(timespec="seconds"),
        "budget_years": {str(y): scopes for y, scopes in sorted(years.items())},
        "populacao": {str(y): v for y,v in population.items()},
        "ipca": {"referencia": current_ref, "indice_referencia": ref_val,
                 "ultimo_indice": current_ref, "indices_anuais": {str(y): v for y,v in ipca_annual.items()},
                 "serie_completa_ate": current_ref, "fonte": "IBGE/SIDRA 1737/2266; contingencia: CSV usuario"},
        "sources": SRC,
        "prov": provenance,
        "scope_count": sum(1 for year in rules for x in rules[year] if x[2] == "seidigi"),
        "ti_count": sum(1 for year in rules for x in rules[year] if x[2] == "ti_ms"),
        "empty": not bool(years),
        "warning": "Dados orcamentarios ausentes" if not years else "",
    }


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def render_html(root, payload, brand_css=None, logo_svg=None):
    template = (root / "templates/index.html").read_text(encoding="utf8")
    styles = (root / "templates/style.css").read_text(encoding="utf8")
    extra_css = ""
    if brand_css:
        p = Path(brand_css).expanduser()
        if not p.exists(): raise FileNotFoundError(f"CSS oficial Vidraria nao encontrado: {p}")
        extra_css = "\n/* Vidraria: CSS oficial incorporado */\n" + p.read_text(encoding="utf8")
    js = (root / "templates/app.js").read_text(encoding="utf8")
    svg = "<span class='mark'>LABX<span class='mark-dot'>.</span></span>"
    if logo_svg:
        p = Path(logo_svg).expanduser()
        if not p.exists(): raise FileNotFoundError(f"Logo Vidraria nao encontrado: {p}")
        content = p.read_text(encoding="utf8")
        if not content.lstrip().startswith("<svg") or "<script" in content.lower():
            raise ValueError("Logo precisa ser SVG standalone seguro")
        svg = content
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # Nao permitir encerrar script por caracteres provenientes das fontes.
    data_json = data_json.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return template.replace("__CSS__", styles + "\n" + extra_css).replace("__APPJS__", js).replace("__DATA__", data_json).replace("__BRAND__", svg)


def publish_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".index-", suffix=".html", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if len(text) < 5000 or '<script id="model" type="application/json">' not in text:
            raise ValueError("HTML nao passou verificacao de integridade")
        os.chmod(tmp, 0o644)  # Nginx/Apache precisam ler o HTML final.
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def cli():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--backfill", action="store_true", help="Buscar orcamentos anuais desde --from-year")
    p.add_argument("--backfill-exec", action="store_true", help="Buscar execucoes mensais historicas (grande volume)")
    p.add_argument("--from-year", type=int, default=2013)
    p.add_argument("--refresh-all", action="store_true")
    p.add_argument("--offline", action="store_true", help="Nao acessar rede, processar apenas cache")
    p.add_argument("--empty", action="store_true", help="Gerar somente esqueleto sem dados, para primeira visualizacao")
    p.add_argument("--brand-css", type=Path, help="CSS compilado da Vidraria para incorporar no HTML")
    p.add_argument("--logo-svg", type=Path, help="Logo oficial da Vidraria em SVG")
    p.add_argument("--output", type=Path, help="Caminho do HTML (padrao public/index.html)")
    args = p.parse_args()
    root = args.root.resolve()
    target = args.output or (root / "public" / "index.html")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        payload = build_data(root, args)
        page = render_html(root, payload, args.brand_css, args.logo_svg)
        publish_atomic(target, page)
        logging.info("PUBLICACAO OK %s [%d anos, IPCA %s]", target, len(payload["budget_years"]), payload["ipca"]["referencia"])
        return 0
    except Exception as e:
        logging.exception("FALHA: HTML antigo preservado; %s", e)
        return 1

if __name__ == "__main__":
    sys.exit(cli())
