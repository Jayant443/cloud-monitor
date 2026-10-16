import { useState } from 'react'
import type { DashboardView } from './Navigation'

const PULL_COMMAND = 'docker pull morgoth443/cloud-monitor-agent:latest'

const RUN_COMMAND = `docker run -d --name monitoring-agent --restart unless-stopped \\
  --pid=host --net=host \\
  -v /var/run/docker.sock:/var/run/docker.sock:ro \\
  -v /proc:/host/proc:ro \\
  -v /sys:/host/sys:ro \\
  -v /:/rootfs:ro \\
  -e BACKEND_URL="http://YOUR_BACKEND_IP:8000" \\
  -e API_KEY="your-api-key" \\
  morgoth443/cloud-monitor-agent:latest`

const VERIFY_COMMAND = 'docker logs monitoring-agent'

function CodeBlock({ command, label }: { command: string; label: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(command)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }
  return <div className="gs-code"><div className="gs-code-head"><span>{label}</span><button className="text-button" onClick={() => void copy()}>{copied ? 'Copied ✓' : 'Copy'}</button></div><pre><code>{command}</code></pre></div>
}

export function GettingStarted({ onEnter }: { onEnter: (view: DashboardView) => void }) {
  return <div className="gs-wrap">
    <header className="gs-topbar"><span className="gs-brand">TheMonitor</span><button className="primary-button" onClick={() => onEnter('overview')}>Open dashboard</button></header>
    <main className="gs-main">
      <div className="section-kicker">GETTING STARTED</div>
      <h1>Monitor an EC2 instance in minutes</h1>
      <p className="gs-sub">Run the monitoring agent container on any EC2 host and it starts reporting to this server. You need Docker installed on that host.</p>

      <section className="panel gs-step">
        <div className="panel-title-row"><div><div className="section-kicker">STEP 1</div><h2>Get an API key</h2></div><span className="count-badge">1</span></div>
        <p className="gs-text">Monitoring agents authenticate with an API key. Create one under <strong>Settings → API keys</strong>, copy the full key shown once, and keep it ready for step 3.</p>
        <button className="primary-button" onClick={() => onEnter('settings')}>Open Settings → API keys</button>
      </section>

      <section className="panel gs-step">
        <div className="panel-title-row"><div><div className="section-kicker">STEP 2</div><h2>Pull the monitoring agent image</h2></div><span className="count-badge">2</span></div>
        <p className="gs-text">On the EC2 instance you want to monitor, pull the monitoring agent image from Docker Hub:</p>
        <CodeBlock label="Pull" command={PULL_COMMAND} />
      </section>

      <section className="panel gs-step">
        <div className="panel-title-row"><div><div className="section-kicker">STEP 3</div><h2>Run the monitoring agent</h2></div><span className="count-badge">3</span></div>
        <p className="gs-text">Start the monitoring agent with host access so it reports real host metrics. Replace <code>YOUR_BACKEND_IP</code> with this server’s address and <code>your-api-key</code> with the key from step 1.</p>
        <CodeBlock label="Run" command={RUN_COMMAND} />
      </section>

      <section className="panel gs-step">
        <div className="panel-title-row"><div><div className="section-kicker">STEP 4</div><h2>Verify</h2></div><span className="count-badge">4</span></div>
        <p className="gs-text">Check the monitoring agent logs for <code>Metrics sent to backend</code>, then open the dashboard — the host appears within seconds.</p>
        <CodeBlock label="Logs" command={VERIFY_COMMAND} />
        <button className="primary-button" onClick={() => onEnter('overview')}>Open dashboard</button>
      </section>
    </main>
  </div>
}
