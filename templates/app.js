'use strict';
(() => {
const model=JSON.parse(document.getElementById('model').textContent);
const $$=id=>document.getElementById(id);
const C={scope:$$('scope'),metric:$$('metric'),group:$$('group'),year:$$('year'),real:$$('real'),percap:$$('percap'),comparison:$$('comparison')};
const br=new Intl.NumberFormat('pt-BR',{maximumFractionDigits:2});
const sortedYears=Object.keys(model.budget_years).map(Number).sort((a,b)=>a-b);
const labelScope={ms:'Ministério da Saúde',seidigi:'SEIDIGI',ti_ms:'TI no Ministério da Saúde'};
const labelMetric={inicial:'Orçamento inicial',atualizado:'Orçamento atualizado',empenhado:'Empenhado',liquidado:'Liquidado',pago:'Pago (exercício)',rp_pago:'RP pagos',desembolso:'Desembolso total',execucao:'Pago / dotação (%)',share_ms:'Participação no MS: pago (%)',share_ti:'TI-MS / SEIDIGI: pago (%)',share_ms_atualizado:'Participação no MS: dotação (%)',share_ms_empenhado:'Participação no MS: empenhado (%)',share_ms_liquidado:'Participação no MS: liquidado (%)',share_ms_pago:'Participação no MS: pago (%)',share_ms_desembolso:'Participação no MS: desembolso (%)',share_ti_atualizado:'TI-MS / SEIDIGI: dotação (%)',share_ti_pago:'TI-MS / SEIDIGI: pago (%)'};
function finite(x){return typeof x==='number' && Number.isFinite(x)}
function fmt(v,unit='money',short=false){if(!finite(v))return '—';if(unit==='percent')return br.format(v)+'%';if(unit==='percap')return 'R$ '+br.format(v);if(short){const x=Math.abs(v);if(x>=1e12)return 'R$ '+br.format(v/1e12)+' tri';if(x>=1e9)return 'R$ '+br.format(v/1e9)+' bi';if(x>=1e6)return 'R$ '+br.format(v/1e6)+' mi';}return 'R$ '+new Intl.NumberFormat('pt-BR',{minimumFractionDigits:0,maximumFractionDigits:2}).format(v)}
function value(y,scope,metric){const r=model.budget_years[String(y)]?.[scope];if(!r)return null;
  if(metric==='desembolso')return finite(r.pago)&&finite(r.rp_pago)?r.pago+r.rp_pago:null;
  if(metric==='execucao')return finite(r.pago)&&finite(r.atualizado)&&r.atualizado>0?100*r.pago/r.atualizado:null;
  if(metric.startsWith('share_ms')){const stage=metric.startsWith('share_ms_')?metric.slice(9):'pago';const numerator=value(y,scope,stage),denominator=value(y,'ms',stage);return finite(numerator)&&finite(denominator)&&denominator>0?100*numerator/denominator:null;}
  if(metric.startsWith('share_ti')){const stage=metric.startsWith('share_ti_')?metric.slice(9):'pago';const ti=value(y,'ti_ms',stage),se=value(y,'seidigi',stage);return finite(ti)&&finite(se)&&se>0?100*ti/se:null;}
  return finite(r[metric])?r[metric]:null;
}
function isPercentage(metric){return metric==='execucao'||metric.startsWith('share_ms')||metric.startsWith('share_ti')}
function converted(raw,year,metric){if(!finite(raw))return null;if(isPercentage(metric))return raw;let v=raw;
if(C.real.checked){const avg=model.ipca.indices_anuais[String(year)];if(!finite(avg)||avg<=0)return null;v*=model.ipca.indice_referencia/avg;}
if(C.percap.checked){const population=model.populacao[String(year)]?.valor;if(!finite(population)||population<=0)return null;v/=population;}
return v;}
function annual(year,scope,metric){return converted(value(year,scope,metric),year,metric)}
function termStart(y){return y>=2003?2003+4*Math.floor((y-2003)/4):1999+4*Math.floor((y-1999)/4)}
function periodLabel(y){const first=termStart(y);return first+'–'+(first+3)}
function aggregate(years,scope,metric){if(!years.length)return null;
 const data=years.map(y=>annual(y,scope,metric));if(data.some(x=>x===null))return null;
 // Porcentagens e participacoes precisam ser calculadas como razao das somas originais.
 if(isPercentage(metric)){
  let numerator=0,denominator=0;
  for(const y of years){let n,d;if(metric==='execucao'){n=value(y,scope,'pago');d=value(y,scope,'atualizado');}
   else if(metric.startsWith('share_ms')){const stage=metric.startsWith('share_ms_')?metric.slice(9):'pago';n=value(y,scope,stage);d=value(y,'ms',stage);}
   else{const stage=metric.startsWith('share_ti_')?metric.slice(9):'pago';n=value(y,'ti_ms',stage);d=value(y,'seidigi',stage);}
   if(!finite(n)||!finite(d))return null;numerator+=n;denominator+=d;}
  return denominator>0?100*numerator/denominator:null;
 }
 // Valores deflacionados = soma das parcelas anuais ja convertidas.
 return data.reduce((a,b)=>a+b,0);
}
function points(scope,metric){if(C.group.value==='ano')return sortedYears.map(y=>({x:String(y),start:y,years:[y],value:annual(y,scope,metric),quality:quality(y,scope),partial:y===new Date().getFullYear()}));
 const periods=[...new Set(sortedYears.map(periodLabel))];return periods.map(p=>{let y0=Number(p.slice(0,4)),ys=sortedYears.filter(y=>termStart(y)===y0);return {x:p,start:y0,years:ys,value:aggregate(ys,scope,metric),quality:ys.map(y=>quality(y,scope)).filter(Boolean).join('; '),partial:ys.length<4||ys.includes(new Date().getFullYear())};});
}
function quality(y,scope){const s=model.budget_years[String(y)]?.[scope]?._status;
 return ({zero_estrutural:'Zero estrutural',execucao_mensal:'CGU mensal',reserva_orcamento_anual:'CGU anual (reserva)',sem_homologacao:'Rubrica não homologada',orcamento_sem_execucao:'Sem execução mensal',indisponivel:'Indisponível'})[s]||'Fonte parcial';}
function svgEscape(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function metricUnit(){return isPercentage(C.metric.value)?'percent':C.percap.checked?'percap':'money'}
function draw(){let p=points(C.scope.value,C.metric.value),p2=C.comparison.checked&&C.scope.value!=='ms'&&!isPercentage(C.metric.value)?points('ms',C.metric.value):[];
 if(!p.length||[...p,...p2].every(x=>x.value===null)){
  $$('chart').innerHTML='<div class="error-empty"><strong>Sem valores homologados disponíveis</strong>Verifique a importação dos dados oficiais e o cadastro de escopos.</div>';return;
 }
 const width=1100,height=310,left=79,right=30,top=25,bottom=55,inner=width-left-right,chartHeight=height-top-bottom;
 const x=i=>left+(p.length===1?inner/2:inner*i/(p.length-1));
 const vals=[...p,...p2].map(o=>o.value).filter(finite);
 const min=Math.min(0,...vals),max=Math.max(...vals);const hi=max===min?max+1:max*1.085;
 const y=v=>top+(hi-v)/(hi-min)*chartHeight;
 const unit=metricUnit();
 const shortLabel=n=>!finite(n)?'—':unit==='percent'?br.format(n)+'%':unit==='percap'?'R$ '+br.format(n):n>=1e12?br.format(n/1e12)+' tri':n>=1e9?br.format(n/1e9)+' bi':n>=1e6?br.format(n/1e6)+' mi':br.format(n);
 let svg=`<svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" aria-labelledby="plot-title"><title id="plot-title">Série histórica ${svgEscape(labelMetric[C.metric.value])} — ${svgEscape(labelScope[C.scope.value])}</title>`;
 for(let k=0;k<=4;k++){let v=min+(hi-min)*k/4,yy=y(v);svg+=`<line x1="${left}" x2="${width-right}" y1="${yy}" y2="${yy}" stroke="#dce6ed" stroke-dasharray="3 5"/><text x="${left-13}" y="${yy+3}" text-anchor="end">${svgEscape(shortLabel(v))}</text>`;}
 if(C.group.value==='ano'&&p.length>1){for(let i=1;i<p.length;i++){const st=p[i].start;if(st>=2007&&((st-2003)%4)===0){const xx=(x(i)+x(i-1))/2;let coords=[];for(let z=top;z<=height-bottom;z+=8)coords.push(`${xx+(Math.floor((z-top)/8)%2?3:-3)},${z}`);svg+=`<polyline points="${coords.join(' ')}" fill="none" stroke="#ad7d55" stroke-width="1.5" opacity=".7"/><text x="${xx+6}" y="${top+13}" fill="#a06e43" font-size="10">${st}</text>`;}}}
 if(C.group.value==='mandato'){for(let i=1;i<p.length;i++){let xx=(x(i)+x(i-1))/2;svg+=`<line x1="${xx}" x2="${xx}" y1="${top}" y2="${height-bottom}" stroke="#d1a780" stroke-dasharray="2 5"/>`;}}
 const lines=[{pts:p,color:'#337ab7',stroke:3.3},{pts:p2,color:'#c58b57',stroke:2.3}];
 for(const l of lines){if(!l.pts.length)continue;let segment=[];function flush(){if(segment.length>1){svg+=`<polyline points="${segment.join(' ')}" stroke="${l.color}" stroke-width="${l.stroke}" fill="none" stroke-linejoin="round" stroke-linecap="round"/>`;}segment=[];}
  l.pts.forEach((o,i)=>{if(!finite(o.value)){flush();return;}const xx=x(i),yy=y(o.value);segment.push(`${xx},${yy}`)});flush();
  l.pts.forEach((o,i)=>{if(!finite(o.value))return;svg+=`<circle cx="${x(i)}" cy="${y(o.value)}" r="3.5" fill="#fff" stroke="${l.color}" stroke-width="2"><title>${svgEscape(o.x)} · ${svgEscape(fmt(o.value,unit,true))}${o.partial?' · período parcial':''}</title></circle>`;});
 }
 const interval=p.length>17?2:1;
 p.forEach((o,i)=>{if(i%interval===0||i===p.length-1)svg+=`<text x="${x(i)}" y="${height-25}" text-anchor="middle" class="axis-label">${svgEscape(o.x)}</text>`;});
 svg+='</svg>';$$('chart').innerHTML=svg;
}
function formatKpi(id,v,unit){$$(id).textContent=fmt(v,unit,true);$$(id).title=fmt(v,unit)}
function yearsForKpi(year){return C.group.value==='mandato'?sortedYears.filter(y=>termStart(y)===termStart(year)):[year]}
function kpi(){const y=Number(C.year.value),scope=C.scope.value,m=C.metric.value,ys=yearsForKpi(y);const single=ys.length===1;
 const collect=(s,met)=>single?annual(ys[0],s,met):aggregate(ys,s,met);
 $$('kpi1-label').textContent=labelMetric[m];formatKpi('kpi1',collect(scope,m),metricUnit());$$('kpi1-sub').textContent=C.group.value==='mandato'?periodLabel(y):String(y);
 formatKpi('kpi2',collect(scope,'execucao'),'percent');
 $$('kpi3-label').textContent=scope==='ms'?'Participação do MS no próprio MS':'Participação no MS (pagamentos)';
 formatKpi('kpi3',collect(scope,'share_ms'),'percent');
 $$('kpi3-sub').textContent='Pago do escopo / pago do MS';
 formatKpi('kpi4',collect(scope,'rp_pago'),C.percap.checked?'percap':'money');
}
function table(){const p=points(C.scope.value,C.metric.value),tr=[];for(const row of p){const ys=row.years;const func=metric=>ys.length===1?annual(ys[0],C.scope.value,metric):aggregate(ys,C.scope.value,metric);const v=func(C.metric.value),unit=metricUnit();let qual=row.quality;
 if(row.partial)qual+=' · período parcial';
 const isZero=ys.every(y=>quality(y,C.scope.value)==='Zero estrutural');
 tr.push(`<tr><td>${svgEscape(row.x)}${row.partial?' *':''}</td><td class="${isZero?'zero':!finite(v)?'missing':''}">${svgEscape(fmt(v,unit))}${isZero?' (estrutural)':''}</td><td>${svgEscape(fmt(func('empenhado'),C.percap.checked?'percap':'money'))}</td><td>${svgEscape(fmt(func('liquidado'),C.percap.checked?'percap':'money'))}</td><td>${svgEscape(fmt(func('pago'),C.percap.checked?'percap':'money'))}</td><td>${svgEscape(fmt(func('execucao'),'percent'))}</td><td class="quality">${svgEscape(qual)}</td></tr>`);
 }
 $$('table-body').innerHTML=tr.join('')||'<tr><td colspan="7">Dados orçamentários ainda não importados.</td></tr>';
 $$('table-value-title').textContent=labelMetric[C.metric.value]+(C.percap.checked?' (R$/hab.)':'');
 $$('chart-range').textContent=p.length?`${p[0].x} a ${p[p.length-1].x} · séries anuais em R$${C.real.checked?' corrigidos pelo IPCA':''}${C.percap.checked?'/habitante':''}`:'Sem série';
}
function showNotes(){const pct=isPercentage(C.metric.value);
 C.real.disabled=pct;C.percap.disabled=pct;if(pct){C.real.checked=false;C.percap.checked=false;}
 C.comparison.disabled=pct||C.scope.value==='ms';if(C.comparison.disabled)C.comparison.checked=false;
 let notes=[];
 if(C.real.checked)notes.push(`Valores a preços de ${model.ipca.referencia.slice(4,6)}/${model.ipca.referencia.slice(0,4)}; deflator pela média anual dos índices mensais conhecidos.`);
 if(C.percap.checked)notes.push('Sem estimativa RIPSA de 2026: valores desse exercício em R$/hab. permanecem indisponíveis.');
 if(pct)notes.push('Razão entre valores brutos do mesmo estágio. IPCA e população não se aplicam a percentuais.');
 if(C.group.value==='mandato')notes.push('Mandatos incompletos sinalizados; porcentagens recalculadas sobre as somas.');
 if(C.scope.value!=='ms'&&((C.scope.value==='seidigi'&&model.scope_count===0)||(C.scope.value==='ti_ms'&&model.ti_count===0)))notes.push('Nenhuma rubrica homologada para este escopo; desde 2023, ausência de dado não significa zero.');
 $$('mode-note').textContent=notes.join(' ');
 $$('legend-main').textContent=labelScope[C.scope.value];$$('legend-ms').style.display=C.comparison.checked?'flex':'none';
 $$('chart-subtitle').textContent=C.group.value==='ano'?'Série anual com limites serrilhados no início dos mandatos federais.':'Somas de quatro exercícios por mandato federal; períodos incompletos são identificados.';
}
function update(){showNotes();kpi();draw();table()}
function initialize(){const timestamp=(model.updated_at||'').replace('T',' · ');
 $$('meta-update').textContent='Última publicação válida: '+(timestamp||'—');$$('footer-update').textContent='Última publicação válida: '+(timestamp||'—');
 $$('meta-coverage').textContent='Dados fiscais: '+(sortedYears.length?`${sortedYears[0]}–${sortedYears[sortedYears.length-1]}`:'não publicados');
 $$('meta-ipca').textContent='IPCA: '+(model.ipca.referencia||'—');
 const yearLatest=sortedYears.length?sortedYears[sortedYears.length-1]:null;const monthCut=yearLatest?model.budget_years[String(yearLatest)]?._mes_referencia:null;
 $$('meta-exec').textContent=monthCut?`Execução mensal até ${String(monthCut).padStart(2,'0')}/${yearLatest}`:'Execução mensal: cobertura não confirmada';
 C.year.innerHTML=sortedYears.length?sortedYears.map(y=>`<option value="${y}">${y}</option>`).join(''):'<option value="0">Sem dados</option>';if(sortedYears.length)C.year.value=String(sortedYears[sortedYears.length-1]);
 let warnings=[];
 if(model.empty)warnings.push('Nenhum dado fiscal foi publicado. Execute a coleta oficial antes de disponibilizar o painel ao público.');
 if(model.scope_count===0)warnings.push('SEIDIGI: classificação de rubricas não homologada; indicadores de 2023 em diante ficam indisponíveis.');
 if(model.ti_count===0)warnings.push('TI/MS: classificação de rubricas ainda não homologada.');
 if(model.ipca.referencia){const ref=Number(model.ipca.referencia.slice(0,4))*12+Number(model.ipca.referencia.slice(4,6));const atual=new Date().getFullYear()*12+(new Date().getMonth()+1);if(atual-ref>2)warnings.push('IPCA com defasagem superior a 2 meses: deflação limitada à competência mostrada.');}
 if(warnings.length){$$('data-warning').hidden=false;$$('data-warning').textContent=warnings.join(' ');}
 let links=Object.entries(model.sources).map(([id,url])=>`<a href="${svgEscape(url)}" target="_blank" rel="noopener noreferrer">${svgEscape(({orcamento:'Orçamento CGU',execucao:'Execução CGU',populacao:'RIPSA/DATASUS',ipca:'IPCA/SIDRA',siops:'SIOPS',siop:'SIOP'})[id]||id)} ↗</a>`).join('');$$('source-links').innerHTML=links;
 $$('source-detail').textContent=`Arquivos de origem verificados: ${(model.prov||[]).length}. Hash SHA-256 auditável no projeto. Dados RIPSA: 2000–2025. IPCA: ${model.ipca.referencia}. Nenhuma transmissão de informações ao abrir o HTML.`;
 Object.values(C).forEach(el=>el.addEventListener('change',update));
 $$('export').addEventListener('click',()=>{const rows=[['periodo','escopo','indicador','valor','unidade','qualidade']];for(const p of points(C.scope.value,C.metric.value)){rows.push([p.x,C.scope.value,C.metric.value,finite(p.value)?String(p.value):'',metricUnit(),p.quality+(p.partial?';parcial':'')]);}const csv=rows.map(r=>r.map(x=>'"'+String(x).replace(/"/g,'""')+'"').join(';')).join('\n');const blob=new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob);let a=document.createElement('a');a.href=url;a.download='indi_recursos_seidigi.csv';document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);});
 update();}
initialize();
})();
