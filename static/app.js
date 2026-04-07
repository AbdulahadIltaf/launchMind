document.addEventListener('DOMContentLoaded', () => {
    // Tab switching
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            document.getElementById(btn.dataset.target).classList.add('active');
        });
    });

    // WebSocket logic
    const ws = new WebSocket(`ws://${location.host}/ws`);
    const statusIndicator = document.querySelector('.status-indicator');
    
    ws.onopen = () => {
        statusIndicator.classList.add('active');
    };
    ws.onclose = () => {
        statusIndicator.classList.remove('active');
    };

    const messagesContainer = document.getElementById('messages-container');

    const addMessage = (from, to, text, type = 'info') => {
        const div = document.createElement('div');
        div.className = 'message-card';
        const time = new Date().toLocaleTimeString();
        
        let headerHtml = `<div class="msg-header">
            <span class="msg-agent">${from} → ${to}</span>
            <span class="msg-time">${time}</span>
        </div>`;
        
        // rudimentary sanitization
        const safeText = document.createTextNode(text).textContent;
        div.innerHTML = `${headerHtml}<div>${safeText}</div>`;
        messagesContainer.appendChild(div);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'graph_event') {
            const stateUpdate = msg.data;
            for (const [nodeName, stateData] of Object.entries(stateUpdate)) {
                
                // Add recent messages to the feed
                if (stateData.messages && Array.isArray(stateData.messages)) {
                    stateData.messages.forEach(m => {
                        let text = m.message_type === 'task' ? 'Assigned a task' : 'Returned result/confirmation';
                        if (m.payload && typeof m.payload === 'object') {
                            if (m.payload.directive) text = m.payload.directive;
                            else text = "Generated artifacts. Please check the dashboard tabs.";
                        } else if (typeof m.payload === 'string') {
                            text = m.payload;
                        }
                        // Only add the last message in the update to not flood if state dumps history
                        // Actually langgraph streams partial updates, so `stateData.messages` only contains new messages pushed by this node!
                        addMessage(m.from_agent, m.to_agent, text);
                    });
                }
                
                if (stateData.product_spec) {
                    const specStr = typeof stateData.product_spec === 'string' ? stateData.product_spec : JSON.stringify(stateData.product_spec, null, 2);
                    document.getElementById('product-spec').innerText = "Product Spec Loaded.";
                }

                if (stateData.github_results) {
                    if (stateData.github_results.html_code) {
                        document.getElementById('html-preview-frame').srcdoc = stateData.github_results.html_code;
                    }
                    const ghStatus = document.getElementById('github-status');
                    ghStatus.classList.remove('empty-state');
                    ghStatus.innerText = `Status: ${stateData.github_results.status || 'Generated'}`;
                    
                    const links = document.getElementById('github-links');
                    links.innerHTML = '';
                    if (stateData.github_results.pr_url && stateData.github_results.pr_url !== 'https://github.com/mock') {
                        links.innerHTML += `<a href="${stateData.github_results.pr_url}" target="_blank" class="link-btn">View Pull Request</a>`;
                    }
                    if (stateData.github_results.issue_url && stateData.github_results.issue_url !== 'https://github.com/mock') {
                        links.innerHTML += `<a href="${stateData.github_results.issue_url}" target="_blank" class="link-btn">View GitHub Issue</a>`;
                    }
                }

                if (stateData.marketing_results) {
                    const marketingContainer = document.getElementById('marketing-posts');
                    marketingContainer.classList.remove('empty-state');
                    let html = '';
                    if (stateData.marketing_results.twitter_post) {
                        html += `<h4>Twitter Post</h4><pre>${stateData.marketing_results.twitter_post}</pre>`;
                    }
                    if (stateData.marketing_results.linkedin_post) {
                        html += `<h4>LinkedIn Post</h4><pre>${stateData.marketing_results.linkedin_post}</pre>`;
                    }
                    marketingContainer.innerHTML = html || `<pre>${JSON.stringify(stateData.marketing_results, null, 2)}</pre>`;
                }

                if (stateData.qa_report) {
                    const qaContainer = document.getElementById('qa-report-content');
                    qaContainer.classList.remove('empty-state');
                    qaContainer.innerHTML = `<pre>${JSON.stringify(stateData.qa_report, null, 2)}</pre>`;
                }
            }
        } else if (msg.type === 'graph_complete') {
            addMessage('System', 'All', '🎉 Workflow completed successfully!');
        } else if (msg.type === 'graph_error') {
            addMessage('System', 'All', `Error: ${msg.data}`);
        }
    };

    // Start button
    document.getElementById('start-btn').addEventListener('click', async () => {
        const idea = document.getElementById('idea-input').value;
        messagesContainer.innerHTML = ''; 
        
        document.getElementById('html-preview-frame').srcdoc = '';
        document.getElementById('github-status').innerText = 'Generating...';
        document.getElementById('github-status').classList.add('empty-state');
        document.getElementById('github-links').innerHTML = '';
        document.getElementById('product-spec').innerText = '';
        document.getElementById('marketing-posts').innerHTML = 'Generating marketing strategy...';
        document.getElementById('marketing-posts').classList.add('empty-state');
        document.getElementById('qa-report-content').innerHTML = 'Waiting for generation...';
        document.getElementById('qa-report-content').classList.add('empty-state');
        
        addMessage('System', 'LaunchMind', `🚀 Initializing startup creation for: "${idea}"`);
        
        try {
            const resp = await fetch('/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ idea })
            });
            if (!resp.ok) {
                addMessage('System', 'Error', 'Failed to start backend workflow.');
            }
        } catch (e) {
            addMessage('System', 'Error', 'Failed to connect to backend: ' + e.message);
        }
    });
});
