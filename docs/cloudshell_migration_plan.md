# NeuroShield – CloudShell Migration Plan

This guide explains **exactly** how to replicate the fully-local NeuroShield setup inside Google Cloud Shell (or any fresh Linux shell) so you can continue development from another laptop without surprises.

---
## 0. Prerequisites

| Tool | Version | Install Cmd (Cloud Shell) |
|------|---------|---------------------------|
|Python | 3.11.x | `sudo apt-get install python3.11 python3.11-venv` |
|NodeJS | ≥ 20.x | `nvm install --lts` <br>*(Cloud Shell ships with nvm)* |
|Git    | latest | *(pre-installed)* |

Cloud Shell has **5 GB** of home-disk quota. The repo + venv + Node cache fits comfortably (< 400 MB).

---
## 1. Clone & Enter Workspace
```bash
# choose a folder under $HOME
git clone https://github.com/Prudhvi333333/neuroshieldDemo.git ns-demo
cd ns-demo
```

---
## 2. Python Environment
```bash
# 2.1 create virtualenv (explicit 3.11)
python3.11 -m venv venv
source venv/bin/activate

# 2.2 upgrade pip & install deps
python -m pip install --upgrade pip
pip install -r requirements.txt  # if present
# fallback: quick install
pip install streamlit google-generativeai langgraph rich python-dotenv
```
> **NOTE** If you hit architecture build errors (e.g., `bitarray`), add `--no-binary :all:` or pin versions; those were already resolved in current `requirements.txt`.

---
## 3. Environment Variables
```bash
cp .env.example .env        # if example exists
echo "GOOGLE_API_KEY=***" >> .env
# optionally set GEMINI_MODEL=gemini-pro
```
Cloud Shell keeps files between sessions; no secret-manager required.

---
## 4. Front-End / App Run
```bash
# inside venv
python -m streamlit run app.py  --server.port 8080
```
Cloud Shell will expose **Web Preview → Port 8080**. The Streamlit dashboard appears with all agents.

---
## 5. Optional – Diagram Generation
```bash
# install mermaid CLI globally (node 20+)
npm install -g @mermaid-js/mermaid-cli puppeteer
# render diagrams if needed
mmdc -i docs/diagrams/component.mmd -o docs/images/component.png
mmdc -i docs/diagrams/firewall.mmd  -o docs/images/firewall.png
```
SVGs load fine in CloudShell Editor.

---
## 6. Typical Debug Workflow
1. Edit code in CloudShell’s IDE or VS Code “Remote – SSH”.
2. Restart Streamlit server (auto-reload works for most .py changes).
3. Tail logs: `tail -f logs/audit_log.json`.
4. Inspect agent JSON in UI tabs.

---
## 7. Next Steps / To-Dos
- [ ] Review raw LLM outputs stored in `raw_analysis_text` for fallback cases.
- [ ] Adjust prompts or parsing if risk_score 0.8 appears frequently.
- [ ] Write unit tests around `safe_json()` and each agent’s `.run()`.
- [ ] Consider containerising: build a slim Python 3.11 base + `requirements.txt` for deterministic deploys.

---
_Last updated: 2025-07-17_
