import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
// Optional report builder: use the Codex bundled Node/runtime. No repository
// npm installation is required. Set ARTIFACT_NODE_MODULES to that runtime's
// node_modules, or use an environment already providing @oai/artifact-tool.
const require=createRequire(process.env.ARTIFACT_NODE_MODULES
  ? path.resolve(process.env.ARTIFACT_NODE_MODULES,'../package.json') : import.meta.url);
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const input=path.resolve(process.argv[2]??path.join(root,'1.Hardware/RevB-KiCad/Naive/BOM.json'));
const out=path.resolve(process.argv[3]??path.join(root,'outputs/hardware-bom'));
const previewDir=path.resolve(process.argv[4]??path.join(out,'previews'));
const data=JSON.parse(await fs.readFile(input,'utf8'));
const groups=new Map();
for(const p of data.parts){
  if(!groups.has(p.mpn))groups.set(p.mpn,{...p,items:[],values:new Set(),notes:new Set()});
  const g=groups.get(p.mpn);g.items.push(p);g.values.add(p.value);if(p.acceptance_note)g.notes.add(p.acceptance_note);
}
const first=['MPU-6050','ESP32-PICO-D4','BH1750FVI-TR','P133H002','CA-C03','104031-0811','USB4105-GF-A','CP2102-GMR'];
const list=[...groups.values()].sort((a,b)=>{
  let aa=first.indexOf(a.mpn),bb=first.indexOf(b.mpn);
  if(aa<0)aa=first.length;if(bb<0)bb=first.length;
  return aa-bb||a.mpn.localeCompare(b.mpn,'en',{numeric:true});
});
const wb=Workbook.create();
const summary=wb.worksheets.add('采购清单');
const detail=wb.worksheets.add('装配明细');
const start=7,last=start+data.parts.length-1,end=start+list.length-1;
for(const s of [summary,detail]){
  s.showGridLines=false;
  s.getRange(`A2:J${last}`).format.font={name:'Arial',size:10,color:'#182330'};
  s.getRange(`A2:J${last}`).format.verticalAlignment='center';
  s.freezePanes.freezeRows(6);s.freezePanes.freezeColumns(s===summary?1:2);
}
summary.tabColor='#27445E';
summary.getRange('A2').values=[['Naive RevB 采购清单']];
summary.getRange('A2').format.font={name:'Arial',size:14,bold:true,color:'#182330'};
summary.getRange('A3').values=[[`${data.date}  每台两块PCB的装配用量`]];
summary.getRange('A4').values=[['元件总数']];summary.getRange('B4').formulas=[[`=SUM('装配明细'!C${start}:C${last})`]];
summary.getRange('D4').values=[['订货型号数']];summary.getRange('E4').values=[[list.length]];
summary.getRange('G3').values=[['不含PCB、FFC、SD卡、USB线、光学件及外壳。']];
summary.getRange('G4').values=[['MPN已明确；供货、装配与实测条件见各行。']];
summary.getRange('A6:G6').values=[['完整订货号 MPN','厂家','数量','元件值','两板位号','供货状态','特殊采购与验收条件']];
summary.getRange(`A${start}:G${end}`).values=list.map(g=>{
  const refs=['MainBoard','ExtendBoard'].map(b=>{
    const rr=g.items.filter(p=>p.board===b).map(p=>p.reference);
    return rr.length?`${b==='MainBoard'?'主板':'屏板'}: ${rr.join(', ')}`:'';
  }).filter(Boolean).join('\n');
  return [g.mpn,g.manufacturer,null,[...g.values].join(' / '),refs,g.supply_status,[...g.notes].join('\n')];
});
summary.getRange(`C${start}:C${end}`).formulas=list.map((_,i)=>[`=SUMIFS('装配明细'!$C$${start}:$C$${last},'装配明细'!$E$${start}:$E$${last},A${start+i})`]);
for(const [col,width]of Object.entries({A:29,B:23,C:8,D:17,E:43,F:30,G:82}))summary.getRange(`${col}2:${col}${end}`).format.columnWidth=width;
summary.getRange(`A${start}:G${end}`).format.rowHeight=54;
summary.getRange(`D${start}:G${end}`).format.wrapText=true;
summary.getRange(`A${start}:B${end}`).setNumberFormat('@');
summary.getRange(`C${start}:C${end}`).setNumberFormat('#,##0');

detail.getRange('A2').values=[['Naive RevB 装配明细']];
detail.getRange('A2').format.font={name:'Arial',size:14,bold:true,color:'#182330'};
detail.getRange('A3').values=[['2026-10-29  每行对应一个实际位号，数量单位：件/台']];
detail.getRange('A4').values=[['来源：两板原生KiCad原理图MPN字段与受控manifest；特殊状态的原厂证据见J列。']];
detail.getRange('A6:J6').values=[['板卡','位号','数量','元件值','完整订货号 MPN','厂家','本地受控封装','供货状态','特殊采购与验收条件','资料来源']];
detail.getRange(`A${start}:J${last}`).values=data.parts.map(p=>[p.board,p.reference,p.quantity,p.value,p.mpn,p.manufacturer,p.footprint,p.supply_status,p.acceptance_note,p.source_url]);
for(const[col,width]of Object.entries({A:16,B:10,C:8,D:18,E:29,F:23,G:45,H:30,I:75,J:82}))detail.getRange(`${col}2:${col}${last}`).format.columnWidth=width;
detail.getRange(`A${start}:J${last}`).format.rowHeight=62;
detail.getRange(`D${start}:J${last}`).format.wrapText=true;
detail.getRange(`E${start}:G${last}`).setNumberFormat('@');
detail.getRange(`C${start}:C${last}`).setNumberFormat('#,##0');
for(const [s,range,status]of [[summary,`A6:G${end}`,`F${start}:F${end}`],[detail,`A6:J${last}`,`H${start}:H${last}`]]){
  const table=s.tables.add(range,true,s===summary?'PurchasingParts':'AssemblyParts');
  table.showFilterButton=true;table.showBandedColumns=false;
  s.getRange(s===summary?'A6:G6':'A6:J6').format={fill:'#27445E',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',verticalAlignment:'center',rowHeight:28};
  s.getRange(status).conditionalFormats.add('containsText',{text:'Obsolete',format:{fill:'#FDE7E6',font:{color:'#A32925',bold:true}}});
  for(const text of ['NRND','待验收'])s.getRange(status).conditionalFormats.add('containsText',{text,format:{fill:'#FFF1D0',font:{color:'#805600',bold:true}}});
}
wb.recalculate();
const metrics=await wb.inspect({kind:'table',range:'采购清单!A4:G14',include:'values,formulas',tableMaxRows:11,tableMaxCols:7});
await fs.mkdir(out,{recursive:true});
await fs.mkdir(previewDir,{recursive:true});
await fs.writeFile(path.join(previewDir,'inspection.ndjson'),metrics.ndjson);
console.log(metrics.ndjson.slice(0,4500));
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},summary:'final error scan'});
console.log(errors.ndjson);
for(const [sheetName,range,file]of [['采购清单','A2:G15','purchasing.png'],['装配明细','A2:H15','assembly.png'],['装配明细','I6:J15','assembly-sources.png']]){
  const png=await wb.render({sheetName,range,scale:1.3,format:'png'});
  await fs.writeFile(path.join(previewDir,file),new Uint8Array(await png.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(out+'/HoloCubic-Naive-RevB-BOM.xlsx');
console.log('Exported 69 instances / 39 MPNs:',out+'/HoloCubic-Naive-RevB-BOM.xlsx');
