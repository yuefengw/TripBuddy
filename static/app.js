class TripBuddyApp {
    constructor() {
        this.apiBaseUrl = `${window.location.origin}/api`;
        this.currentMode = "standard_search";
        this.sessionId = this.generateSessionId();
        this.isStreaming = false;
        this.currentStreamRouteType = null;
        this.currentChatHistory = [];
        this.chatHistories = this.loadChatHistories();
        this.isCurrentChatFromHistory = false;
        this.hasInteracted = this.chatHistories.length > 0;

        this.initMarkdown();
        this.initializeElements();
        this.bindEvents();
        this.renderChatHistory();
        this.refreshEmptyState();
        this.updateModeLabel();
        this.autoResizeInput();
    }

    initMarkdown() {
        const tryInit = () => {
            if (typeof marked === "undefined") {
                setTimeout(tryInit, 120);
                return;
            }

            marked.setOptions({
                breaks: true,
                gfm: true,
                headerIds: false,
                mangle: false
            });
        };

        tryInit();
    }

    initializeElements() {
        this.mainPanel = document.querySelector(".main-panel");
        this.contentPanel = document.querySelector(".content-panel");
        this.newChatBtn = document.getElementById("newChatBtn");
        this.chatHistoryList = document.getElementById("chatHistoryList");
        this.topbar = document.getElementById("topbar");
        this.topbarCopy = document.getElementById("topbarCopy");
        this.heroPanel = document.getElementById("heroPanel");
        this.quickPrompts = document.getElementById("quickPrompts");
        this.chatStage = document.querySelector(".chat-stage");
        this.chatMessages = document.getElementById("chatMessages");
        this.composerShell = document.querySelector(".composer-shell");
        this.messageInput = document.getElementById("messageInput");
        this.sendButton = document.getElementById("sendButton");
        this.toolsBtn = document.getElementById("toolsBtn");
        this.toolsMenu = document.getElementById("toolsMenu");
        this.uploadFileItem = document.getElementById("uploadFileItem");
        this.fileInput = document.getElementById("fileInput");
        this.modeSelectorBtn = document.getElementById("modeSelectorBtn");
        this.modeDropdown = document.getElementById("modeDropdown");
        this.currentModeText = document.getElementById("currentModeText");
        this.loadingOverlay = document.getElementById("loadingOverlay");
    }

    bindEvents() {
        this.newChatBtn?.addEventListener("click", () => this.newChat());
        this.sendButton?.addEventListener("click", () => this.sendMessage());

        this.messageInput?.addEventListener("input", () => this.autoResizeInput());
        this.messageInput?.addEventListener("keydown", (event) => {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                this.sendMessage();
            }
        });

        this.quickPrompts?.addEventListener("click", (event) => {
            const card = event.target.closest(".prompt-card");
            if (!card) return;
            const prompt = card.dataset.prompt || "";
            this.messageInput.value = prompt;
            this.autoResizeInput();
            this.messageInput.focus();
        });

        this.toolsBtn?.addEventListener("click", (event) => {
            event.stopPropagation();
            this.toggleToolsMenu();
        });

        this.uploadFileItem?.addEventListener("click", () => {
            this.closeMenus();
            this.fileInput?.click();
        });

        this.fileInput?.addEventListener("change", (event) => this.handleFileSelect(event));

        this.modeSelectorBtn?.addEventListener("click", (event) => {
            event.stopPropagation();
            this.toggleModeMenu();
        });

        this.modeDropdown?.querySelectorAll("[data-mode]").forEach((item) => {
            item.addEventListener("click", () => {
                this.selectMode(item.dataset.mode);
                this.closeMenus();
            });
        });

        document.addEventListener("click", (event) => {
            if (!event.target.closest(".menu-wrap") && !event.target.closest(".mode-wrap")) {
                this.closeMenus();
            }
        });

        window.addEventListener("resize", () => this.syncLayout());
    }

    generateSessionId() {
        return `trip-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    }

    toggleToolsMenu() {
        const wrapper = this.toolsBtn?.closest(".menu-wrap");
        wrapper?.classList.toggle("active");
        this.modeSelectorBtn?.closest(".mode-wrap")?.classList.remove("active");
    }

    toggleModeMenu() {
        const wrapper = this.modeSelectorBtn?.closest(".mode-wrap");
        wrapper?.classList.toggle("active");
        this.toolsBtn?.closest(".menu-wrap")?.classList.remove("active");
    }

    closeMenus() {
        this.toolsBtn?.closest(".menu-wrap")?.classList.remove("active");
        this.modeSelectorBtn?.closest(".mode-wrap")?.classList.remove("active");
    }

    selectMode(mode) {
        this.currentMode = mode === "deep_search" ? "deep_search" : "standard_search";
        this.updateModeLabel();
        this.modeDropdown?.querySelectorAll("[data-mode]").forEach((item) => {
            item.classList.toggle("is-active", item.dataset.mode === this.currentMode);
        });
    }

    updateModeLabel() {
        if (!this.currentModeText) return;
        this.currentModeText.textContent = this.currentMode === "deep_search" ? "深度搜索" : "标准搜索";
    }

    autoResizeInput() {
        if (!this.messageInput) return;
        this.messageInput.style.height = "auto";
        this.messageInput.style.height = `${Math.min(this.messageInput.scrollHeight, 180)}px`;
    }

    refreshEmptyState() {
        const shouldShowIntro = this.currentChatHistory.length === 0;
        this.mainPanel?.classList.toggle("is-empty", shouldShowIntro);
        this.heroPanel?.classList.toggle("is-hidden", !shouldShowIntro);
        this.topbarCopy?.classList.toggle("is-hidden", !shouldShowIntro);
        this.topbar?.classList.toggle("is-compact", !shouldShowIntro);
        requestAnimationFrame(() => this.syncLayout());
    }

    syncLayout() {
        if (!this.mainPanel || !this.heroPanel || !this.contentPanel) return;

        const isEmpty = this.currentChatHistory.length === 0;
        if (!isEmpty) {
            this.heroPanel.style.maxHeight = "";
            this.heroPanel.style.overflowY = "";
            return;
        }

        const mainPanelHeight = this.mainPanel.clientHeight;
        const composerHeight = this.composerShell?.offsetHeight || 0;
        const mainStyles = window.getComputedStyle(this.mainPanel);
        const mainGap = parseFloat(mainStyles.gap || "0") || 0;
        const availableContentHeight = Math.max(0, mainPanelHeight - composerHeight - mainGap);
        const topbarHeight = this.topbar?.offsetHeight || 0;
        const contentGap = parseFloat(window.getComputedStyle(this.contentPanel).gap || "0") || 0;
        const reservedSpace = 24;
        const heroMaxHeight = Math.max(180, availableContentHeight - topbarHeight - contentGap - reservedSpace);

        this.heroPanel.style.maxHeight = `${Math.floor(heroMaxHeight)}px`;
        this.heroPanel.style.overflowY = "auto";
        this.contentPanel.scrollTop = 0;
    }

    renderChatHistory() {
        if (!this.chatHistoryList) return;
        this.chatHistoryList.innerHTML = "";

        this.chatHistories.forEach((history) => {
            const item = document.createElement("div");
            item.className = "history-item";
            item.classList.toggle("is-active", history.id === this.sessionId);
            item.innerHTML = `
                <div class="history-item-content">
                    <span class="history-item-title">${this.escapeHtml(history.title)}</span>
                </div>
                <button class="history-item-delete" title="删除对话">
                    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                </button>
            `;

            item.addEventListener("click", (event) => {
                if (event.target.closest(".history-item-delete")) return;
                this.loadChatHistory(history.id);
            });

            item.querySelector(".history-item-delete")?.addEventListener("click", (event) => {
                event.stopPropagation();
                this.deleteChatHistory(history.id);
            });

            this.chatHistoryList.appendChild(item);
        });
    }

    loadChatHistories() {
        try {
            return JSON.parse(localStorage.getItem("tripbuddyChatHistories") || "[]");
        } catch (error) {
            console.error("load histories failed", error);
            return [];
        }
    }

    saveChatHistories() {
        localStorage.setItem("tripbuddyChatHistories", JSON.stringify(this.chatHistories));
    }

    buildHistoryTitle(content) {
        const plain = content.replace(/\s+/g, " ").trim();
        return plain.length > 24 ? `${plain.slice(0, 24)}...` : plain;
    }

    persistCurrentChat() {
        if (this.currentChatHistory.length === 0) return;

        const firstUserMessage = this.currentChatHistory.find((item) => item.type === "user");
        const title = this.buildHistoryTitle(firstUserMessage?.content || "新旅行对话");
        const existingIndex = this.chatHistories.findIndex((item) => item.id === this.sessionId);
        const payload = {
            id: this.sessionId,
            title,
            messages: [...this.currentChatHistory],
            updatedAt: new Date().toISOString()
        };

        if (existingIndex >= 0) {
            this.chatHistories[existingIndex] = {
                ...this.chatHistories[existingIndex],
                ...payload
            };
        } else {
            this.chatHistories.unshift({
                ...payload,
                createdAt: new Date().toISOString()
            });
        }

        this.chatHistories = this.chatHistories.slice(0, 50);
        this.saveChatHistories();
        this.renderChatHistory();
    }

    async loadChatHistory(historyId) {
        const localHistory = this.chatHistories.find((item) => item.id === historyId);
        if (!localHistory) return;

        if (this.currentChatHistory.length > 0 && this.sessionId !== historyId) {
            this.persistCurrentChat();
        }

        this.sessionId = historyId;
        this.isCurrentChatFromHistory = true;
        this.hasInteracted = true;
        this.currentChatHistory = [];
        this.chatMessages.innerHTML = "";
        this.renderChatHistory();

        try {
            const response = await fetch(`${this.apiBaseUrl}/chat/session/${historyId}`);
            if (response.ok) {
                const data = await response.json();
                const history = data.history || [];
                if (history.length > 0) {
                    history.forEach((item) => {
                        this.addMessage(item.role === "user" ? "user" : "assistant", item.content, {
                            save: true,
                            timestamp: item.timestamp
                        });
                    });
                    this.refreshEmptyState();
                    this.scrollToBottom(true);
                    return;
                }
            }
        } catch (error) {
            console.warn("load backend session failed", error);
        }

        (localHistory.messages || []).forEach((item) => {
            this.addMessage(item.type, item.content, {
                save: true,
                timestamp: item.timestamp,
                route: item.route || null
            });
        });
        this.refreshEmptyState();
        this.scrollToBottom(true);
    }

    deleteChatHistory(historyId) {
        this.chatHistories = this.chatHistories.filter((item) => item.id !== historyId);
        this.saveChatHistories();
        this.renderChatHistory();

        if (this.sessionId === historyId) {
            this.newChat(false);
        }
    }

    newChat(shouldPersist = true) {
        if (this.isStreaming) {
            this.showNotification("请等当前回复完成后再新建对话。", "warning");
            return;
        }

        if (shouldPersist) {
            this.persistCurrentChat();
        }

        this.sessionId = this.generateSessionId();
        this.currentChatHistory = [];
        this.isCurrentChatFromHistory = false;
        this.hasInteracted = true;
        this.chatMessages.innerHTML = "";
        this.messageInput.value = "";
        this.autoResizeInput();
        this.refreshEmptyState();
        this.renderChatHistory();
    }

    async sendMessage() {
        const question = this.messageInput.value.trim();
        if (!question) return;
        if (this.isStreaming) {
            if (this.currentStreamRouteType === "multi_agent") {
                await this.sendHumanInterrupt(question);
            }
            return;
        }

        this.closeMenus();
        this.hasInteracted = true;
        this.refreshEmptyState();
        this.addMessage("user", question);
        this.messageInput.value = "";
        this.autoResizeInput();

        const assistantMessage = this.addMessage("assistant", "", {
            save: true,
            route: null,
            streaming: true,
            pending: true
        });
        this.persistCurrentChat();

        this.isStreaming = true;
        this.currentStreamRouteType = null;
        this.updateSendState();

        try {
            await this.sendStreamRequest(question, assistantMessage);
            this.persistCurrentChat();
        } catch (error) {
            console.error(error);
            this.updateAssistantMessage(
                assistantMessage,
                `抱歉，这次旅行请求处理失败了。\n\n${error.message}`,
                { route: null, done: true }
            );
            this.showNotification("请求失败，请稍后再试。", "error");
        } finally {
            this.isStreaming = false;
            this.currentStreamRouteType = null;
            this.updateSendState();
        }
    }

    updateSendState() {
        if (!this.sendButton) return;
        this.sendButton.disabled = this.isStreaming && this.currentStreamRouteType !== "multi_agent";
    }

    async sendHumanInterrupt(question) {
        this.closeMenus();
        this.hasInteracted = true;
        this.refreshEmptyState();
        this.addMessage("user", question);
        this.messageInput.value = "";
        this.autoResizeInput();
        this.persistCurrentChat();

        try {
            const response = await fetch(`${this.apiBaseUrl}/chat/interrupt`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    sessionId: this.sessionId,
                    message: question
                })
            });
            const payload = await response.json();
            if (!response.ok || payload.status !== "success" || !payload.data?.accepted) {
                throw new Error(payload.message || "追加条件失败");
            }
            this.showNotification("新条件已交给主 Agent，正在重分解任务。", "info");
        } catch (error) {
            this.showNotification(`追加条件失败：${error.message}`, "error");
        }
    }

    async sendStreamRequest(question, assistantMessage) {
        const response = await fetch(`${this.apiBaseUrl}/chat_stream`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                Id: this.sessionId,
                Question: question,
                conversationMode: this.currentMode
            })
        });

        if (!response.ok || !response.body) {
            throw new Error("流式连接失败");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        let currentEvent = "message";
        let fullResponse = "";
        let routeMeta = null;

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split("\n");
            buffer = parts.pop() || "";

            for (const part of parts) {
                const line = part.trimEnd();
                if (line.startsWith("event:")) {
                    currentEvent = line.slice(6).trim();
                    continue;
                }

                if (!line.startsWith("data:")) {
                    continue;
                }

                const raw = line.slice(5).trim();
                if (!raw) continue;

                const message = JSON.parse(raw);
                if (currentEvent !== "message") continue;

                if (message.type === "route") {
                    routeMeta = message.data;
                    this.currentStreamRouteType = routeMeta?.route_type || null;
                    this.updateSendState();
                    this.updateAssistantMessage(assistantMessage, fullResponse, {
                        route: routeMeta,
                        done: false
                    });
                }

                if (message.type === "status") {
                    this.updateAssistantMessage(assistantMessage, fullResponse, {
                        route: routeMeta,
                        done: false,
                        pending: !fullResponse,
                        statusText: message.data || ""
                    });
                }

                if (message.type === "content") {
                    fullResponse += message.data || "";
                    this.updateAssistantMessage(assistantMessage, fullResponse, {
                        route: routeMeta,
                        done: false
                    });
                }

                if (message.type === "done") {
                    const finalData = message.data || {};
                    if (finalData.answer) {
                        if (!fullResponse || finalData.answer.startsWith(fullResponse)) {
                            fullResponse = finalData.answer;
                        } else if (
                            !fullResponse.startsWith(finalData.answer) &&
                            fullResponse.length < finalData.answer.length * 0.5
                        ) {
                            fullResponse = finalData.answer;
                        }
                    }
                    routeMeta = finalData.route || routeMeta;
                    this.updateAssistantMessage(assistantMessage, fullResponse, {
                        route: routeMeta,
                        done: true
                    });
                    this.currentStreamRouteType = null;
                }

                if (message.type === "error") {
                    this.currentStreamRouteType = null;
                    throw new Error(message.data || "流式请求失败");
                }
            }
        }
    }

    async handleFileSelect(event) {
        const file = event.target.files?.[0];
        if (!file) return;

        this.showOverlay(true, "上传旅行资料中", `正在索引 ${file.name}`);

        try {
            const formData = new FormData();
            formData.append("file", file);

            const response = await fetch(`${this.apiBaseUrl}/upload`, {
                method: "POST",
                body: formData
            });
            const payload = await response.json();

            if (!response.ok || payload.code !== 200) {
                throw new Error(payload.detail || payload.message || "上传失败");
            }

            this.showNotification(`已上传并索引：${file.name}`, "success");
        } catch (error) {
            this.showNotification(`上传失败：${error.message}`, "error");
        } finally {
            this.showOverlay(false);
            event.target.value = "";
        }
    }

    addMessage(type, content, options = {}) {
        const message = document.createElement("div");
        message.className = `message ${type === "user" ? "user" : "assistant"}`;

        const shell = document.createElement("div");
        shell.className = "message-shell";

        const metaRow = document.createElement("div");
        metaRow.className = "message-meta-row";

        const contentEl = document.createElement("div");
        contentEl.className = "message-content";
        if (options.streaming) {
            contentEl.classList.add("streaming");
        }

        const timeEl = document.createElement("div");
        timeEl.className = "message-time";
        timeEl.textContent = this.formatTime(options.timestamp || new Date().toISOString());

        shell.appendChild(metaRow);
        shell.appendChild(contentEl);
        shell.appendChild(timeEl);
        message.appendChild(shell);
        this.chatMessages.appendChild(message);

        if (type === "user") {
            contentEl.textContent = content;
        } else {
            this.updateAssistantMessage(message, content, {
                route: options.route || null,
                done: !options.streaming,
                pending: options.pending === true
            });
        }

        if (options.save !== false) {
            this.currentChatHistory.push({
                type,
                content,
                timestamp: options.timestamp || new Date().toISOString(),
                route: options.route || null
            });
            message.dataset.historyIndex = String(this.currentChatHistory.length - 1);
        }

        this.refreshEmptyState();
        this.scrollToBottom(true);
        return message;
    }

    updateAssistantMessage(messageElement, content, options = {}) {
        const shell = messageElement.querySelector(".message-shell");
        const metaRow = shell.querySelector(".message-meta-row");
        const contentEl = shell.querySelector(".message-content");
        const normalizedContent = typeof content === "string" ? content : "";
        const shouldShowPending = options.pending === true || (options.done === false && !normalizedContent.trim());

        metaRow.innerHTML = "";

        if (options.route?.route_type) {
            metaRow.appendChild(this.buildPill("route-pill", this.formatRouteType(options.route.route_type)));
        }

        if (options.route?.selected_workflow) {
            metaRow.appendChild(this.buildPill("meta-pill", options.route.selected_workflow));
        }

        if (options.route?.intent) {
            metaRow.appendChild(this.buildPill("meta-pill", options.route.intent));
        }

        contentEl.classList.remove("streaming", "is-pending");

        if (shouldShowPending) {
            contentEl.classList.add("is-pending");
            contentEl.innerHTML = this.renderPendingState(options.route, options.statusText || "");
        } else if (options.done === false) {
            contentEl.classList.add("streaming");
            contentEl.textContent = normalizedContent;
        } else {
            contentEl.innerHTML = this.renderMarkdown(normalizedContent);
            this.highlightCodeBlocks(contentEl);
        }

        const historyIndex = Number(messageElement.dataset.historyIndex);
        if (Number.isInteger(historyIndex) && historyIndex >= 0 && this.currentChatHistory[historyIndex]) {
            this.currentChatHistory[historyIndex].content = normalizedContent;
            this.currentChatHistory[historyIndex].route = options.route || null;
        }

        this.scrollToBottom(options.done === false || this.isStreaming);
    }

    renderPendingState(route, statusText = "") {
        const title = route?.route_type
            ? `已进入${this.formatRouteType(route.route_type)}`
            : "正在分析你的旅行问题";
        const subtitle = statusText || (
            route?.selected_workflow
                ? `准备执行 ${route.selected_workflow}`
                : "正在识别意图、读取记忆并组织回答"
        );

        return `
            <div class="assistant-pending">
                <div class="assistant-pending-title">${this.escapeHtml(title)}</div>
                <div class="assistant-pending-subtitle">${this.escapeHtml(subtitle)}</div>
                <div class="assistant-pending-dots" aria-hidden="true">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;
    }

    buildPill(className, text) {
        const el = document.createElement("span");
        el.className = className;
        el.textContent = text;
        return el;
    }

    renderMarkdown(content) {
        if (!content) return "";
        if (typeof marked === "undefined") return this.escapeHtml(content);
        try {
            return marked.parse(content);
        } catch (error) {
            console.error("markdown render failed", error);
            return this.escapeHtml(content);
        }
    }

    highlightCodeBlocks(container) {
        if (typeof hljs === "undefined") return;
        container.querySelectorAll("pre code").forEach((block) => {
            if (!block.classList.contains("hljs")) {
                hljs.highlightElement(block);
            }
        });
    }

    formatRouteType(routeType) {
        const mapping = {
            knowledge: "知识问答",
            workflow: "固定 Workflow",
            multi_agent: "Multi-Agent",
            plan_execute: "Plan-and-Execute"
        };
        return mapping[routeType] || routeType;
    }

    formatTime(timestamp) {
        const date = new Date(timestamp);
        return Number.isNaN(date.getTime())
            ? ""
            : date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    }

    isNearBottom() {
        if (!this.chatMessages) return true;
        const distance = this.chatMessages.scrollHeight - this.chatMessages.scrollTop - this.chatMessages.clientHeight;
        return distance < 96;
    }

    scrollToBottom(force = false) {
        if (!this.chatMessages) return;
        if (!force && !this.isNearBottom()) return;

        const container = this.chatMessages;
        const lastMessage = container.lastElementChild;
        if (!lastMessage) return;

        const applyScroll = () => {
            lastMessage.scrollIntoView({ behavior: 'instant', block: 'end' });
        };

        applyScroll();
        requestAnimationFrame(applyScroll);
        setTimeout(applyScroll, 0);
    }

    showOverlay(
        show,
        title = "TripBuddy 正在处理",
        subtitle = "正在分析意图、调用工作流或组建多智能体协作，请稍候"
    ) {
        if (!this.loadingOverlay) return;

        const titleEl = this.loadingOverlay.querySelector(".overlay-title");
        const subtitleEl = this.loadingOverlay.querySelector(".overlay-subtitle");
        if (titleEl) titleEl.textContent = title;
        if (subtitleEl) subtitleEl.textContent = subtitle;
        this.loadingOverlay.classList.toggle("is-visible", show);
    }

    showNotification(message, type = "info") {
        const node = document.createElement("div");
        node.className = `notification ${type}`;
        node.textContent = message;
        document.body.appendChild(node);

        setTimeout(() => {
            node.style.opacity = "0";
            node.style.transform = "translateY(-6px)";
        }, 2400);

        setTimeout(() => {
            node.remove();
        }, 2800);
    }

    escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    new TripBuddyApp();
});
