import json
from pathlib import Path
from typing import Any

def generate_html_dashboard(stats_data: dict[str, Any], output_path: str | Path) -> None:
    """
    Generate a standalone HTML dashboard visualizing Audit log statistics.
    
    Args:
        stats_data: Dictionary containing stats: total, by_action, by_tool, by_policy.
        output_path: Path to save the HTML file.
    """
    path = Path(output_path)
    
    # Prepare serializable data for embedded JS
    json_data = json.dumps(stats_data, indent=2)

    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>mcpguard dashboard</title>
    <!-- Include Chart.js via CDN -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 24px;
            background-color: #f6f8fa;
            color: #24292f;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding-bottom: 24px;
            border-bottom: 1px solid #d0d7de;
            margin-bottom: 32px;
        }
        h1 {
            margin: 0;
            font-size: 28px;
            font-weight: 600;
        }
        .summary-banner {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }
        .card {
            background: white;
            border: 1px solid #d0d7de;
            border-radius: 6px;
            padding: 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }
        .card-title {
            font-size: 14px;
            color: #57606a;
            margin-bottom: 8px;
        }
        .card-value {
            font-size: 32px;
            font-weight: 700;
        }
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-bottom: 32px;
        }
        @media (max-width: 768px) {
            .grid { grid-template-columns: 1fr; }
        }
        canvas {
            max-height: 400px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 16px;
        }
        th, td {
            text-align: left;
            padding: 12px;
            border-bottom: 1px solid #d0d7de;
        }
        th {
            background-color: #f6f8fa;
            font-weight: 600;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🛡️ mcpguard dashboard</h1>
            <div style="font-size: 14px; color: #57606a;">Total Events: <strong id="total-banner-value">0</strong></div>
        </header>

        <div class="summary-banner">
            <div class="card">
                <div class="card-title">Allowed</div>
                <div class="card-value" style="color: #1a7f37;" id="allowed-count">0</div>
            </div>
            <div class="card">
                <div class="card-title">Denied</div>
                <div class="card-value" style="color: #cf222e;" id="denied-count">0</div>
            </div>
            <div class="card">
                <div class="card-title">Review / Log</div>
                <div class="card-value" style="color: #0969da;" id="review-count">0</div>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <h3>Action breakdown</h3>
                <canvas id="actionsChart"></canvas>
            </div>
            <div class="card">
                <h3>Policy trigger rate</h3>
                <canvas id="policiesChart"></canvas>
            </div>
        </div>

        <div class="card">
            <h3>Tool usage detail</h3>
            <table id="tools-table">
                <thead>
                    <tr><th>Tool Name</th><th>Invocations</th></tr>
                </thead>
                <tbody>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        const stats = {STATS_JSON};
        
        // Populate banner
        document.getElementById('total-banner-value').innerText = stats.total;
        document.getElementById('allowed-count').innerText = stats.by_action["ALLOW"] || 0;
        document.getElementById('denied-count').innerText = stats.by_action["DENY"] || 0;
        document.getElementById('review-count').innerText = (stats.by_action["APPROVE"] || 0) + (stats.by_action["LOG"] || 0);

        // Populate Audit graphs
        const actionsCtx = document.getElementById('actionsChart').getContext('2d');
        new Chart(actionsCtx, {
            type: 'pie',
            data: {
                labels: Object.keys(stats.by_action),
                datasets: [{
                    label: '# of Events',
                    data: Object.values(stats.by_action),
                    backgroundColor: [
                        '#1a7f37', // ALLOW
                        '#cf222e', // DENY
                        '#0969da', // LOG
                        '#8250df', // APPROVE
                        '#efb034'  # UNKNOWN
                    ],
                }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });

        const policyCtx = document.getElementById('policiesChart').getContext('2d');
        new Chart(policyCtx, {
            type: 'bar',
            data: {
                labels: Object.keys(stats.by_policy),
                datasets: [{
                    label: 'Trigger Count',
                    data: Object.values(stats.by_policy),
                    backgroundColor: '#57606a',
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: { y: { beginAtZero: true } }
            }
        });

        // Populate detail table
        const tbody = document.querySelector('#tools-table tbody');
        Object.entries(stats.by_tool).sort((a,b) => b[1] - a[1]).forEach(([tool, count]) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td><code>${tool}</code></td><td>${count}</td>`;
            tbody.appendChild(tr);
        });

    </script>
</body>
</html>
"""
    # Embed data
    final_output = html_template.replace("{STATS_JSON}", json_data)
    
    path.write_text(final_output)
