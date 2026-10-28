// Author with @oai/artifact-tool. Run from a directory where that package resolves.
// Arguments: input JSON, absolute output directory. Pure-Python pipeline is independent.
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [input, outputDir] = process.argv.slice(2);
if (!input || !outputDir) throw new Error('Usage: node build_excel.mjs INPUT_JSON OUTPUT_DIR');
const data = JSON.parse(await fs.readFile(input, 'utf8'));
const wb = Workbook.create();
const summary = wb.worksheets.add('Review');
const campaigns = wb.worksheets.add('Campaigns');
const advertisers = wb.worksheets.add('Advertisers');
const n = data.campaigns.length + 5, na = data.advertisers.length + 4;
for (const sheet of [summary, campaigns, advertisers]) {
  sheet.showGridLines = false;
  sheet.getRange('A1:J110').format.font = {name:'Arial',size:10,color:'#17243B'};
  sheet.getRange('A1:J110').format.columnWidth = 15;
  sheet.getRange('A1:J110').format.rowHeight = 21;
}
function header(sheet, range) {
  sheet.getRange(range).format = {fill:'#243B55',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:25};
}
summary.getRange('A2').values = [['Advertising campaign review']];
summary.getRange('A2').format.font = {size:15,bold:true};
summary.getRange('A3').values = [['Synthetic data. Oct–Dec 2025. UTC. Click attribution: 24 hours.']];
summary.getRange('A5:B5').values = [['Advertiser ID', 1]];
summary.getRange('B5').format.fill = '#FFF2CC';
summary.getRange('B5').dataValidation={rule:{type:'list',formula1:`Advertisers!$A$5:$A$${na}`}};
summary.getRange('B6').formulas=[[`=IFNA(VLOOKUP(B5,Advertisers!$A$5:$B$${na},2,FALSE),"Missing advertiser")`]];
summary.getRange('A7:D7').values = [['Impressions','Clicks','CTR','Campaigns with no clicks']];
header(summary,'A7:D7');
summary.getRange('A8:D8').formulas = [[
  `=SUMIFS(Campaigns!$D$6:$D$${n},Campaigns!$A$6:$A$${n},$B$5)`,
  `=SUMIFS(Campaigns!$E$6:$E$${n},Campaigns!$A$6:$A$${n},$B$5)`,
  '=IF(A8=0,"n.a.",B8/A8)',
  `=COUNTIFS(Campaigns!$A$6:$A$${n},$B$5,Campaigns!$E$6:$E$${n},0)`]];
summary.getRange('C8').setNumberFormat('0.00%');
summary.getRange('A8:B8').setNumberFormat('#,##0');
summary.getRange('D7:D7').format.columnWidth = 28;
summary.getRange('F5').values = [['Change the yellow advertiser ID to review another account.']];
summary.getRange('F7').values = [['No clicks is a review flag, not proof of wasted spend.']];
summary.getRange('F9').values = [['Apply campaign objectives and sample-size checks before acting.']];
summary.getRange('A11:E11').values = [['Advertiser ID','Advertiser','Impressions','Clicks','CTR']];
header(summary,'A11:E11');
data.advertisers.forEach((a,i) => {
  const row = i + 12;
  summary.getRange(`A${row}:B${row}`).values = [[a.advertiser_id,a.advertiser_name]];
  summary.getRange(`C${row}:E${row}`).formulas = [[
    `=SUMIFS(Campaigns!$D$6:$D$${n},Campaigns!$A$6:$A$${n},A${row})`,
    `=SUMIFS(Campaigns!$E$6:$E$${n},Campaigns!$A$6:$A$${n},A${row})`,
    `=IF(C${row}=0,"n.a.",D${row}/C${row})`]];
});
summary.getRange(`E12:E${data.advertisers.length+11}`).setNumberFormat('0.00%');
summary.getRange('B:B').format.columnWidth=34;
summary.getRange('A:A').format.columnWidth=17;
summary.getRange('C:C').format.columnWidth=17;
campaigns.getRange('A2').values = [['Campaign observations and investigation']];
campaigns.getRange('A2').format.font = {size:15,bold:true};
campaigns.getRange('A3').values = [['Source: generated campaign_review.csv. Each row is one advertiser/campaign.']];
campaigns.getRange('A5:I5').values = [['Advertiser ID','Campaign ID','Advertiser','Impressions','Clicks','CTR','Review reason','Owner','Status']];
header(campaigns,'A5:I5');
data.campaigns.forEach((c,i) => {
  const row = i+6;
  campaigns.getRange(`A${row}:I${row}`).values = [[c.advertiser_id,c.campaign_id,null,c.impressions,c.clicks,null,c.review_reason,null,'Unreviewed']];
  campaigns.getRange(`C${row}`).formulas = [[`=IFNA(VLOOKUP(A${row},Advertisers!$A$5:$B$${na},2,FALSE),"Missing advertiser")`]];
  campaigns.getRange(`F${row}`).formulas = [[`=IF(D${row}=0,"n.a.",E${row}/D${row})`]];
});
campaigns.getRange(`D6:E${n}`).setNumberFormat('#,##0');
campaigns.getRange(`F6:F${n}`).setNumberFormat('0.00%');
campaigns.getRange('C:C').format.columnWidth=34;
campaigns.getRange('G:G').format.columnWidth=80;
campaigns.getRange(`H6:I${n}`).format.fill='#FFF2CC';
campaigns.getRange(`I6:I${n}`).dataValidation={rule:{type:'list',values:['Unreviewed','Investigating','Resolved']}};
campaigns.tables.add(`A5:I${n}`,true,'CampaignReview');
campaigns.freezePanes.freezeRows(5);
advertisers.getRange('A2').values = [['Advertiser lookup']];
advertisers.getRange('A2').format.font={size:15,bold:true};
advertisers.getRange('A3').values = [['Source: seeded synthetic advertiser dimension, generator version 2.']];
advertisers.getRange('A4:B4').values = [['Advertiser ID','Advertiser']];
header(advertisers,'A4:B4');
advertisers.getRange(`A5:B${na}`).values=data.advertisers.map(a=>[a.advertiser_id,a.advertiser_name]);
advertisers.getRange('B:B').format.columnWidth=38;
wb.recalculate();
const expected = data.campaigns.filter(c=>c.advertiser_id===1).reduce((s,c)=>s+c.impressions,0);
assert.equal(summary.getRange('A8').values[0][0],expected);
summary.getRange('B5').values=[[2]];
wb.recalculate();
assert.equal(summary.getRange('A8').values[0][0], data.campaigns.filter(c=>c.advertiser_id===2).reduce((s,c)=>s+c.impressions,0));
summary.getRange('B5').values=[[1]];
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'Review!A5:E8',include:'values,formulas',tableMaxRows:4,tableMaxCols:5})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#SPILL!',options:{useRegex:true,maxResults:20},summary:'Formula error scan'})).ndjson);
await fs.mkdir(outputDir,{recursive:true});
for(const sheetName of ['Review','Campaigns','Advertisers']) {
  const preview=await wb.render({sheetName,range:sheetName==='Review'?'A1:J18':sheetName==='Campaigns'?'A1:I12':'A1:E12',scale:1.5,format:'png'});
  await fs.writeFile(`${outputDir}/${sheetName}.png`,new Uint8Array(await preview.arrayBuffer()));
}
const file=await SpreadsheetFile.exportXlsx(wb);
await file.save(`${outputDir}/campaign_investigation.xlsx`);
