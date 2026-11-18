document.addEventListener('DOMContentLoaded', () => {
    // --- 1. Cache Elements ---
    const els = {
        historyList: document.getElementById('historyList'),
        messages: document.getElementById('messages'),
        input: document.getElementById('messageInput'),
        sendBtn: document.getElementById('sendBtn'),
        stopBtn: document.getElementById('stopBtn'),
        newChatBtn: document.getElementById('newChatBtn'),
        processArea: document.getElementById('processArea'),
        processDetail: document.getElementById('processDetail'),
        contextMenu: document.getElementById('contextMenu'),
        chatView: document.getElementById('chatView'),
        projectsView: document.getElementById('projectsView'),
        settingsView: document.getElementById('settingsView'),
        projList: document.getElementById('projectListSidebar'),
        projForm: document.getElementById('newProjectForm'),
        projDetails: document.getElementById('projectDetails'),
        projTitleInput: document.getElementById('projTitle'),
        projBriefInput: document.getElementById('projBrief'),
        projFileInput: document.getElementById('projFile'),
        projSubmitBtn: document.getElementById('submitProjectBtn'),
        projShowFormBtn: document.getElementById('showNewProjectBtn'),
        projCancelBtn: document.getElementById('cancelNewProjectBtn'),
        attachmentList: document.getElementById('attachmentList'),
        officeChatContainer: document.getElementById('officeChatContainer')
    };

    let state = {
        activeConversationId: null,
        activeTraceId: null,
        isProcessing: false,
        activeProjectId: null,
        pendingFiles: [],
        activeConvId: null
    };

    // --- 2. Health Check ---
    async function checkHealth() {
        try {
            const res = await fetch('/api/health');
            const data = await res.json();
            const dot = document.getElementById('statusDot');
            const text = document.getElementById('statusText');
            if (!dot || !text) return;
            if (data.readiness && data.readiness.model === 'reachable') {
                dot.classList.add('online'); text.textContent = 'Model connected';
            } else {
                dot.classList.remove('online'); text.textContent = 'Model offline';
            }
        } catch (e) {
            const text = document.getElementById('statusText');
            if (text) text.textContent = 'Backend offline';
        }
    }
    checkHealth();
    setInterval(checkHealth, 5000);

    // --- 3. Navigation ---
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            ['chatView', 'projectsView', 'settingsView'].forEach(id => {
                const el = document.getElementById(id); if (el) el.hidden = true;
            });
            if (btn.dataset.view === 'chat') { els.chatView.hidden = false; }
            else if (btn.dataset.view === 'projects') { 
                els.projectsView.hidden = false; 
                loadProjects(); 
                connectProjectStream();
                if (state.activeProjectId) loadProjectChat(state.activeProjectId);
            }
            else if (btn.dataset.view === 'settings') { 
                els.settingsView.hidden = false; 
                loadSettings(); 
            }
        };
    });

    function showChatView() {
        document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
        document.querySelector('[data-view="chat"]').classList.add('active');
        ['chatView', 'projectsView', 'settingsView'].forEach(id => {
            const el = document.getElementById(id); if (el) el.hidden = true;
        });
        els.chatView.hidden = false;
    }

    // --- 4. Chat Logic ---
    if (els.input) {
        els.input.addEventListener('input', () => {
            els.input.style.height = 'auto';
            els.input.style.height = (els.input.scrollHeight) + 'px';
            updateUIState();
        });
        els.input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
        });
    }

    if (els.sendBtn) els.sendBtn.onclick = sendMessage;
    if (els.stopBtn) els.stopBtn.onclick = async () => {
        if (state.activeTraceId) await fetch(`/api/tasks/${state.activeTraceId}/cancel`, { method: 'POST' });
    };

    if (els.newChatBtn) {
        els.newChatBtn.onclick = async () => {
            try {
                const res = await fetch('/api/conversations', { method: 'POST' });
                const data = await res.json();
                state.activeConversationId = data.conversation_id;
                els.messages.innerHTML = '<div class="welcome-screen" id="welcome"><div class="welcome-logo">J</div><h1>What are we working on?</h1><p>Julian coordinates the work, checks the evidence, and tells you what is verified.</p></div>';
                els.input.value = '';
                els.input.style.height = 'auto';
                updateUIState();
                loadHistory();
                showChatView();
            } catch (e) { console.error(e); }
        };
    }

    function updateUIState() {
        if (!els.input || !els.sendBtn || !els.stopBtn || !els.processArea) return;
        const hasText = els.input.value.trim().length > 0;
        if (state.isProcessing) {
            els.sendBtn.classList.add('hidden'); els.stopBtn.classList.remove('hidden'); els.processArea.hidden = false;
        } else {
            els.stopBtn.classList.add('hidden'); els.sendBtn.classList.remove('hidden'); els.processArea.hidden = true;
            if (hasText) { els.sendBtn.classList.remove('disabled'); els.sendBtn.disabled = false; }
            else { els.sendBtn.classList.add('disabled'); els.sendBtn.disabled = true; }
        }
    }

    async function loadHistory() {
        if (!els.historyList) return;
        try {
            const res = await fetch('/api/conversations');
            const data = await res.json();
            els.historyList.innerHTML = '';
            if (!data.conversations || data.conversations.length === 0) {
                els.historyList.innerHTML = '<div style="padding:10px;font-size:13px;color:#8e8e8e;">No recent chats.</div>';
                return;
            }
            data.conversations.forEach(c => {
                const div = document.createElement('div');
                div.className = 'history-item'; div.dataset.id = c.id;
                div.innerHTML = `<span class="history-title">${c.title}</span><span class="history-dots">⋯</span>`;
                els.historyList.appendChild(div);
            });
        } catch (e) { console.error(e); }
    }

    async function loadConversation(id) {
        try {
            state.activeConversationId = id;
            const res = await fetch(`/api/conversations/${id}`);
            const data = await res.json();
            showChatView();
            if (!els.messages) return;
            const welcome = document.getElementById('welcome');
            if (welcome) welcome.style.display = 'none';
            els.messages.innerHTML = '';
            if (data.messages && data.messages.length > 0) {
                data.messages.forEach(m => {
                    const msgDiv = document.createElement('div');
                    msgDiv.className = `message ${m.role}`;
                    msgDiv.innerHTML = `<div class="msg-content">${m.content}</div>`;
                    els.messages.appendChild(msgDiv);
                });
                els.messages.scrollTop = els.messages.scrollHeight;
            }
        } catch (e) { console.error(e); }
    }

    async function sendMessage() {
        const text = els.input.value.trim();
        if (!text || state.isProcessing) return;
        els.input.value = ''; els.input.style.height = 'auto'; updateUIState();

        if (!state.activeConversationId) {
            const res = await fetch('/api/conversations', { method: 'POST' });
            const data = await res.json();
            state.activeConversationId = data.conversation_id; loadHistory();
        }

        const welcome = document.getElementById('welcome');
        if (welcome) welcome.style.display = 'none';
        
        const userDiv = document.createElement('div');
        userDiv.className = 'message user';
        userDiv.innerHTML = `<div class="msg-content">${text}</div>`;
        els.messages.appendChild(userDiv);

        const assDiv = document.createElement('div');
        assDiv.className = 'message assistant';
        const assContent = document.createElement('div');
        assContent.className = 'msg-content';
        assDiv.appendChild(assContent);
        els.messages.appendChild(assDiv);
        els.messages.scrollTop = els.messages.scrollHeight;

        state.isProcessing = true; updateUIState();

        try {
            const response = await fetch('/api/chat/stream', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text, conversation_id: state.activeConversationId })
            });
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '', fullText = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const parts = buffer.split('\n\n'); buffer = parts.pop();
                for (const part of parts) {
                    const lines = part.split('\n'); let type = '', dataStr = '';
                    for (const line of lines) {
                        if (line.startsWith('event: ')) type = line.substring(7).trim();
                        if (line.startsWith('data: ')) dataStr = line.substring(6).trim();
                    }
                    if (!dataStr) continue;
                    const data = JSON.parse(dataStr);
                    if (type === 'meta') state.activeTraceId = data.trace_id;
                    if (type === 'status') els.processDetail.textContent = data.message;
                    if (type === 'token') { fullText += data.content; assContent.textContent = fullText; els.messages.scrollTop = els.messages.scrollHeight; }
                    if (type === 'result') { assContent.textContent = data.answer; state.activeTraceId = null; }
                }
            }
        } catch (e) { assContent.textContent = "Request failed."; }
        finally { state.isProcessing = false; state.activeTraceId = null; updateUIState(); loadHistory(); checkMoveBtn(); }
    }

    // --- Context Menu ---
    document.addEventListener('click', (e) => {
        const dots = e.target.closest('.history-dots');
        if (dots) {
            e.preventDefault(); e.stopPropagation();
            const item = dots.closest('.history-item'); state.activeConvId = item.dataset.id;
            const rect = dots.getBoundingClientRect();
            if (els.contextMenu) {
                els.contextMenu.style.position = 'fixed'; els.contextMenu.style.top = `${rect.bottom + 5}px`; els.contextMenu.style.left = `${rect.left - 120}px`;
                els.contextMenu.classList.remove('hidden'); els.contextMenu.style.display = 'flex';
            }
            return;
        }
        if (els.contextMenu && !els.contextMenu.contains(e.target)) { els.contextMenu.classList.add('hidden'); els.contextMenu.style.display = 'none'; }
        const item = e.target.closest('.history-item');
        if (item && !e.target.closest('.history-dots')) loadConversation(item.dataset.id);
    });

    if (document.getElementById('menuRename')) document.getElementById('menuRename').onclick = async () => {
        els.contextMenu.classList.add('hidden');
        const newTitle = prompt("Rename chat:", "New Title");
        if (newTitle && state.activeConvId) {
            await fetch(`/api/conversations/${state.activeConvId}`, { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ title: newTitle }) });
            loadHistory();
        }
    };
    if (document.getElementById('menuDelete')) document.getElementById('menuDelete').onclick = async () => {
        els.contextMenu.classList.add('hidden');
        if (confirm("Delete this chat?") && state.activeConvId) {
            await fetch(`/api/conversations/${state.activeConvId}`, { method: 'DELETE' });
            els.messages.innerHTML = ''; state.activeConversationId = null; loadHistory(); showChatView();
        }
    };

    // --- 5. Project Logic ---
    function renderAttachments() {
        if (!els.attachmentList) return;
        els.attachmentList.innerHTML = '';
        state.pendingFiles.forEach((item, index) => {
            const div = document.createElement('div');
            div.style.cssText = 'display: flex; justify-content: space-between; align-items: center; background: #fff; padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 13px; margin-bottom: 4px;';
            div.innerHTML = `<span>${item.type === 'file' ? '📄 ' + item.name : '🔗 ' + item.content}</span><button style="background:#ef4444;color:#fff;border:none;border-radius:4px;padding:2px 8px;cursor:pointer;" onclick="removeAttachment(${index})">✕</button>`;
            els.attachmentList.appendChild(div);
        });
    }
    window.removeAttachment = (index) => { state.pendingFiles.splice(index, 1); renderAttachments(); };

    if (els.projFileInput) els.projFileInput.onchange = async (e) => {
        const file = e.target.files[0]; if (!file) return;
        const formData = new FormData(); formData.append('file', file);
        try {
            els.projFileInput.disabled = true;
            const res = await fetch('/api/uploads?conversation_id=project-upload', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.extracted_text) { state.pendingFiles.push({ type: 'file', name: data.filename, content: data.extracted_text }); renderAttachments(); }
        } catch (e) { alert("Upload failed."); } finally { els.projFileInput.disabled = false; els.projFileInput.value = ''; }
    };

    if (document.getElementById('addLinkBtn')) document.getElementById('addLinkBtn').onclick = () => {
        const url = prompt("Enter URL:");
        if (url) { state.pendingFiles.push({ type: 'link', name: 'link', content: url }); renderAttachments(); }
    };

    if (els.projShowFormBtn) {
        els.projShowFormBtn.onclick = () => { els.projForm.style.display = 'block'; els.projDetails.style.display = 'none'; };
        els.projCancelBtn.onclick = () => { els.projForm.style.display = 'none'; els.projDetails.style.display = 'none'; };
    }

    if (els.projSubmitBtn) els.projSubmitBtn.onclick = async () => {
        const title = els.projTitleInput.value.trim(); const brief = els.projBriefInput.value.trim();
        if (!title || !brief) return alert("Fill title and brief.");
        
        const finalAttachments = JSON.stringify(state.pendingFiles);
        els.projSubmitBtn.disabled = true; els.projSubmitBtn.textContent = "Queuing...";
        try {
            const res = await fetch('/api/projects', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ title, brief, attachments: finalAttachments }) });
            const data = await res.json();
            state.activeProjectId = data.project_id;
            els.projTitleInput.value = ''; els.projBriefInput.value = ''; state.pendingFiles = []; renderAttachments();
            els.projForm.style.display = 'none'; els.projDetails.style.display = 'block';
            await loadProjects();
            loadProjectChat(state.activeProjectId);
        } catch(e) { alert("Error queuing."); } finally { els.projSubmitBtn.disabled = false; els.projSubmitBtn.textContent = "Queue Project"; }
    };

    async function loadProjects() {
        if (!els.projList) return;
        try {
            const res = await fetch('/api/projects');
            const data = await res.json();
            const projects = data.projects || [];
            els.projList.innerHTML = '';
            if (projects.length === 0) { els.projList.innerHTML = '<div style="padding:20px;text-align:center;color:#888;">No projects yet.</div>'; return; }
            
            projects.forEach(p => {
                const div = document.createElement('div');
                div.style.cssText = `padding: 12px; border-radius: 6px; cursor: pointer; margin-bottom: 4px; font-size: 14px; display: flex; justify-content: space-between; align-items: center; ${state.activeProjectId === p.id ? 'background: #e5e7eb; font-weight: bold;' : 'background: transparent;'}`;
                div.innerHTML = `<span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${p.title}</span>`;
                let color = '#f59e0b'; 
                if (p.status === 'waiting_approval') color = '#3b82f6'; 
                if (p.status === 'building' || p.status === 'qc') color = '#8b5cf6'; 
                if (p.status === 'finished') color = '#10b981'; 
                if (p.status === 'needs_revision') color = '#ef4444'; 
                const dot = document.createElement('span');
                dot.style.cssText = `width: 8px; height: 8px; border-radius: 50%; background: ${color}; flex-shrink: 0;`;
                div.appendChild(dot);
                div.onclick = () => { state.activeProjectId = p.id; els.projForm.style.display = 'none'; els.projDetails.style.display = 'block'; loadProjects(); loadProjectChat(p.id); };
                els.projList.appendChild(div);
            });
            
            if (state.activeProjectId) {
                const p = projects.find(x => x.id === state.activeProjectId);
                if (p) renderProjectDetails(p);
            }
        } catch(e) { console.error(e); }
    }

    async function loadProjectChat(projectId) {
        if (!els.officeChatContainer) return;
        els.officeChatContainer.innerHTML = '<div style="color: #888; text-align: center;">Loading chat...</div>';
        try {
            const res = await fetch('/api/office/history');
            const data = await res.json();
            const history = data.history.filter(h => h.project_id === projectId);
            els.officeChatContainer.innerHTML = '';
            if (history.length === 0) {
                els.officeChatContainer.innerHTML = '<div style="color: #888; text-align: center; font-style: italic;">No activity yet.</div>';
            } else {
                const chron = [...history].reverse();
                chron.forEach(log => {
                    const agent = (log.agent_name || '').toLowerCase();
                    let type = 'system', icon = '⚙️';
                    if (agent.includes('julian') || agent.includes('orchestrator')) { type = 'julian'; icon = '🧠'; }
                    else if (agent.includes('qc') || agent.includes('reviewer')) { type = 'agent'; icon = '🧪'; }
                    else { type = 'agent'; icon = '🤖'; }
                    
                    const div = document.createElement('div');
                    div.className = `chat-bubble ${type}`;
                    let timeStr = log.created_at ? new Date(log.created_at).toLocaleTimeString() : '';
                    div.innerHTML = `<div class="chat-header"><span>${icon}</span> ${log.agent_name} <span style="font-weight:normal; margin-left:4px;">${timeStr}</span></div><div class="chat-content">${log.message}</div>`;
                    els.officeChatContainer.appendChild(div);
                });
                els.officeChatContainer.scrollTop = els.officeChatContainer.scrollHeight;
            }
        } catch(e) { console.error(e); }
    }

    function renderProjectDetails(p) {
        if (document.getElementById('detailTitle')) document.getElementById('detailTitle').textContent = p.title;
        let color = '#f59e0b', bg = '#fef3c7';
        if (p.status === 'waiting_approval') { color = '#3b82f6'; bg = '#eff6ff'; }
        if (p.status === 'building' || p.status === 'qc') { color = '#8b5cf6'; bg = '#f5f3ff'; }
        if (p.status === 'finished') { color = '#10b981'; bg = '#ecfdf5'; }
        if (p.status === 'needs_revision') { color = '#ef4444'; bg = '#fef2f2'; }
        const badge = document.getElementById('detailStatus');
        if (badge) { badge.textContent = (p.status || 'unknown').replace('_', ' '); badge.style.color = color; badge.style.background = bg; }
        if (document.getElementById('detailBrief')) document.getElementById('detailBrief').textContent = p.brief;
        
        const planDiv = document.getElementById('detailPlan');
        if (planDiv) {
            if (p.plan_json) {
                try {
                    const plan = JSON.parse(p.plan_json);
                    let html = `<div class="chat-bubble julian"><div class="chat-header"><span>🧠</span> Orchestrator</div><div class="chat-content"><b>Concept:</b> ${plan.concept || 'N/A'}<br><br><b>Files to build:</b><ul>`;
                    if (plan.files) {
                        plan.files.forEach(f => { html += `<li><code>${f.filename}</code> - ${f.purpose}</li>`; });
                    }
                    html += `</ul></div></div>`;
                    planDiv.innerHTML = html;
                } catch(e) { planDiv.innerHTML = ''; }
            } else { planDiv.innerHTML = ''; }
        }

        const actionArea = document.getElementById('actionArea');
        if (!actionArea) return;
        actionArea.innerHTML = '';
        if (p.status === 'waiting_approval') {
            actionArea.innerHTML = `<button onclick="approveProject('${p.id}')" style="background: #3b82f6; color: #fff; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 16px;">Approve & Build</button><div style="margin-top: 20px;"><strong style="display:block; margin-bottom: 8px;">Request Revisions:</strong><textarea id="revText_${p.id}" placeholder="Explain what needs to change..." style="width: 100%; height: 100px; padding: 12px; border: 1px solid #ccc; border-radius: 6px; margin-bottom: 10px;"></textarea><button onclick="reviseProject('${p.id}')" style="background: #f59e0b; color: #fff; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer;">Submit Revision</button></div>`;
        } else if (p.status === 'finished') {
            actionArea.innerHTML = `<a href="/api/projects/${p.id}/download" download style="display: inline-block; background: #10b981; color: #fff; text-decoration: none; padding: 12px 24px; border-radius: 6px; font-weight: bold; font-size: 16px;">⬇️ Download ZIP</a>`;
        } else if (p.status === 'needs_revision') {
            actionArea.innerHTML = `<div style="background: #fef2f2; padding: 16px; border-radius: 8px; margin-bottom: 16px; border: 1px solid #fecaca;"><strong style="color: #ef4444;">QC Failed.</strong> Check the chat logs.</div><strong style="display:block; margin-bottom: 8px;">Fix the Code:</strong><textarea id="revText_${p.id}" placeholder="Explain how to fix the broken code..." style="width: 100%; height: 100px; padding: 12px; border: 1px solid #ccc; border-radius: 6px; margin-bottom: 10px;"></textarea><button onclick="reviseProject('${p.id}')" style="background: #ef4444; color: #fff; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer;">Rebuild with Fix</button>`;
        }
    }

    window.approveProject = async (id) => { await fetch(`/api/projects/${id}/approve`, { method: 'PUT' }); loadProjects(); };
    window.reviseProject = async (id) => {
        const input = document.getElementById(`revText_${id}`);
        if (!input || !input.value.trim()) return alert("Type feedback first.");
        await fetch(`/api/projects/${id}/revise`, { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ feedback: input.value.trim(), attachments: "" }) });
        loadProjects();
    };
    window.deleteActiveProject = async () => {
        if (!state.activeProjectId || !confirm("Delete project?")) return;
        const deletedId = state.activeProjectId;
        await fetch(`/api/projects/${deletedId}`, { method: 'DELETE' });
        state.activeProjectId = null;
        document.getElementById('projectDetails').style.display = 'none';
        els.officeChatContainer.innerHTML = '<div style="color: #888; text-align: center; font-style: italic;">Select a project to see the conversation.</div>';
        loadProjects();
    };

    // --- 6. Live Project Stream ---
    let officeStream = null;
    function connectProjectStream() {
        if (officeStream) return;
        officeStream = new EventSource(`/api/office/stream?trace_id=*`);
        officeStream.onmessage = (e) => {
            const data = JSON.parse(e.data);
            if (data.stage === 'system') return;
            
            if (state.activeProjectId && data.details && data.details.project_id === state.activeProjectId) {
                loadProjectChat(state.activeProjectId); // Reload chat on any new event
            }
        };
    }

    // Poll everything every 3s if Projects tab is open
    setInterval(async () => {
        if (els.projectsView && !els.projectsView.hidden && state.activeProjectId) {
            try {
                // 1. Update Project Status & Buttons
                const resProj = await fetch('/api/projects');
                const dataProj = await resProj.json();
                const projects = dataProj.projects || [];
                
                // Redraw the sidebar list
                const activeProj = projects.find(x => x.id === state.activeProjectId);
                if (activeProj) {
                    // Check if status changed
                    const badge = document.getElementById('detailStatus');
                    if (badge && badge.textContent.toLowerCase() !== activeProj.status.replace('_', ' ').toLowerCase()) {
                        loadProjects(); // Re-render the whole view to show the Approve button
                    }
                }

                // 2. Update Chat
                const resChat = await fetch('/api/office/history');
                const dataChat = await resChat.json();
                const history = dataChat.history.filter(h => h.project_id === state.activeProjectId);
                if (history.length > 0) {
                    const currentLogs = els.officeChatContainer.children.length;
                    if (history.length !== currentLogs) loadProjectChat(state.activeProjectId);
                }
            } catch(e) { console.error(e); }
        }
    }, 3000);

    // --- 7. Settings Logic ---
    async function loadSettings() {
        try {
            const res = await fetch('/api/settings');
            const data = await res.json();
            if (document.getElementById('setPersona')) document.getElementById('setPersona').value = data.persona_prompt;
            if (document.getElementById('setTemp')) document.getElementById('setTemp').value = data.temperature;
            if (document.getElementById('tempVal')) document.getElementById('tempVal').textContent = data.temperature;
            if (document.getElementById('setRouterKeywords')) document.getElementById('setRouterKeywords').value = data.router_keywords || '{}';
            if (document.getElementById('setUserName')) document.getElementById('setUserName').value = data.user_name;
            if (document.getElementById('setAgentName')) document.getElementById('setAgentName').value = data.agent_name;
            if (document.getElementById('setPlannerPrompt')) document.getElementById('setPlannerPrompt').value = data.planner_prompt || "";
            if (document.getElementById('setReplyPrompt')) document.getElementById('setReplyPrompt').value = data.julian_reply_prompt || "";
        } catch(e) { console.error(e); }
    }

    if (document.getElementById('setTemp')) document.getElementById('setTemp').addEventListener('input', (e) => {
        if (document.getElementById('tempVal')) document.getElementById('tempVal').textContent = e.target.value;
    });

    if (document.getElementById('saveSettingsBtn')) {
        document.getElementById('saveSettingsBtn').addEventListener('click', async (e) => {
            const btn = e.target; btn.textContent = "Saving..."; btn.disabled = true;
            try {
                const payload = {
                    persona_prompt: document.getElementById('setPersona').value,
                    temperature: parseFloat(document.getElementById('setTemp').value),
                    router_keywords: document.getElementById('setRouterKeywords').value,
                    user_name: document.getElementById('setUserName').value,
                    agent_name: document.getElementById('setAgentName').value,
                    planner_prompt: document.getElementById('setPlannerPrompt').value,
                    julian_reply_prompt: document.getElementById('setReplyPrompt').value
                };
                const res = await fetch('/api/settings', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
                if (!res.ok) {
                    const err = await res.text();
                    throw new Error("HTTP " + res.status + ": " + err);
                }
                alert("Settings saved successfully!");
            } catch(e) { alert("Failed to save settings."); }
            finally { btn.textContent = "Save Settings"; btn.disabled = false; }
        });
    }


    
    const remoteModal = document.getElementById('remoteModal');
    const showRemoteBtn = document.getElementById('showRemoteBtn');
    const cancelRemoteBtn = document.getElementById('cancelRemoteBtn');
    const submitRemoteBtn = document.getElementById('submitRemoteBtn');
    const remoteAuthCheck = document.getElementById('remoteAuthCheck');

    if (showRemoteBtn) {
        showRemoteBtn.onclick = () => { if (remoteModal) remoteModal.style.display = 'flex'; };
    }
    if (cancelRemoteBtn) {
        cancelRemoteBtn.onclick = () => { 
            if (remoteModal) remoteModal.style.display = 'none';
            ['remoteTitle', 'remoteBrief', 'remoteUrl'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
            if (remoteAuthCheck) remoteAuthCheck.checked = false;
            if (submitRemoteBtn) { submitRemoteBtn.disabled = true; submitRemoteBtn.style.opacity = '0.5'; }
        };
    }
    if (remoteAuthCheck) {
        remoteAuthCheck.onchange = (e) => {
            if (submitRemoteBtn) {
                submitRemoteBtn.disabled = !e.target.checked;
                submitRemoteBtn.style.opacity = e.target.checked ? '1' : '0.5';
            }
        };
    }
    if (submitRemoteBtn) {
        submitRemoteBtn.onclick = async () => {
            const title = document.getElementById('remoteTitle').value.trim();
            const brief = document.getElementById('remoteBrief').value.trim();
            const target_url = document.getElementById('remoteUrl').value.trim();
            
            if (!title || !brief || !target_url) return alert("Please fill all fields.");
            
            submitRemoteBtn.disabled = true;
            submitRemoteBtn.textContent = "Starting...";
            
            try {
                const res = await fetch('/api/projects/audit-remote', { 
                    method: 'POST', 
                    headers: {'Content-Type': 'application/json'}, 
                    body: JSON.stringify({ title, brief, target_url }) 
                });
                const data = await res.json();
                
                if (data.project_id) {
                    remoteModal.style.display = 'none';
                    ['remoteTitle', 'remoteBrief', 'remoteUrl'].forEach(id => document.getElementById(id).value = '');
                    remoteAuthCheck.checked = false;
                    submitRemoteBtn.disabled = true; submitRemoteBtn.style.opacity = '0.5';
                    
                    state.activeProjectId = data.project_id;
                    els.projForm.style.display = 'none';
                    els.projDetails.style.display = 'block';
                    await loadProjects();
                    loadProjectChat(data.project_id);
                } else {
                    alert("Error: " + (data.detail || "Failed"));
                }
            } catch(e) { alert("Error: " + e.message); }
            finally { submitRemoteBtn.textContent = "Start Remote Audit"; }
        };
    }


    // --- Move to Project ---
    const moveBtn = document.getElementById('moveToProjectBtn');
    
    // Show button if there are messages in chat
    function checkMoveBtn() {
        if (moveBtn && els.messages && els.messages.children.length > 1) {
            moveBtn.style.display = 'inline-block';
        }
    }
    
    if (moveBtn) {
        moveBtn.onclick = async () => {
            const title = prompt("Enter Project Title:", "New App");
            if (!title) return;
            
            moveBtn.disabled = true;
            moveBtn.textContent = "Moving...";
            
            try {
                const res = await fetch('/api/projects/from-chat', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ conversation_id: state.activeConversationId, title })
                });
                const data = await res.json();
                
                if (data.project_id) {
                    // Switch to Projects tab
                    document.querySelector('[data-view="projects"]').click();
                    state.activeProjectId = data.project_id;
                    setTimeout(() => { loadProjects(); loadProjectChat(data.project_id); }, 300);
                }
            } catch(e) { alert("Failed to move project."); }
            finally { moveBtn.disabled = false; moveBtn.textContent = "🚀 Move Chat to Project"; }
        };
    }

    // Call checkMoveBtn after sending message
    const originalSendMessage = window.sendMessage;
    window.sendMessage = async function() {
        await originalSendMessage();
        checkMoveBtn();
    };

    // Init
    loadHistory();
    updateUIState();
});
