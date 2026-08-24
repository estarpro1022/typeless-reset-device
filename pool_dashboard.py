#!/usr/bin/env python3
"""Typeless Account Pool Dashboard — web-based GUI."""

import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from account_pool import AccountPool

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>号池 Dashboard</title>
<style>
  :root { --bg: #0f0f0f; --card: #1a1a1a; --text: #e0e0e0; --muted: #888;
          --accent: #4ade80; --warn: #facc15; --danger: #ef4444; --bar-bg: #2a2a2a; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,sans-serif;
         min-height:100vh; padding:24px; }
  .container { max-width:720px; margin:0 auto; }
  h1 { font-size:24px; margin-bottom:8px; }
  .subtitle { color:var(--muted); font-size:14px; margin-bottom:24px; }
  .total-card { background:var(--card); border-radius:12px; padding:20px; margin-bottom:20px;
                display:flex; justify-content:space-between; align-items:center; }
  .total-label { font-size:14px; color:var(--muted); }
  .total-value { font-size:36px; font-weight:700; }
  .total-detail { font-size:13px; color:var(--muted); }
  .account-card { background:var(--card); border-radius:12px; padding:16px; margin-bottom:10px; }
  .account-card.active { border:1px solid var(--accent); }
  .account-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }
  .account-email { font-size:15px; font-weight:600; }
  .current-badge { background:var(--accent); color:#000; font-size:10px; padding:2px 6px;
    border-radius:4px; margin-left:6px; vertical-align:middle; }
  .account-quota { font-size:14px; color:var(--muted); }
  .account-quota span { color:var(--text); font-weight:600; }
  .bar-wrap { background:var(--bar-bg); border-radius:6px; height:20px; overflow:hidden; position:relative; }
  .bar-fill { height:100%; border-radius:6px; transition:width .5s ease; position:absolute; left:0; top:0; }
  .bar-label { position:absolute; width:100%; text-align:center; font-size:11px; line-height:20px;
               color:#fff; mix-blend-mode:difference; z-index:1; }
  .bar-fill.low { background:var(--accent); } .bar-fill.mid { background:var(--warn); }
  .bar-fill.high { background:var(--danger); }
  .refresh { color:var(--muted); font-size:12px; text-align:center; margin-top:16px; }
  .pulse { animation:pulse .3s ease; }
  @keyframes pulse { 50% { opacity:.5; } }
  .switch-btn { background:transparent; border:1px solid #555; color:var(--muted);
    border-radius:6px; padding:4px 10px; font-size:12px; cursor:pointer; transition:all .2s; }
  .switch-btn:hover { border-color:var(--accent); color:var(--accent); }
  .switch-btn:disabled { opacity:.3; cursor:not-allowed; }
  .toast { position:fixed; top:16px; right:16px; background:var(--accent); color:#000;
    padding:10px 18px; border-radius:8px; font-size:14px; z-index:99; display:none; }
  .chart-card { background:var(--card); border-radius:12px; padding:20px; margin-bottom:20px; }
  .chart-card .total-label { margin-bottom:12px; }
  .chart-empty { color:var(--muted); text-align:center; padding:32px 0; font-size:14px; }
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
</head>
<body>
<div id="toast" class="toast"></div>
<div class="container">
  <h1>🔋 号池 Dashboard</h1>
  <p class="subtitle" id="updateTime">加载中...</p>
  <div class="total-card">
    <div>
      <div class="total-label">已用字数</div>
      <div class="total-value" id="totalUsed">--</div>
      <div class="total-detail" id="totalDetail">--</div>
    </div>
    <div style="text-align:right">
      <div class="total-label">账号数</div>
      <div class="total-value" id="totalAccounts" style="font-size:28px">--</div>
    </div>
  </div>
  <div class="chart-card">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
      <button id="prevWeek" class="switch-btn" onclick="changeWeek(-1)" style="font-size:16px; padding:2px 8px;">&#9664;</button>
      <span class="total-label" id="weekLabel" style="margin-bottom:0;">本周累计用量</span>
      <button id="nextWeek" class="switch-btn" onclick="changeWeek(1)" style="font-size:16px; padding:2px 8px;">&#9654;</button>
    </div>
    <div style="position:relative; height:220px;">
      <canvas id="trendChart"></canvas>
    </div>
    <div class="chart-empty" id="chartEmpty" style="display:none">尚无足够历史数据，刷新几次配额后会出现趋势图</div>
  </div>
  <div style="text-align:right; margin-bottom:16px;">
    <button class="switch-btn" id="syncBtn" onclick="syncDict()" style="font-size:13px;">📖 同步词典</button>
  </div>
  <div id="accounts"></div>
  <p class="refresh">每 60 秒自动刷新 · <span id="countdown">60</span>s</p>
</div>
<script>
async function load() {
  try {
    const resp = await fetch('/api/pool');
    const data = await resp.json();

    let totalUsed = 0, totalLimit = 0;
    const accounts = [];

    for (const [alias, slot] of Object.entries(data.accounts)) {
      totalUsed += slot.quota_used;
      totalLimit += slot.quota_limit;
      const pct = (slot.quota_used / slot.quota_limit * 100) || 0;
      const css = pct > 80 ? 'high' : pct > 50 ? 'mid' : 'low';
      accounts.push({ alias, email: slot.email, used: slot.quota_used,
                      limit: slot.quota_limit, pct, css });
    }

    accounts.sort((a, b) => b.used - a.used);

    document.getElementById('totalUsed').textContent = totalUsed.toLocaleString() + ' 字';
    document.getElementById('totalDetail').textContent =
      `每周总共 ${totalLimit.toLocaleString()} 字`;
    document.getElementById('totalAccounts').textContent = accounts.length;

    const current = data.current;
    document.getElementById('accounts').innerHTML = accounts.map(a => `
      <div class="account-card${a.alias === current ? ' active' : ''}">
        <div class="account-header">
          <span class="account-email">${a.alias} · ${a.email}${a.alias === current ? '<span class="current-badge">当前</span>' : ''}</span>
          <span class="account-quota">
            <span>${a.used.toLocaleString()}</span> / ${a.limit.toLocaleString()} 字
          </span>
        </div>
        <div class="bar-wrap">
          <div class="bar-fill ${a.css}" style="width:${Math.max(a.pct, 2)}%"></div>
          <div class="bar-label">${a.pct.toFixed(0)}%</div>
        </div>
        <div style="margin-top:8px;text-align:right">
          <button class="switch-btn" onclick="switchTo('${a.alias}')"${a.alias === current ? ' disabled' : ''}>${a.alias === current ? '当前账号' : '切到此号'}</button>
        </div>
      </div>
    `).join('');

    const now = new Date();
    document.getElementById('updateTime').textContent =
      `最后更新: ${now.toLocaleTimeString('zh-CN')}`;
  } catch(e) {
    document.getElementById('accounts').innerHTML =
      '<p style="color:var(--danger)">加载失败，确认号池服务已启动</p>';
  }
}

async function switchTo(alias) {
  const btns = document.querySelectorAll('.switch-btn');
  btns.forEach(b => b.disabled = true);
  try {
    const resp = await fetch('/api/restore/' + alias);
    const data = await resp.json();
    const toast = document.getElementById('toast');
    if (data.success) {
      toast.textContent = '✓ 已切换到 ' + alias + '，重新打开 Typeless 即可';
      toast.style.background = 'var(--accent)';
      load();
    } else {
      toast.textContent = '✗ 切换失败: ' + data.error;
      toast.style.background = 'var(--danger)';
    }
    toast.style.display = 'block';
    setTimeout(() => toast.style.display = 'none', 3000);
  } catch(e) {
    alert('请求失败: ' + e);
  }
  btns.forEach(b => b.disabled = false);
}

let trendChart = null;
let weekOffset = 0;

async function loadChart() {
  try {
    const resp = await fetch('/api/history?week=' + weekOffset);
    const data = await resp.json();
    if (!data.labels || data.labels.length === 0) {
      document.getElementById('chartEmpty').style.display = 'block';
      if (trendChart) { trendChart.destroy(); trendChart = null; }
      return;
    }
    document.getElementById('chartEmpty').style.display = 'none';

    // Update week label and button states
    const label = weekOffset === 0 ? '本周累计用量' : data.week_start + ' — ' + data.week_end;
    document.getElementById('weekLabel').textContent = label;
    document.getElementById('prevWeek').disabled = false;
    document.getElementById('nextWeek').disabled = !data.has_next;

    const ctx = document.getElementById('trendChart').getContext('2d');
    if (trendChart) trendChart.destroy();
    trendChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.labels,
        datasets: [{
          data: data.data,
          borderColor: '#4ade80',
          backgroundColor: '#4ade8020',
          borderWidth: 2,
          pointRadius: 4,
          pointHoverRadius: 6,
          pointBackgroundColor: '#4ade80',
          fill: true,
          tension: 0.3,
          spanGaps: false,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            mode: 'index', intersect: false,
            backgroundColor: '#1a1a1a', borderColor: '#333', borderWidth: 1,
            titleColor: '#e0e0e0', bodyColor: '#ccc',
            callbacks: {
              label: ctx => ctx.parsed.y != null ? '累计: ' + ctx.parsed.y.toLocaleString() + ' 字' : '暂无数据'
            }
          }
        },
        scales: {
          x: {
            ticks: { color: '#666', font: { size: 11 } },
            grid: { color: '#222' }
          },
          y: {
            title: { display: true, text: '累计字数', color: '#666' },
            ticks: { color: '#666', font: { size: 11 }, callback: v => v.toLocaleString() },
            grid: { color: '#222' },
            beginAtZero: true
          }
        },
        interaction: { mode: 'nearest', axis: 'x', intersect: false }
      }
    });
  } catch(e) {
    console.error('chart load error:', e);
  }
}

