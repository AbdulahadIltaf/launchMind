document.addEventListener('DOMContentLoaded', () => {
    // ===== STATE MANAGEMENT =====
    const state = {
        isRunning: false,
        completedStages: new Set(),
        currentStage: null
    };

    // ===== DOM ELEMENTS =====
    const elements = {
        startBtn: document.getElementById('start-btn'),
        ideaInput: document.getElementById('idea-input'),
        messagesContainer: document.getElementById('messages-container'),
        statusText: document.getElementById('status-text'),
        statusDot: document.querySelector('.status-dot'),
        connectionIndicator: document.querySelector('.connection-indicator'),
        
        // Tab controls
        tabBtns: document.querySelectorAll('.tab-btn'),
        tabContents: document.querySelectorAll('.tab-content'),
        
        // Content areas
        previewFrame: document.getElementById('html-preview-frame'),
        githubStatus: document.getElementById('github-status'),
        githubLinks: document.getElementById('github-links'),
        productSpec: document.getElementById('product-spec'),
        marketingPosts: document.getElementById('marketing-posts'),
        qaReport: document.getElementById('qa-report-content'),
        workflowStatus: document.getElementById('workflow-status')
    };

    // ===== TAB SWITCHING =====
    elements.tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            elements.tabBtns.forEach(b => b.classList.remove('active'));
            elements.tabContents.forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            document.getElementById(btn.dataset.target).classList.add('active');
        });
    });

    // ===== WEBSOCKET CONNECTION =====
    let ws;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;
    
    function connectWebSocket() {
        ws = new WebSocket(`ws://${location.host}/ws`);
        
        ws.onopen = () => {
            console.log('Connected to server');
            reconnectAttempts = 0;
            updateConnectionStatus(true);
            addSystemMessage('Connected to LaunchMind server', 'success');
        };
        
        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            updateConnectionStatus(false);
        };
        
        ws.onclose = () => {
            console.log('Disconnected from server');
            updateConnectionStatus(false);
            
            if (reconnectAttempts < maxReconnectAttempts) {
                reconnectAttempts++;
                setTimeout(connectWebSocket, 2000 * reconnectAttempts);
            }
        };
        
        ws.onmessage = handleWebSocketMessage;
    }
    
    function updateConnectionStatus(connected) {
        elements.statusDot.classList.toggle('active', connected);
        elements.connectionIndicator.classList.toggle('connected', connected);
        elements.statusText.textContent = connected ? 'Connected' : 'Offline';
    }
    
    connectWebSocket();

    // ===== MESSAGE HANDLING =====
    function addMessage(from, to, text, type = 'info') {
        const div = document.createElement('div');
        div.className = 'message-card';
        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        
        let headerHtml = `<div class="msg-header">
            <span class="msg-agent">${from} → ${to}</span>
            <span class="msg-time">${time}</span>
        </div>`;
        
        const safeText = document.createTextNode(text).textContent;
        div.innerHTML = `${headerHtml}<div>${safeText}</div>`;
        elements.messagesContainer.appendChild(div);
        elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
    }
    
    function addSystemMessage(text, type = 'info') {
        addMessage('System', 'LaunchMind', text, type);
    }

    function updateWorkflowTimeline(stage) {
        const stages = ['CEO Planning', 'Product Design', 'Engineering', 'Marketing', 'QA & Review'];
        const workflowItems = document.querySelectorAll('.workflow-item');
        
        workflowItems.forEach((item, index) => {
            const dot = item.querySelector('.workflow-dot');
            if (index < stages.indexOf(stage)) {
                dot.style.background = 'var(--success)';
                dot.style.borderColor = 'var(--success)';
            } else if (stages[index] === stage) {
                dot.style.background = 'var(--accent-primary)';
                dot.style.borderColor = 'var(--accent-primary)';
            }
        });
    }

    function handleWebSocketMessage(event) {
        try {
            const msg = JSON.parse(event.data);
            
            if (msg.type === 'graph_event') {
                const stateUpdate = msg.data;
                
                for (const [nodeName, stateData] of Object.entries(stateUpdate)) {
                    // Handle messages from agents
                    if (stateData.messages && Array.isArray(stateData.messages)) {
                        stateData.messages.forEach(m => {
                            let text = m.message_type === 'task' ? 'Assigned a task' : 'Processed result';
                            
                            if (m.payload && typeof m.payload === 'object') {
                                if (m.payload.directive) {
                                    text = m.payload.directive;
                                } else {
                                    text = '✓ Generated artifacts. Check the dashboard tabs.';
                                }
                            } else if (typeof m.payload === 'string' && m.payload.length > 0) {
                                text = m.payload.substring(0, 100);
                            }
                            
                            addMessage(m.from_agent || 'Agent', m.to_agent || 'Team', text);
                        });
                    }
                    
                    // Update workflow stage based on node
                    if (['ceo_node', 'product_node', 'engineer_node', 'marketing_node', 'qa_node'].includes(nodeName)) {
                        const stageMap = {
                            'ceo_node': 'CEO Planning',
                            'product_node': 'Product Design',
                            'engineer_node': 'Engineering',
                            'marketing_node': 'Marketing',
                            'qa_node': 'QA & Review'
                        };
                        if (stageMap[nodeName]) {
                            updateWorkflowTimeline(stageMap[nodeName]);
                        }
                    }
                    
                    // Handle product spec
                    if (stateData.product_spec) {
                        const specStr = typeof stateData.product_spec === 'string' 
                            ? stateData.product_spec 
                            : JSON.stringify(stateData.product_spec, null, 2);
                        elements.productSpec.innerText = specStr;
                    }
                    
                    // Handle GitHub results (engineer output)
                    if (stateData.github_results) {
                        if (stateData.github_results.html_code) {
                            elements.previewFrame.srcdoc = stateData.github_results.html_code;
                        }
                        
                        elements.githubStatus.classList.remove('empty-state');
                        const status = stateData.github_results.status || 'Generated Successfully';
                        elements.githubStatus.innerHTML = `<strong>✓ ${status}</strong>`;
                        
                        elements.githubLinks.innerHTML = '';
                        if (stateData.github_results.pr_url && stateData.github_results.pr_url !== 'https://github.com/mock') {
                            elements.githubLinks.innerHTML += `
                                <a href="${stateData.github_results.pr_url}" target="_blank" class="link-btn">
                                    📤 View Pull Request
                                </a>
                            `;
                        }
                        if (stateData.github_results.issue_url && stateData.github_results.issue_url !== 'https://github.com/mock') {
                            elements.githubLinks.innerHTML += `
                                <a href="${stateData.github_results.issue_url}" target="_blank" class="link-btn">
                                    📋 View GitHub Issue
                                </a>
                            `;
                        }
                        
                        state.completedStages.add('Engineering');
                    }
                    
                    // Handle marketing results
                    if (stateData.marketing_results) {
                        elements.marketingPosts.classList.remove('empty-state');
                        let html = '';
                        
                        if (stateData.marketing_results.twitter_post) {
                            html += `<div style="margin-bottom:16px;">
                                <h4 style="color:var(--accent-primary);margin-bottom:8px;">🐦 Twitter Post</h4>
                                <pre style="background:rgba(0,0,0,0.3);padding:10px;border-radius:6px;font-size:12px;">${escapeHtml(stateData.marketing_results.twitter_post)}</pre>
                            </div>`;
                        }
                        if (stateData.marketing_results.linkedin_post) {
                            html += `<div style="margin-bottom:16px;">
                                <h4 style="color:var(--accent-primary);margin-bottom:8px;">💼 LinkedIn Post</h4>
                                <pre style="background:rgba(0,0,0,0.3);padding:10px;border-radius:6px;font-size:12px;">${escapeHtml(stateData.marketing_results.linkedin_post)}</pre>
                            </div>`;
                        }
                        
                        elements.marketingPosts.innerHTML = html || formatJSON(stateData.marketing_results);
                        state.completedStages.add('Marketing');
                    }
                    
                    // Handle QA report
                    if (stateData.qa_report) {
                        elements.qaReport.classList.remove('empty-state');
                        elements.qaReport.innerHTML = formatJSON(stateData.qa_report);
                        state.completedStages.add('QA');
                    }
                }
            } else if (msg.type === 'graph_complete') {
                addSystemMessage('🎉 Workflow completed successfully!', 'success');
                state.isRunning = false;
                updateButtonState();
            } else if (msg.type === 'graph_error') {
                addSystemMessage(`❌ Error: ${msg.data}`, 'error');
                state.isRunning = false;
                updateButtonState();
            }
        } catch (error) {
            console.error('Error parsing message:', error);
        }
    }

    // ===== UTILITY FUNCTIONS =====
    function escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }

    function formatJSON(obj) {
        const str = typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2);
        return `<pre style="background:rgba(0,0,0,0.3);padding:10px;border-radius:6px;font-size:12px;overflow-x:auto;">${escapeHtml(str)}</pre>`;
    }

    function resetUI() {
        elements.previewFrame.srcdoc = '';
        elements.githubStatus.innerHTML = '<p class="empty-state">⏳ Awaiting code generation...</p>';
        elements.githubStatus.classList.add('empty-state');
        elements.githubLinks.innerHTML = '';
        elements.productSpec.innerText = 'Loading...';
        elements.marketingPosts.innerHTML = '<p class="empty-state">⏳ Awaiting marketing strategy...</p>';
        elements.marketingPosts.classList.add('empty-state');
        elements.qaReport.innerHTML = '<p class="empty-state">⏳ Awaiting QA validation...</p>';
        elements.qaReport.classList.add('empty-state');
        elements.messagesContainer.innerHTML = '';
        state.completedStages.clear();
    }

    function updateButtonState() {
        elements.startBtn.disabled = state.isRunning;
        elements.startBtn.style.opacity = state.isRunning ? '0.6' : '1';
        elements.startBtn.style.cursor = state.isRunning ? 'not-allowed' : 'pointer';
    }

    // ===== START BUTTON HANDLER =====
    elements.startBtn.addEventListener('click', async () => {
        const idea = elements.ideaInput.value.trim();
        
        if (!idea) {
            addSystemMessage('⚠️ Please enter a startup idea!', 'warning');
            return;
        }
        
        if (state.isRunning) {
            return;
        }
        
        state.isRunning = true;
        updateButtonState();
        resetUI();
        
        addSystemMessage(`🚀 Initializing startup creation for: "${idea}"`, 'info');
        
        try {
            const resp = await fetch('/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ idea })
            });
            
            if (!resp.ok) {
                addSystemMessage('❌ Failed to start backend workflow.', 'error');
                state.isRunning = false;
                updateButtonState();
            }
        } catch (e) {
            addSystemMessage(`❌ Failed to connect to backend: ${e.message}`, 'error');
            state.isRunning = false;
            updateButtonState();
        }
    });

    // Initial UI setup
    updateButtonState();
    updateConnectionStatus(false);
});
