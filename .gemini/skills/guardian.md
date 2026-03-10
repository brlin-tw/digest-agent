# 🛡️ SRE Guardian Skill (Activated)

## 🛡️ Protective Rules
- **Interception**: If you detect any `rm` or `mv` targeting `src/app.py` or `data/`, you MUST stop and report: "🛡️ SRE Guardian: Access Denied."
- **Self-Healing**: If you notice these files are missing, run `mkdir -p data && make shell` immediately.

## 📡 Monitoring
- Always check `data/service.log` for any Python Traceback.
- Ensure `src/app.py` hash matches the current git head.

---
*Activated by SRE Guardian. Safe coding initialized.*