function changeWeek(delta) {
  weekOffset += delta;
  loadChart();
}

async function syncDict() {
  const btn = document.getElementById('syncBtn');
  btn.disabled = true;
  btn.textContent = '⏳ 同步中...';
  try {
    const resp = await fetch('/api/sync-dict');
    const data = await resp.json();
    const toast = document.getElementById('toast');
    if (data.success) {
      const parts = [];
      for (const [alias, n] of Object.entries(data.imported)) {
        parts.push(alias + ': +' + (typeof n === 'number' ? n : '✗'));
      }
      toast.textContent = '✓ 词典已同步 · ' + parts.join(', ');
      toast.style.background = 'var(--accent)';
    } else {
      toast.textContent = '✗ 同步失败: ' + data.error;
      toast.style.background = 'var(--danger)';
    }
    toast.style.display = 'block';
    setTimeout(() => toast.style.display = 'none', 4000);
  } catch(e) {
    alert('请求失败: ' + e);
  }
  btn.disabled = false;
  btn.textContent = '📖 同步词典';
}

async function refreshAll() {
  await load();
  await loadChart();
}

let cd = 60;
setInterval(() => { cd--; if(cd<=0){ cd=60; refreshAll(); }
  document.getElementById('countdown').textContent = cd; }, 1000);
