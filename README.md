# Content Intelligence & Shorts Engine (v2.1)

Plataforma de inteligência de conteúdo para garimpar vídeos e Shorts virais, analisar estruturas de retenção (Hooks 0-3s), alimentar ideias no Kanban de produção, preparar dados de cortes para o **MedPy** e modelar novos roteiros com IA.

---

## 💡 O Que Mudou na Versão 2.1

1. **Arquitetura Modular FastAPI & Separação Backend/Frontend:**
   - **`underfind/backend/`**: Estrutura modular dividida em `core/` (constantes, logger e utils), `schemas/` (Pydantic), `services/` (YouTube e Transcripts), `db/` (persistência SQLite local) e `routers/` (rotas segregadas).
   - **`underfind/frontend/`**: Aplicação SPA React 18 + TypeScript + Vite compilada em `underfind/frontend/dist`.
   - **Logger Centralizado Próprio**: Suporte nativo a nível `TRACE` (nível 5), `DEBUG` para envio e parâmetros, `TRACE` para resposta e `ERROR` para falhas, sem poluição de stdout.

2. **Hub de Integração MCP (Family-Friendly UX):**
   - Integração em 1 clique com **Claude Desktop / Claude AI**, **ChatGPT**, **Cursor / VS Code** e **Google Gemini / Antigravity**.
   - Cópia direta do comando universal `python -m underfind.backend.mcp.server` e bloco de configuração JSON `mcpServers`.
   - Inspetor visual das 4 ferramentas MCP prontas para uso local com zero telemetria.

3. **Design Engineering (Filosofia Emil Kowalski):**
   - **Zero Emojis:** Interface limpa, minimalista e focada em dados, métricas e tipografia.
   - **Paleta Neutra:** Tons escuros profundos de zinc com contraste refinado e acabamento premium.
   - **Interações Snappy:** Easing suave (`cubic-bezier(0.23, 1, 0.32, 1)`), física de clique ativo com `:active { transform: scale(0.97); }` e entradas animadas com `scale(0.96); opacity: 0`.
   - **Barra de Pesquisa Segmentada:** Interface contínua unificando nicho, tamanho de canal, taxa viral e região.

4. **Espaço de Trabalho de Vídeos (Workspace Modal):**
   - Player de vídeo embutido para inspeção direta.
   - **Modelagem de Roteiro (IA):** Gancho inicial (0-3s) isolado, transcrição completa com timestamps e prompt calibrado para LLMs.
   - **Preparação para MedPy (Cortes):** 5 marcadores de corte (Hook, Curiosity, Value, Climax, Loop) prontos para compilação de b-roll.

---

## Pipeline de Localização (v2.2, em construção)

Objetivo: pegar Reels/Shorts/TikToks internacionais (nicho inicial: GTA VI), traduzir para o idioma de cada página e renderizar no formato "foto de perfil + nome no topo, vídeo abaixo", entregando o arquivo final para a ferramenta de publicação em lote.

Cada vídeo de origem vira um **job** com máquina de estados persistida em SQLite:

```
found -> downloaded -> transcribed -> translated -> voiced -> rendered -> exported
                    (qualquer etapa ativa) -> failed | discarded
```

- Avanço só de uma etapa por vez; voltar para qualquer etapa anterior é permitido (re-execução).
- `failed` guarda a etapa que falhou e só permite retentar a partir dela ou antes; `discarded` só volta para `found`.
- A partir de `translated` o job precisa de uma **página de destino** (nome, @, avatar, idioma, template).
- **Registro de uso:** uma origem que já tem job não é reaproveitada (409), inclusive reuploads em outra plataforma detectados por hash perceptual (`force=true` ignora).
- **Cota do YouTube:** cada chamada reserva unidades antes de executar (`YOUTUBE_DAILY_QUOTA`), com retry exponencial para 429/5xx e bloqueio ao esgotar (HTTP 429 na API).

| Endpoint | Função |
|---|---|
| `POST /api/jobs` | Abre job a partir de URL do YouTube, Instagram ou TikTok (links curtos `vm.tiktok.com` são resolvidos) |
| `POST /api/jobs/from-video` | Abre job a partir de um resultado da busca/trending |
| `GET /api/jobs`, `GET /api/jobs/{id}`, `GET /api/jobs/{id}/events`, `GET /api/jobs/stats` | Consulta de jobs, histórico e contagem por status |
| `PATCH /api/jobs/{id}/status`, `PATCH /api/jobs/{id}/page` | Move o job na pipeline / define a página de destino |
| `GET/POST/PUT/DELETE /api/pages` | Perfis de página (identidade + idioma) |
| `GET/POST/PUT /api/templates` | Templates de renderização (cabeçalho, fontes, legenda) |
| `GET /api/quota` | Uso de cota do dia |

Próximas fases: download (yt-dlp) + transcrição (Whisper), renderização do template (ffmpeg), exportação com manifest, tradução/dublagem e busca automatizada multi-plataforma.

---

## 🚀 Como Rodar

### Opção 1: Execução Nativa em Python
Certifique-se de ter o Python 3.12 instalado e execute diretamente na raiz do projeto:
```bash
python app.py
```
Acesse no seu navegador:
* 🌐 **Aplicação Web:** `http://localhost:8000`
* 📚 **Documentação da API (Swagger):** `http://localhost:8000/docs`

Para utilizar o CLI no terminal:
```bash
python app.py search "inteligencia artificial" --shorts
python app.py trending --region BR
python app.py blueprint <VIDEO_ID>
```

### Opção 2: Execução com Docker & Docker Compose
Para rodar a aplicação completa containerizada com montagem persistente do SQLite:
```bash
docker compose up --build
```

---

## 🗺️ Roadmap de Integração

```
[Content Engine (v2.1)] ──> Garimpa Shorts Virais & Extrai Hooks 0-3s
         │
         ▼
[MedPy Engine (v2.2)] ────> Realiza Cortes Automáticos & Converte para 9:16
         │
         ▼
[Analytics OAuth (v2.3)] ─> Login com Google OAuth para monitorar métricas do próprio canal
         │
         ▼
[Agente Supervisor (v2.4)]─> Orquestração 100% Autônoma de Ponta a Ponta
```

### Próximas Etapas:
* **v2.2:** Integração do MCP do **MedPy** para processamento de vídeo e cortes automáticos.
* **v2.3:** Login do criador via Google OAuth para rastrear estatísticas dos próprios vídeos diretamente no Underfind Dashboard.
* **v2.4:** Agente de IA supervisor orquestrando busca, roteiro, corte com MedPy e agendamento.
