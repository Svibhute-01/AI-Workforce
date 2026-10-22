# AI-Workforce 🚀

### Multi-Agent AI Platform for Intelligent SDLC Automation

AI Workforce is an AI-powered software development platform that uses specialized AI agents to automate different stages of the Software Development Life Cycle.

## 🤖 AI Agents

- **Requirements Analyst AI** – Converts SRS documents into structured requirements, user stories and acceptance criteria.
- **Project Manager AI** – Converts requirements into tasks, epics, dependencies, sprints, milestones and risks.
- **System Architect AI** – Generates High-Level Design (HLD) and Low-Level Design (LLD) from requirements and project plans.
- **Developer AI** – Builds and modifies code based on project tasks.
- **QA AI** – Validates implementations against requirements and acceptance criteria.

## 🧠 Core Technologies

[![Core Technologies](https://skillicons.dev/icons?i=react,vite,fastapi,postgres,python,tailwind,github)](https://skillicons.dev)

- **LangChain** – LLM application framework
- **LangGraph** – Multi-agent workflow orchestration
- **RAG** – Project-specific knowledge retrieval
- **ChromaDB** – Vector database
- **Gemini 2.5 Flash** – LLM for agent reasoning and generation
- **Gemini-Embedding-001** – Embedding model for semantic retrieval

## 🔄 Architecture

```text
SRS
 ↓
Requirements Analyst AI
 ↓
Project Manager AI
 ↓
System Architect AI
 ↓
Developer AI
 ↓
QA AI
 ↓
Software Delivery
```

## 📊 Features

- Multi-agent SDLC automation
- Project-specific RAG
- AI-generated requirements and project plans
- AI-generated HLD and LLD
- Dynamic project dashboard
- Task and sprint management
- AI agent run tracking
- PostgreSQL-based persistent project state
- Modern responsive SaaS UI

## 🚧 Status

- [x] Requirements Analyst AI
- [x] Project Manager AI
- [x] System Architect AI
- [x] Developer AI (code generation, tests, self-repair; runs as `Developer_Agent/`)
- [ ] QA AI