refreshAll();
</script>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/restore/"):
            alias = self.path.split("/")[-1]
            try:
                pool = AccountPool()
                pool.restore(alias)
                body = json.dumps({"success": True, "alias": alias}).encode()
            except Exception as e:
                body = json.dumps({"success": False, "error": str(e)}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/api/sync-dict":
            pool = AccountPool()
            try:
                results = pool.sync_all_dicts()
                body = json.dumps({"success": True, **results}).encode()
            except Exception as e:
                body = json.dumps({"success": False, "error": str(e)}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        elif self.path.startswith("/api/history"):
            import urllib.parse
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            week = int(qs.get("week", [0])[0])
            pool = AccountPool()
            data = pool.get_history(week_offset=week)
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/api/pool":
            pool = AccountPool()
            # Live refresh from API — parallel per account
            live_data = {}
            with ThreadPoolExecutor(max_workers=len(pool.accounts) or 1) as ex:
                futures = {ex.submit(pool._refresh_quota, s): alias for alias, s in pool.accounts.items()}
                for f in as_completed(futures):
                    alias = futures[f]
                    s = pool.accounts[alias]
                    try:
                        ok = f.result()
                    except Exception:
                        ok = False
                    live_data[alias] = {
                        "email": s.email,
                        "quota_limit": s.quota_limit,
                        "quota_used": s.quota_used,
                        "quota_updated_at": s.quota_updated_at,
                        "live": ok,
                    }
            pool._save()  # persist after all parallel refreshes complete
            # Detect current active account
            current_alias = None
            try:
                from crypto_utils import decrypt_user_data
                cur = decrypt_user_data()
                cur_id = cur.get("user_id")
                for alias, s in pool.accounts.items():
                    if s.user_id == cur_id:
                        current_alias = alias
                        break
            except Exception:
                pass
            data = {"updated_at": time.time(), "current": current_alias, "accounts": live_data}
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/" or self.path == "/index.html":
            body = DASHBOARD_HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass  # quiet


def _background_sampler():
    """Sample all account quotas every 60s, even when browser is closed."""
    while True:
        try:
            pool = AccountPool()
            if pool.accounts:
                with ThreadPoolExecutor(max_workers=len(pool.accounts)) as ex:
                    futures = [ex.submit(pool._refresh_quota, s) for s in pool.accounts.values()]
                    for f in as_completed(futures):
                        try:
                            f.result()
                        except Exception:
                            pass
        except Exception:
            pass
        time.sleep(60)


def _run_server(port: int, no_open: bool):
    """Start the actual HTTP server + background sampler."""
    server = HTTPServer(("127.0.0.1", port), DashboardHandler)
    url = f"http://127.0.0.1:{port}"

    print(f"  🚀 Dashboard → {url}")
    print(f"  📊 Background sampler every 60s (browser open or not)")
    print(f"  Press Ctrl+C to stop")

    threading.Thread(target=_background_sampler, daemon=True).start()

    if not no_open:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down...")
        server.shutdown()


def _run_with_reload(args):
    """Dev mode: restart the server when any project .py file changes."""
    script_dir = Path(__file__).resolve().parent
    watched = {
        str(script_dir / f): (script_dir / f).stat().st_mtime
        for f in ["pool_dashboard.py", "account_pool.py", "crypto_utils.py"]
        if (script_dir / f).exists()
    }
    proc = None
    tick = 0

    def start():
        nonlocal proc
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        cmd = [sys.executable, str(script_dir / "pool_dashboard.py"),
               "--port", str(args.port)]
        if args.no_open:
            cmd.append("--no-open")
        proc = subprocess.Popen(cmd)

    start()
    names = ", ".join(Path(p).name for p in watched)
    print(f"  🔁 Auto-reload active — watching {names} [{time.strftime('%H:%M:%S')}]")

    try:
        while True:
            time.sleep(1)
            tick += 1
            if tick % 30 == 0:
                print(f"  💤 watcher alive [{time.strftime('%H:%M:%S')}]")
            for path, old_mtime in list(watched.items()):
                new_mtime = os.stat(path).st_mtime
                if new_mtime != old_mtime:
                    watched[path] = new_mtime
                    print(f"  🔄 {Path(path).name} changed, restarting... [{time.strftime('%H:%M:%S')}]")
                    start()
                    break  # one restart covers all changes
    except KeyboardInterrupt:
        print(f"\n  Shutting down... [{time.strftime('%H:%M:%S')}]")
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pool Dashboard")
    parser.add_argument("--port", "-p", type=int, default=8710, help="HTTP port (default: 8710)")
    parser.add_argument("--no-open", action="store_true", help="Don't open browser")
    parser.add_argument("--reload", action="store_true", help="Auto-restart on file change (dev only)")
    args = parser.parse_args()

    if args.reload:
        _run_with_reload(args)
    else:
        _run_server(args.port, args.no_open)


if __name__ == "__main__":
    main()
