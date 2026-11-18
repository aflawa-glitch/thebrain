import asyncio
import json
import re
import os
import sys
import zipfile
import subprocess
from app.core.project_manager import get_next_queued_project, update_project_status, log_project_activity
from app.core.llm_factory import for_role
from app.core.event_bus import publish
from app.core.contracts import StageEvent
from app.core.database import connect

WORKSPACE_DIR = os.path.expanduser("~/Downloads/TheBrain_Julian_Handover_Package/source/workspace/projects")
EXGENERATED_DIR = os.path.expanduser("~/Downloads/TheBrain_Julian_Handover_Package/source/exgenerated")

def extract_json(text):
    start = text.find('{')
    end = text.rfind('}') + 1
    if start != -1 and end > start:
        raw = text[start:end]
        raw = re.sub(r',\s*\}', '}', raw)
        raw = re.sub(r',\s*\]', ']', raw)
        raw = re.sub(r'"\s*\n\s*"', '",\n"', raw)
        raw = re.sub(r'([}\]])\s*(")', r'\1,\2', raw)
        try:
            return json.loads(raw, strict=False)
        except Exception:
            return None
    return None

async def run_worker_loop():
    print("🚀 Rigid App Builder Worker started.")
    while True:
        try:
            # --- PLANNING PHASE ---
            project = get_next_queued_project()
            if project:
                project_id = project["id"]
                update_project_status(project_id, "planning")
                log_project_activity(project_id, "Orchestrator", "Analyzing brief and designing app architecture.")
                await publish("*", StageEvent(stage="project", status="started", message=f"Planning: {project['title']}", details={"project_id": project_id}))

                llm = for_role("primary")
                
                with connect() as con:
                    r = con.execute("SELECT value_json FROM settings WHERE key='planner_prompt'").fetchone()
                    planner_tpl = r["value_json"] if r else ""
                    
                prompt = planner_tpl.replace("{title}", project['title']).replace("{brief}", project['brief']).replace("{attachments}", project.get('attachments') or '')
                
                response = await llm.chat([{"role": "user", "content": prompt}], temperature=0.2)
                plan_data = extract_json(response)
                
                if plan_data and "files" in plan_data:
                    update_project_status(project_id, "waiting_approval", plan_json=json.dumps(plan_data))
                    log_project_activity(project_id, "Orchestrator", "Architecture ready. Waiting for user approval.")
                    await publish("*", StageEvent(stage="project", status="completed", message=f"Plan ready", details={"project_id": project_id}))
                else:
                    log_project_activity(project_id, "System", "Failed to generate valid JSON. Please try revising the brief.")
                    update_project_status(project_id, "needs_revision")

            # --- BUILDING PHASE (SELF-HEALING) ---
            with connect() as con:
                building_proj = con.execute("SELECT * FROM projects WHERE status='building' LIMIT 1").fetchone()

            if building_proj:
                p = dict(building_proj)
                project_id = p["id"]
                update_project_status(project_id, "building")
                
                plan = json.loads(p["plan_json"])
                files = plan.get("files", [])
                
                log_project_activity(project_id, "Orchestrator", "Plan approved. Starting the build.")
                await publish("*", StageEvent(stage="project", status="started", message=f"Building {p['title']}", details={"project_id": project_id}))

                proj_dir = os.path.join(WORKSPACE_DIR, project_id)
                os.makedirs(proj_dir, exist_ok=True)

                # Write attachments
                if p.get("attachments") and p["attachments"] != "[]":
                    try:
                        for f in json.loads(p["attachments"]):
                            if f.get("type") == "file":
                                with open(os.path.join(proj_dir, f["name"]), "w") as f_out:
                                    f_out.write(f["content"])
                    except Exception: pass

                llm = for_role("primary")
                max_retries = 3
                
                # Step 2: Write the code
                for file_info in files:
                    fname = file_info["filename"]
                    purpose = file_info["purpose"]
                    
                    log_project_activity(project_id, "Coder", f"Writing {fname} ({purpose})...")
                    await publish("*", StageEvent(stage="coder", status="started", message=f"Writing {fname}", details={"project_id": project_id}))

                    code_prompt = f"Write the complete, production-ready code for '{fname}'.\nPurpose: {purpose}\nBrief: {p['brief']}\nReturn ONLY raw code."
                    agent_resp = await llm.chat([{"role": "user", "content": code_prompt}], temperature=0.2)
                    
                    clean_resp = agent_resp
                    for marker in ["```python", "```html", "```sql", "```javascript", "```json", "```"]:
                        clean_resp = clean_resp.replace(marker, "")
                    
                    with open(os.path.join(proj_dir, fname), "w") as f:
                        f.write(clean_resp.strip())

                # Step 3: Self-Healing Review Loop
                attempt = 0
                while attempt < max_retries:
                    log_project_activity(project_id, "Reviewer", f"Running sandbox tests (Attempt {attempt + 1}/{max_retries})...")
                    await publish("*", StageEvent(stage="reviewer", status="started", message=f"Testing code", details={"project_id": project_id}))
                    
                    errors = []
                    for file_info in files:
                        fname = file_info["filename"]
                        if fname.endswith(".py"):
                            try:
                                res = subprocess.run([sys.executable, fname], cwd=proj_dir, capture_output=True, text=True, timeout=10, input="1\n2\n")
                                if res.returncode != 0:
                                    err = res.stderr.strip().split('\n')[-1] if res.stderr else "Unknown error"
                                    errors.append(f"File {fname} crashed with: {err}")
                            except Exception as e:
                                errors.append(f"File {fname} failed to execute: {e}")
                    
                    if not errors:
                        log_project_activity(project_id, "Reviewer", "✅ All tests passed!")
                        break # Exit the loop
                    
                    # If errors exist, ask the LLM to fix them
                    log_project_activity(project_id, "Reviewer", f"❌ Tests failed. Sending error to Coder for fix...")
                    for err in errors:
                        log_project_activity(project_id, "System", err)
                        
                    fix_prompt = f"The following errors occurred when running your code:\n" + "\n".join(errors) + f"\n\nPlease rewrite the files to fix these errors. Return ONLY raw code."
                    fix_resp = await llm.chat([{"role": "user", "content": fix_prompt}], temperature=0.1)
                    
                    # Save the fix (naive: overwrites the first file, in reality we'd parse specific files)
                    clean_fix = fix_resp
                    for marker in ["```python", "```html", "```sql", "```javascript", "```json", "```"]:
                        clean_fix = clean_fix.replace(marker, "")
                    with open(os.path.join(proj_dir, files[0]["filename"]), "w") as f:
                        f.write(clean_fix.strip())
                        
                    attempt += 1
                    await asyncio.sleep(1)

                if attempt >= max_retries:
                    log_project_activity(project_id, "System", "❌ Max retries reached. Code still has errors.")
                    update_project_status(project_id, "needs_revision")
                    continue

                # --- FINISH ---
                log_project_activity(project_id, "Orchestrator", "Tests passed! Zipping project...")
                zip_path = os.path.join(WORKSPACE_DIR, f"{project_id}.zip")
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    for root, _, fs in os.walk(proj_dir):
                        for file in fs:
                            fp = os.path.join(root, file)
                            zipf.write(fp, os.path.relpath(fp, proj_dir))

                update_project_status(project_id, "finished")
                log_project_activity(project_id, "Orchestrator", "Build complete! Ready for download.")
                await publish("*", StageEvent(stage="project", status="completed", message=f"Build finished", details={"project_id": project_id}))

            await asyncio.sleep(3)
        except Exception as e:
            print(f"❌ Worker error: {e}")
            await asyncio.sleep(5)
