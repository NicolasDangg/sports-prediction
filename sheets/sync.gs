/**
 * Google Sheet <- GitHub sync for the paper-trading dashboard.
 *
 * Setup (once):
 *   1. In the sheet: Extensions -> Apps Script, paste this file, save.
 *   2. Project Settings (gear) -> Script Properties -> add GITHUB_TOKEN
 *      (a fine-grained token with read-only "Contents" access to this one repo).
 *   3. Run `install` once and approve the permissions. That runs a first sync and
 *      schedules `sync` every morning, after the agent has committed new state.
 */

const REPO = 'NicolasDangg/sports-prediction';
const TABS = {
  'Wallets': 'state/bankroll_history.csv',
  'Bets': 'state/ledger.csv',
  'Today': 'state/predictions.csv',
  'EPL Elo': 'state/epl_ratings.csv',
  'ATP Elo': 'state/atp_ratings.csv',
  'Deposits': 'state/deposits.csv',
};

function install() {
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('sync').timeBased().everyDays(1).atHour(9).create();
  sync();
}

function sync() {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('Add GITHUB_TOKEN under Project Settings -> Script Properties');
  const ss = SpreadsheetApp.getActive();

  for (const [tab, path] of Object.entries(TABS)) {
    const resp = UrlFetchApp.fetch(`https://api.github.com/repos/${REPO}/contents/${path}`, {
      headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github.raw' },
      muteHttpExceptions: true,
    });
    if (resp.getResponseCode() !== 200) {
      console.log(`${path}: HTTP ${resp.getResponseCode()} (not created yet?)`);
      continue;
    }
    const rows = Utilities.parseCsv(resp.getContentText()).map(r => r.map(typed));
    const width = Math.max(...rows.map(r => r.length));
    const sheet = ss.getSheetByName(tab) || ss.insertSheet(tab);
    sheet.clearContents();
    sheet.getRange(1, 1, rows.length, width).setValues(rows.map(r => pad(r, width)));
    sheet.setFrozenRows(1);
    sheet.getRange(1, 1, 1, width).setFontWeight('bold');
  }
  buildDashboard(ss);
}

/** Dashboard: latest wallet standings plus a bankroll-over-time chart, one line per wallet. */
function buildDashboard(ss) {
  let dash = ss.getSheetByName('Dashboard');
  if (dash) return;  // formulas and chart update by themselves once created
  dash = ss.insertSheet('Dashboard', 0);
  dash.getRange('A1').setValue('Latest standings').setFontWeight('bold');
  dash.getRange('A2').setFormula('=QUERY(Wallets!A:I, "select * where A = date \'"&TEXT(MAX(Wallets!A:A),"yyyy-mm-dd")&"\'", 1)');
  dash.getRange('A8').setValue('Bankroll by day').setFontWeight('bold');
  dash.getRange('A9').setFormula('=QUERY(Wallets!A:E, "select A, sum(E) where A is not null group by A pivot B", 1)');
  const chart = dash.newChart()
    .asLineChart()
    .addRange(dash.getRange('A9:F400'))
    .setNumHeaders(1)
    .setOption('title', 'Virtual bankroll ($1,000 start)')
    .setOption('interpolateNulls', true)
    .setPosition(1, 8, 0, 0)
    .build();
  dash.insertChart(chart);
  const blank = ss.getSheetByName('Sheet1');
  if (blank && blank.getLastRow() === 0) ss.deleteSheet(blank);
}

/** CSV gives text; turn numbers, booleans and ISO dates into real values so charts work. */
function typed(v) {
  if (/^-?\d+(\.\d+)?$/.test(v)) return Number(v);
  if (/^\d{4}-\d{2}-\d{2}$/.test(v)) { const [y, m, d] = v.split('-').map(Number); return new Date(y, m - 1, d); }
  if (v === 'True' || v === 'False') return v === 'True';
  return v;
}

function pad(row, width) {
  return row.length >= width ? row : row.concat(Array(width - row.length).fill(''));
}
