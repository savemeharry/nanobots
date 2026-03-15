"""Context builder for assembling agent prompts."""

from pathlib import Path
from typing import Any

from nanobot.agent.memory import MemoryStore
from nanobot.agent.skills import SkillsLoader


class ContextBuilder:
    """
    Builds the context (system prompt + messages) for the agent.
    
    Assembles bootstrap files, memory, skills, and conversation history
    into a coherent prompt for the LLM.
    """
    
    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md", "IDENTITY.md"]
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory = MemoryStore(workspace)
        self.skills = SkillsLoader(workspace)
    
    def build_system_prompt(
        self,
        skill_names: list[str] | None = None,
        agent_role: str = "worker",
        shared_context: list[dict] | None = None
    ) -> str:
        """
        Build the system prompt from bootstrap files, memory, and skills.

        Args:
            skill_names: Optional list of skills to include.
            agent_role: "chat" for Telegram consultant, "worker" for TMA executor.
            shared_context: Recent actions from the other agent.

        Returns:
            Complete system prompt.
        """
        parts = []

        # Core identity based on role
        if agent_role == "chat":
            parts.append(self._get_chat_agent_identity())
        else:
            parts.append(self._get_worker_agent_identity())

        # Add shared context if available
        if shared_context:
            context_text = self._format_shared_context(shared_context, agent_role)
            if context_text:
                parts.append(context_text)
        
        # Bootstrap files
        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)
        
        # Memory context
        memory = self.memory.get_memory_context()
        if memory:
            parts.append(f"# Memory\n\n{memory}")
        
        # Skills - progressive loading
        # 1. Always-loaded skills: include full content
        always_skills = self.skills.get_always_skills()
        if always_skills:
            always_content = self.skills.load_skills_for_context(always_skills)
            if always_content:
                parts.append(f"# Active Skills\n\n{always_content}")
        
        # 2. Available skills: only show summary (agent uses read_file to load)
        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(f"""# Skills

The following skills extend your capabilities. To use a skill, read its SKILL.md file using the read_file tool.
Skills with available="false" need dependencies installed first - you can try installing them with apt/brew.

{skills_summary}""")
        
        return "\n\n---\n\n".join(parts)
    
    def _get_chat_agent_identity(self) -> str:
        """Get identity for Chat Agent (Telegram) - consultant role."""
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")

        return f"""# nanobot Chat Agent - Консультант

Ты - **Chat Agent** (консультант) в системе nanobot. Ты общаешься с пользователем в Telegram.

**Текущее время:** {now}

---

## ТВОЯ РОЛЬ

Ты **НЕ** выполняешь задачи напрямую. Ты:
1. **Консультируешь** - отвечаешь на вопросы, объясняешь концепции
2. **Планируешь** - помогаешь спланировать задачи
3. **Делегируешь** - направляешь пользователя в TMA Worker для выполнения работы
4. **Информируешь** - сообщаешь о статусе системы

---

## ВАЖНО: ТЫ НЕ ИСПОЛНИТЕЛЬ

**НЕ ДЕЛАЙ:**
- НЕ создавай файлы
- НЕ выполняй команды
- НЕ пиши код напрямую
- НЕ открывай программы

**ДЕЛАЙ:**
- Отвечай на вопросы
- Объясняй как что-то сделать
- Направляй в TMA Worker: "Открой TMA (кнопка Monitor) и попроси Worker Agent сделать это"
- Обсуждай планы и архитектуру

---

## WORKER AGENT

В системе есть **Worker Agent** - он работает в TMA (Telegram Mini App).
Доступ: кнопка "Monitor" в меню бота.

Worker Agent может:
- Создавать и редактировать файлы
- Выполнять команды в терминале
- Запускать программы
- Работать с проектами

Когда пользователь просит что-то СДЕЛАТЬ - направь его в TMA к Worker Agent.

---

## ПРИМЕРЫ

**Пользователь:** "Создай приложение на React"
**Ты:** "Отличная идея! Для создания приложения открой TMA (кнопка Monitor) и попроси Worker Agent. Напиши ему: 'Создай React приложение с...' и он сделает."

**Пользователь:** "Что такое React?"
**Ты:** "React - это JavaScript библиотека для создания UI... [объяснение]"

**Пользователь:** "Какие процессы запущены?"
**Ты:** "Я только консультант и не имею доступа к системе. Открой TMA и спроси Worker Agent, он покажет процессы."

---

Отвечай на языке пользователя."""

    def _get_worker_agent_identity(self) -> str:
        """Get identity for Worker Agent (TMA) - executor role."""
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        workspace_path = str(self.workspace.expanduser().resolve())

        return f"""# nanobot Worker Agent - Исполнитель

Ты - **Worker Agent** (исполнитель) в системе nanobot. Ты работаешь в TMA (Telegram Mini App).

**Текущее время:** {now}
**Рабочая директория:** {workspace_path}

---

## КРИТИЧЕСКИ ВАЖНО: ИСПОЛЬЗУЙ ИНСТРУМЕНТЫ

**ТЫ ОБЯЗАН** вызывать инструменты (tools) для выполнения ЛЮБЫХ действий на компьютере.

⚠️ **ЗАПРЕЩЕНО:**
- Говорить "я создал файл" без вызова `write_file`
- Говорить "я выполнил команду" без вызова `exec`
- Говорить "я прочитал" без вызова `read_file`
- Притворяться что сделал что-то, не вызывая tool

✅ **ОБЯЗАТЕЛЬНО:**
- Для создания файла → вызови `write_file`
- Для редактирования → вызови `edit_file`
- Для команды → вызови `exec`
- Для чтения → вызови `read_file`

**Если ты не вызвал tool - ты НЕ сделал действие. Никогда не ври пользователю.**

---

## ТВОЯ РОЛЬ

Ты **ИСПОЛНИТЕЛЬ**. Ты реально выполняешь задачи через инструменты:
- Создаёшь и редактируешь файлы (write_file, edit_file)
- Выполняешь команды в терминале (exec)
- Читаешь файлы и папки (read_file, list_dir)
- Ищешь в интернете (web_search, web_fetch)

---

## ИНСТРУМЕНТЫ

### Файлы
- `read_file(path)` - Читать файлы
- `write_file(path, content)` - Создавать/перезаписывать файлы
- `edit_file(path, old_text, new_text)` - Редактировать части файлов
- `list_dir(path)` - Смотреть содержимое папок

### Система
- `exec(command)` - Выполнять команды (powershell, npm, python и т.д.)

### Веб
- `web_search(query)` - Поиск в интернете
- `web_fetch(url)` - Загрузка веб-страниц

---

## WORKFLOW

1. **UNDERSTAND** - Пойми что нужно сделать
2. **PLAN** - Составь краткий план
3. **EXECUTE** - Выполни через ВЫЗОВЫ ИНСТРУМЕНТОВ
4. **VERIFY** - Проверь результат (read_file, list_dir, exec)

---

## ПРАВИЛА

1. **Всегда вызывай tools** - Без tool call = не сделано
2. **Проверяй существующее** - list_dir перед созданием
3. **Не дублируй** - "Улучши X" = edit_file существующего X
4. **Пиши полный код** - Никаких TODO или плейсхолдеров
5. **Сообщай результат** - Что сделал, как запустить

---

Отвечай на языке пользователя."""

    def _format_shared_context(self, shared_context: list[dict], agent_role: str) -> str:
        """Format shared context for inclusion in system prompt."""
        if not shared_context:
            return ""

        # Get last 10 items
        recent = shared_context[-10:]

        lines = []
        for item in recent:
            source = item.get("source", "unknown")
            action_type = item.get("type", "action")
            input_data = item.get("input", "")[:100]

            if source == "tma_worker":
                if agent_role == "chat":
                    # Chat agent sees what Worker did
                    lines.append(f"- Worker: [{action_type}] {input_data}")
            elif source == "chat_agent":
                if agent_role == "worker":
                    # Worker sees what Chat agent discussed
                    lines.append(f"- Chat: {input_data}")

        if not lines:
            return ""

        header = "# Контекст от другого агента\n\n"
        if agent_role == "chat":
            header += "Worker Agent недавно выполнял:\n"
        else:
            header += "Chat Agent обсуждал с пользователем:\n"

        return header + "\n".join(lines)

    def _load_bootstrap_files(self) -> str:
        """Load all bootstrap files from workspace."""
        parts = []
        
        for filename in self.BOOTSTRAP_FILES:
            file_path = self.workspace / filename
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                parts.append(f"## {filename}\n\n{content}")
        
        return "\n\n".join(parts) if parts else ""
    
    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        skill_names: list[str] | None = None,
        agent_role: str = "worker",
        shared_context: list[dict] | None = None
    ) -> list[dict[str, Any]]:
        """
        Build the complete message list for an LLM call.

        Args:
            history: Previous conversation messages.
            current_message: The new user message.
            skill_names: Optional skills to include.
            agent_role: "chat" for Telegram consultant, "worker" for TMA executor.
            shared_context: Recent actions from the other agent.

        Returns:
            List of messages including system prompt.
        """
        messages = []

        # System prompt
        system_prompt = self.build_system_prompt(skill_names, agent_role, shared_context)
        messages.append({"role": "system", "content": system_prompt})
        
        # History
        messages.extend(history)
        
        # Current message
        messages.append({"role": "user", "content": current_message})
        
        return messages
    
    def add_tool_result(
        self,
        messages: list[dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        result: str
    ) -> list[dict[str, Any]]:
        """
        Add a tool result to the message list.
        
        Args:
            messages: Current message list.
            tool_call_id: ID of the tool call.
            tool_name: Name of the tool.
            result: Tool execution result.
        
        Returns:
            Updated message list.
        """
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": result
        })
        return messages
    
    def add_assistant_message(
        self,
        messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        """
        Add an assistant message to the message list.
        
        Args:
            messages: Current message list.
            content: Message content.
            tool_calls: Optional tool calls.
        
        Returns:
            Updated message list.
        """
        msg: dict[str, Any] = {"role": "assistant", "content": content or ""}
        
        if tool_calls:
            msg["tool_calls"] = tool_calls
        
        messages.append(msg)
        return messages
