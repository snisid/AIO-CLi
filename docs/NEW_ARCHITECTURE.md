# 🧠 Nouvelle Architecture AIO-CLI

**Document de Référence Architecturale**  
**Version:** 2.0.0  
**Date:** 2025  
**Statut:** Architecture Cible

---

## Vue d'Ensemble

AIO-CLI évolue vers une plateforme de **coding agent multi-modèles de niveau frontier**, capable d'utiliser dynamiquement plusieurs LLMs et plusieurs gateways/providers selon la nature de la tâche.

L'objectif n'est PAS de simplement ajouter des modèles à une configuration, mais de construire un véritable :

> **Multi-Model Coding Agent Runtime + Intelligent Routing System + Tool/MCP Execution System + Verification/Recovery Loop**

---

## Architecture Logique

```
                         AIO-CLI KERNEL
                              │
                              ▼
                    ┌────────────────────┐
                    │ GLOBAL TASK ROUTER │
                    └─────────┬──────────┘
                              │
             ┌────────────────┼─────────────────┐
             │                │                 │
             ▼                ▼                 ▼
       CODING AGENT      RESEARCH AGENT    ARCHITECT AGENT
             │                │                 │
             ▼                ▼                 ▼
      INTELLIGENT        INTELLIGENT        INTELLIGENT
        ROUTER             ROUTER             ROUTER
             │                │                 │
       ┌─────┼─────┐    ┌─────┼─────┐    ┌─────┼─────┐
       ▼     ▼     ▼    ▼     ▼     ▼    ▼     ▼     ▼
     Opus  GPT   GLM  Kimi  Deep  Qwen  Fable  Opus  GPT
     Qwen Deep  GLM  Gemma GLM   Mini  GLM    Deep  Qwen
```

**Principe fondamental :**
- **Global Router** = choisit l'agent spécialisé pour la tâche
- **Agent Router** = choisit le meilleur modèle pour cet agent

---

## 1. Système d'Agents Spécialisés

### 🟢 Coding Agent (Priorité Maximale)

**Rôle :** Ingénieur logiciel autonome

**Capacités :**
- Analyser un repository complet
- Comprendre une architecture existante
- Rechercher des fichiers
- Modifier plusieurs fichiers
- Créer/supprimer des fichiers
- Exécuter des commandes
- Compiler et lancer les tests
- Analyser et corriger les erreurs
- Effectuer des refactors
- Gérer Git
- Utiliser MCP et les tools

**Modèles par tier :**

| Tier | Modèles | Usage |
|------|---------|-------|
| S (Frontier) | Fable 5, Opus 5, GPT-5.6, GLM-5.3 | Architecture complexe, code critique |
| A (Heavy) | DeepSeek-V4-Pro, Kimi 3, Qwen 3.8 27B | Implementation principale |
| B (Fast) | GLM-5.3-Flash, GLM-5.2:free, MiniMax M3:free | Tâches rapides |
| C (Free) | Gemma 4 26B:free, LFM 2.5 2.6B:free | Operations simples |

**Exemple de workflow :**
```
Complex architecture → Fable 5
    ↓
Implementation → Qwen 3.8
    ↓
Code review → DeepSeek V4
    ↓
Verification → GPT-5.6
```

---

### 🏗️ Architecture Agent

**Rôle :** Conception système et décisions techniques

**Capacités :**
- System analysis
- Architecture design
- Dependency analysis
- Design patterns
- Scalability
- Security architecture
- Technical decisions

**Router Priority :**
1. Fable 5
2. Opus 5
3. GPT-5.6
4. GLM-5.3
5. DeepSeek-V4-Pro
6. Kimi 3
7. Qwen 3.8 27B

**Pattern Multi-Modèle pour Architecture Critique :**
```
         ARCHITECTURE TASK
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
 Fable 5      Opus 5      GLM 5.3
    │           │           │
    └───────────┼───────────┘
                ▼
           CONSENSUS
                │
                ▼
          FINAL DESIGN
```

---

### 🔬 Research Agent

**Rôle :** Recherche et synthèse de connaissances

**Capacités :**
- Web research
- Documentation
- Repository research
- Technical comparison
- Long-context analysis
- Source verification
- Knowledge synthesis

**Router Priority :**
1. Kimi 3 (long contexte)
2. GPT-5.6
3. Fable 5
4. Opus 5
5. DeepSeek-V4-Pro
6. Qwen 3.8 27B
7. Gemma 4
8. GLM-5.2:free

---

### 🧪 Debugging Agent

**Rôle :** Analyse et correction d'erreurs

**Capacités :**
- Error analysis
- Stack trace analysis
- Root cause analysis
- Reproduction
- Patch generation
- Regression testing
- Verification

**Router Priority :**
1. DeepSeek-V4-Pro
2. GLM-5.3
3. Opus 5
4. GPT-5.6
5. Qwen 3.8
6. GLM-5.3-Flash

**Boucle de Correction :**
```
ERROR → ANALYZE → PATCH → TEST
                          │
                        FAIL?
                          │
                          └──── YES → DIFFERENT MODEL
                                        ↓
                                      PATCH
                                        ↓
                                       TEST
```

⚠️ **Règle :** Ne jamais laisser un modèle corriger indéfiniment son propre travail.

---

### 🔐 Security Agent

**Rôle :** Audit et validation de sécurité

**Capacités :**
- Threat modeling
- Permission analysis
- MCP security
- Tool validation
- Schema validation
- Prompt injection detection
- Command safety
- Secrets detection
- Security review

**Router Priority :**
1. Fable 5
2. Opus 5
3. GPT-5.6
4. DeepSeek-V4-Pro
5. GLM-5.3

**Pattern Double Validation pour Opérations Critiques :**
```
Implementation
      ↓
Security Model A
      ↓
Security Model B
      ↓
Consensus
      ↓
ALLOW / BLOCK
```

---

### 🧠 Planning Agent

**Rôle :** Décomposition et orchestration des tâches

**Capacités :**
- Task decomposition
- Dependency graph
- Execution planning
- Agent assignment
- Model assignment
- Recovery planning

**Modèles :**
- Fable 5
- Opus 5
- GPT-5.6
- GLM-5.3
- Kimi 3
- DeepSeek-V4-Pro

**Exemple de Plan Multi-Agent :**
```
TASK
 │
 ├── A: inspect repository → Qwen 3.8
 ├── B: MCP architecture → GLM-5.3
 ├── C: security analysis → Opus 5
 ├── D: implementation → Qwen 3.8
 ├── E: tests → GLM-5.3-Flash
 └── F: final review → GPT-5.6
```

---

### ⚡ Fast Agent

**Rôle :** Tâches simples et rapides

**Capacités :**
- Simple coding
- Formatting
- Classification
- Small transformations
- Summarization
- Metadata
- Simple tool calls

**Priorité (Cost-Optimized) :**
1. LFM 2.5 2.6B:free
2. GLM-5.3-Flash
3. Gemma 4:free
4. GLM-5.2:free
5. MiniMax M3:free
6. Qwen 3.8

💡 **Impact :** Réduction massive de la consommation des modèles premium.

---

### 👁️ Vision Agent

**Rôle :** Analyse d'images et d'interfaces

**Capacités :**
- Image analysis
- Screenshot analysis
- UI analysis
- Diagram understanding
- Visual debugging

**Priorité :**
1. GPT-5.6
2. Fable 5
3. Kimi 3
4. Gemma 4
5. MiniMax M3

---

### 🧩 MCP Agent

**Rôle :** Gestion du Model Context Protocol

**Capacités :**
- Server discovery
- Authentication
- Tool/resource discovery
- Schema validation
- Capability analysis
- Tool execution
- Monitoring
- Reconnection/Restart
- Security choke-point
- Graceful shutdown

**Router par Type d'Opération :**
```
Architecture → Fable 5 / Opus 5
Implementation → GLM-5.3 / Qwen 3.8
Schema → GPT-5.6 / DeepSeek
Security → Opus 5 / Fable 5
Fast operations → GLM-5.3-Flash
```

---

## 2. Intelligent Model Router

### Architecture du Router

Chaque agent possède son propre **Intelligent Router** indépendant :

```
Agent
│
├── AgentProfile
├── AgentRouter
├── ModelRegistry
├── CapabilityMatrix
├── ProviderHealth
├── TokenBudget
├── ContextManager
├── ToolRegistry
├── ExecutionPolicy
└── VerificationPolicy
```

### Interface du Router

```python
class AgentRouter:
    def select_model(self, task: Task) -> ModelSpec
    def select_provider(self, model: ModelSpec) -> Provider
    def check_health(self, model: str) -> HealthStatus
    def check_quota(self, model: str) -> QuotaInfo
    def estimate_cost(self, task: Task, model: str) -> float
    def estimate_latency(self, model: str) -> float
    def check_context(self, task: Task, model: str) -> bool
    def fallback(self, failed_model: str) -> ModelSpec
    def escalate(self, task: Task) -> ModelSpec
```

---

## 3. Model Registry & Capability Matrix

### Profil de Modèle

Chaque modèle a une fiche de capacités dynamique :

```yaml
model:
  id: qwen-3.8-27b
  provider: ollama
  
  capabilities:
    coding: 0.88
    reasoning: 0.86
    architecture: 0.82
    debugging: 0.87
    research: 0.80
    vision: 0.00
    tool_calling: 0.90
    mcp: 0.90
  
  performance:
    latency: medium
    throughput: high
    context: large
  
  cost:
    local: 0
  
  reliability:
    score: 0.99
```

⚠️ **Important :** Les scores ne sont pas codés en dur définitivement. AIO-CLI doit pouvoir les recalibrer à partir des benchmarks et de l'historique réel.

---

### Modèle de Scoring

```
MODEL_SCORE =

  (Capability × Task_Match × Reliability × Context_Fit 
   × Tool_Compatibility × Health)
  
  ─────────────────────────────────────────
  
  (Cost + Latency + Quota_Pressure)
```

**Filtres avant scoring :**
1. Capability filter
2. Context filter
3. Tool/MCP filter
4. Health filter
5. Quota filter
6. Cost/latency optimization

---

## 4. Providers & Gateways

### Architecture Multi-Gateway

```
                 AGENT ROUTER
                      │
                MODEL SELECTION
                      │
           ┌──────────┼──────────┐
           ▼          ▼          ▼
        Ollama      9Router    OmniRoute
           │          │          │
           └──────────┼──────────┘
                      ▼
                  OpenRouter
                      │
                      ▼
               Provider Failover
```

### Providers Supportés

#### 🟢 Local - Ollama
- **Modèle principal :** Qwen 3.8 27B
- **Avantages :**
  - Pas de quota distant
  - Pas d'API key
  - Données locales
  - Disponible sans Internet
  - Fallback permanent

#### 🔵 9Router
- **Type :** Gateway OpenAI-compatible
- **Usage :** Fallback et diversification
- **API Key :** `NINEROUTER_API_KEY`

#### 🟣 OmniRoute
- **Type :** Gateway MIT auto-hébergée
- **Usage :** Pool de modèles gratuits
- **API Key :** `OMNIROUTE_API_KEY`

#### 🟠 OpenRouter
- **Type :** Gateway multi-providers
- **Usage :** Filet de sécurité avec routeur gratuit
- **API Key :** `OPENROUTER_API_KEY`
- **Note :** Gratuit ≠ illimité (limites documentées)

---

## 5. Automatic Token/Quota Failover

### Principe Central

> « À chaque requête, déterminer quels modèles sont disponibles, quels quotas restent, quelles capacités sont nécessaires, puis choisir le meilleur modèle disponible. »

### États de Quota

```python
@dataclass
class ModelStatus:
    provider: str
    model: str
    available: bool = True
    remaining_tokens: int | None = None
    remaining_requests: int | None = None
    reset_at: datetime | None = None
    latency_ms: float | None = None
    last_error: str | None = None
```

### Niveaux de Gestion de Quota

**Niveau 1 — Quota connu :**
```
remaining_tokens = 5000
→ on peut anticiper
```

**Niveau 2 — Quota inconnu :**
```
remaining_tokens = None
→ on utilise normalement
```

**Niveau 3 — Provider refuse :**
```
429 / quota exceeded
→ on désactive temporairement
```

---

### Preemptive Switching

⚠️ **Ne pas attendre zéro token !**

```python
if (
    status.remaining_tokens is not None
    and status.remaining_tokens < estimated_tokens
):
    skip(model)
```

**Estimation des tokens :**
```
Estimated request = input + context + tools + output budget

Input             5,000
Conversation      20,000
MCP tools          4,000
Output budget      4,000
────────────────────────
Estimated         33,000 tokens
```

---

### Circuit Breaker

```
Provider
   ↓
5 failures
   ↓
CIRCUIT OPEN
   ↓
disable 60 sec
   ↓
probe
   ↓
healthy?
 ├── yes → ACTIVE
 └── no  → continue disabled
```

---

## 6. Chaîne de Fallback Intelligente

### Niveaux de Fallback

```
Niveau 1 — Meilleur modèle
Opus/Fable/GLM/etc.

Niveau 2 — Meilleur modèle disponible
Autre modèle remote

Niveau 3 — Local (filet de sécurité)
Ollama → Qwen 27B
```

### Exemple de Workflow

```
Primary: OmniRoute / Opus-5
remaining = 8K (estimated = 25K)
   ↓
❌ Skip Opus-5
   ↓
Search: OpenRouter / GLM-5.3
remaining = sufficient, quality = 96
   ↓
GLM-5.3 selected
   ↓
429 Too Many Requests
   ↓
❌ GLM-5.3
   ↓
Search: 9Router / Fable-5
   ↓
✓ Available
   ↓
Execute
   ↓
Quota exhausted
   ↓
Last fallback: Ollama / Qwen 27B
```

---

## 7. Boucle PLAN → EXECUTE → VERIFY → REPAIR

### Workflow Principal

```
USER TASK
    ↓
UNDERSTAND
    ↓
PLAN
    ↓
EXECUTE
    ↓
TEST
    ↓
VERIFY
    ↓
SUCCESS ✓
```

### Boucle de Réparation

```
FAILURE
    ↓
ANALYZE (Root Cause)
    ↓
REPLAN
    ↓
REPAIR
    ↓
TEST
    ↓
VERIFY
```

⚠️ **Limitation :** Limiter les retries et empêcher les boucles infinies.

---

## 8. Model Escalation

### Principe

Ne pas utiliser systématiquement les modèles les plus coûteux.

**Tâche simple :**
```
LFM 2.5 → GLM-5.3-Flash → Qwen 3.8
```

**Coding complexe :**
```
Qwen 3.8 → GLM-5.3 → DeepSeek-V4-Pro → Opus 5 / Fable 5 / GPT-5.6
```

**Architecture critique :**
```
GLM-5.3 → Opus 5 / Fable 5 → GPT-5.6 verification
```

🎯 **Le système doit escalader automatiquement** lorsqu'un modèle échoue ou lorsque la complexité dépasse son niveau.

---

## 9. Multi-Model Code Review

### Pattern de Review Indépendante

Pour les modifications importantes :

```
Implementation Model
        ↓
Independent Review Model
        ↓
Testing
        ↓
Final Verification
```

⚠️ **Règle :** Éviter que le même modèle écrive, vérifie et valide son propre code.

---

## 10. Parallel Agent Execution

### Exécution Parallèle

Lorsque les tâches sont indépendantes :

```
Task
├── Repository analysis
├── Security analysis
├── Documentation analysis
└── Test analysis
```

Doivent pouvoir s'exécuter en parallèle.

### Mécanismes Requis

- Task graph
- Dependency graph
- Concurrency control
- Cancellation
- Timeout
- Result aggregation

---

## 11. Context Management

### Rôles du Context Manager

- Repository context
- File context
- Task context
- Conversation context
- Tool results
- MCP results
- Previous actions
- Errors
- Test results

### Optimisations

⚠️ **Éviter d'envoyer inutilement tout le repository à chaque appel LLM.**

Implémenter :
- Context selection
- Context compression
- Relevant-file retrieval
- Summarization
- Context caching
- Token budgeting

---

## 12. Token / Quota Manager

### Surveillance Continue

- Tokens utilisés
- Tokens restants (quand disponibles)
- Limites provider
- Rate limits
- Erreurs 429
- Budget
- Coût estimé

### Règle de Fallback

```
quota exhausted
    ↓
provider fallback
    ↓
model fallback
    ↓
next best model
```

⚠️ **NE JAMAIS arrêter AIO-CLI** quand un quota est épuisé.

---

## 13. Health Manager

### Surveillance Continue

- Provider availability
- Latency
- Timeout
- Error rate
- HTTP failures
- Authentication failures
- Rate limits
- Model availability

### Mécanismes

- Circuit breaker
- Exponential backoff
- Cooldown
- Health scoring

Un provider défaillant ne doit pas ralentir inutilement toutes les tâches.

---

## 14. Tool Runtime

### Tools Minimum

- Filesystem (read/write/edit/delete)
- Terminal/Shell
- Git
- Search/Glob
- Code execution
- Tests
- Package manager
- HTTP/API (autorisé)
- MCP

⚠️ **Tous les tools doivent passer par une couche de contrôle commune.**

---

## 15. MCP Integration

### Cycle de Vie Complet

1. Server discovery
2. Authentication
3. Tool discovery
4. Resource discovery
5. Schema retrieval
6. Schema validation
7. Tool execution
8. Monitoring
9. Reconnection
10. Restart
11. Graceful shutdown
12. Security validation

⚠️ **Tous les appels MCP doivent passer par le Security Choke-Point.**

---

## 16. Security Choke-Point

### Point de Contrôle Central

**Toutes** les opérations sensibles doivent passer par lui :

- Shell commands
- Filesystem modifications
- MCP tools
- Network calls
- Credential access
- Git operations
- Package installation

### Implémentation Minimum

- Permission checks
- Allowlist/denylist
- Command validation
- Path validation
- Secret detection
- Tool policy
- Audit logging

⚠️ **Jamais d'accès direct incontrôlé au système pour le LLM.**

---

## 17. Integration des Projets Externes

### Repositories à Étudier

| Projet | URL | Usage Potentiel |
|--------|-----|-----------------|
| 9router | https://github.com/decolua/9router.git | Gateway provider |
| OmniRoute | https://github.com/diegosouzapw/OmniRoute.git | Orchestration/failover |
| bolt.new | https://github.com/stackblitz/bolt.new.git | Code generation patterns |
| cursor | https://github.com/cursor/cursor.git | Agentic coding patterns |
| VercelZero | https://github.com/DaveSimoes/VercelZero.git | Deployment workflows |
| emergent | https://github.com/ndl7209/emergent.git | Agent orchestration |

### Règles d'Intégration

⚠️ **NE PAS copier aveuglément leur code.**

Pour chaque repository :
1. Analyser l'architecture
2. Identifier les composants réutilisables
3. Identifier les patterns utiles
4. Vérifier les licences
5. Vérifier les dépendances
6. Vérifier les conflits d'architecture
7. Intégrer uniquement ce qui apporte une amélioration réelle

---

## 18. Observability

### Enregistrement de Chaque Exécution

- Task
- Agent
- Model
- Provider
- Latency
- Tokens
- Estimated cost
- Tool calls
- MCP calls
- Errors
- Retries
- Fallback
- Final result
- Verification result

### Questions Auxquelles Répondre

> « Pourquoi AIO-CLI a choisi ce modèle ? »

---

## 19. Adaptive Routing

### Apprentissage Progressif

AIO-CLI doit progressivement apprendre quels modèles fonctionnent le mieux pour quelles tâches.

**Données à enregistrer :**
```
task type + model + provider + result + quality + latency + failure
```

### Évolution

Commencer avec :
- Scoring déterministe + historique

Préparer pour :
- Routing adaptatif basé ML (futur)

---

## 20. Performance

### Optimisations

- Streaming
- Async execution
- Connection pooling
- Caching
- Context caching
- Parallel tasks
- Concurrent tool calls (quand sûrs)
- Request batching (quand supporté)
- Model warm-up (Ollama)
- Provider health caching

⚠️ **Ne jamais sacrifier la fiabilité uniquement pour gagner quelques millisecondes.**

---

## 21. Configuration

### Exemple Conceptuel

```yaml
agents:
  coding:
    router:
      strategy: capability_score
      escalation: true
      verification: true
  
  architecture:
    router:
      strategy: performance
      multi_model_review: true

models:
  - qwen-3.8-27b
  - glm-5.3
  - deepseek-v4-pro
  - opus-5
  - fable-5
  - gpt-5.6

providers:
  ollama:
    type: local
    enabled: true
    base_url: http://localhost:11434
  
  9router:
    type: gateway
    enabled: true
    api_key_env: NINEROUTER_API_KEY
  
  omniroute:
    type: gateway
    enabled: true
    api_key_env: OMNIROUTE_API_KEY
  
  openrouter:
    type: gateway
    enabled: true
    api_key_env: OPENROUTER_API_KEY

routing:
  default:
    prefer_free: true
    prefer_local: true
    fallback_enabled: true
  
  coding:
    min_capability: high
    tool_calling: true
  
  reasoning:
    min_capability: high
  
  private:
    local_only: true
```

---

## 22. Tests Obligatoires

### Catégories de Tests

#### Router
- Model selection
- Provider selection
- Capability matching
- Fallback
- Escalation

#### Provider
- Timeout
- Rate limit
- Authentication error
- Unavailable provider

#### Agent
- Task execution
- Retry
- Recovery
- Context handling

#### Coding
- Multi-file modification
- Compile
- Test
- Repair

#### MCP
- Discovery
- Schema validation
- Execution
- Reconnect
- Security

#### Security
- Dangerous command
- Unauthorized path
- Secret leakage
- Malicious tool

#### Integration (End-to-End)
```
User → Global Router → Agent → Agent Router → Model 
     → Provider → Tool → Test → Verification → Result
```

---

## 23. Benchmark Interne

### Catégories de Benchmark

- Repository understanding
- Coding
- Debugging
- Refactoring
- Architecture
- Tool calling
- MCP
- Test repair
- Long-context tasks

Les résultats doivent alimenter le Model Registry pour améliorer le routing.

---

## 24. Principes d'Architecture

### Règles Impératives

1. **Modularité** - Composants indépendants et testables
2. **Dependency Inversion** - Dépendre des abstractions, pas des implémentations
3. **Provider Independence** - Aucun lock-in provider
4. **Model Independence** - Aucun lock-in modèle
5. **Agent Independence** - Agents spécialisés autonomes
6. **Testability** - Tout doit être testable unitairement
7. **Observability** - Traçabilité complète
8. **Security** - Choke-points obligatoires
9. **Graceful Degradation** - Fallback automatique
10. **Backward Compatibility** - Préserver les fonctionnalités existantes

⚠️ **AIO-CLI ne doit jamais devenir dépendant d'un seul fournisseur.**

---

## 25. Definition of Done

La mission est terminée uniquement lorsque :

- ✅ AIO-CLI compile/build correctement
- ✅ Les tests existants passent
- ✅ Les nouveaux tests passent
- ✅ Coding Agent fonctionne
- ✅ Chaque agent possède son routing spécialisé
- ✅ Model Registry fonctionne
- ✅ Provider Registry fonctionne
- ✅ Fallback fonctionne
- ✅ Quota management fonctionne
- ✅ Health management fonctionne
- ✅ Context management fonctionne
- ✅ MCP fonctionne
- ✅ Security Choke-Point fonctionne
- ✅ Verification loop fonctionne
- ✅ Multi-model routing fonctionne
- ✅ Modèles locaux Ollama fonctionnent
- ✅ Gateways distants fonctionnent
- ✅ Erreurs provider récupérées automatiquement
- ✅ Aucun secret hardcodé
- ✅ Aucune dépendance externe inutile

---

## 26. Méthode d'Implémentation

### Phases

| Phase | Sujet | Livrables |
|-------|-------|-----------|
| 1 | Repository audit | État des lieux complet |
| 2 | Architecture + interfaces | ABCs, dataclasses |
| 3 | Model Registry | Registry + Capability Matrix |
| 4 | Provider Registry | Registry + Health |
| 5 | Global Router | Task classification |
| 6 | Agent Routers | Router par agent |
| 7 | Coding Agent | Agent principal |
| 8 | Context Manager | Gestion contexte |
| 9 | Fallback / quota / health | Resilience |
| 10 | Tool + MCP runtime | Exécution |
| 11 | Verification / repair | Quality loops |
| 12 | External project integration | Patterns utiles |
| 13 | Testing | Suite complète |
| 14 | Benchmark | Performance metrics |
| 15 | Performance optimization | Tuning |

### Après Chaque Phase

1. Exécuter les tests
2. Corriger les régressions
3. Documenter les changements
4. Vérifier l'architecture
5. Continuer uniquement si stable

---

## 27. Rapport Final

À la fin, fournir :

1. Architecture finale
2. Fichiers ajoutés
3. Fichiers modifiés
4. Fichiers supprimés
5. Modèles supportés
6. Providers supportés
7. Agents supportés
8. Routing strategy
9. Fallback strategy
10. MCP implementation
11. Security implementation
12. Tests ajoutés
13. Benchmarks
14. Problèmes connus
15. Améliorations futures

---

## 28. Architecture Finale Cible

```
                         AIO-CLI
                            │
                    ┌───────▼────────┐
                    │ GLOBAL ROUTER  │
                    └───────┬────────┘
                            │
       ┌────────────────────┼────────────────────┐
       │                    │                    │
       ▼                    ▼                    ▼
   CODING                RESEARCH             SECURITY
    AGENT                  AGENT                AGENT
       │                    │                    │
  ┌────▼────┐          ┌────▼────┐          ┌────▼────┐
  │ ROUTER  │          │ ROUTER  │          │ ROUTER  │
  └────┬────┘          └────┬────┘          └────┬────┘
       │                    │                    │
   MODELS                 MODELS               MODELS
       │                    │                    │
       └────────────────────┼────────────────────┘
                            │
                     PROVIDER ROUTER
                            │
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
          Ollama          9Router       OmniRoute
             │              │              │
             └──────────────┼──────────────┘
                            ▼
                       OpenRouter
                            │
                            ▼
                   Provider Failover
```

---

## Conclusion

Cette architecture transforme AIO-CLI en un véritable **système multi-agents cognitif** où :

- Opus 5, Fable 5, GLM-5.3, GPT-5.6, Kimi 3, DeepSeek-V4-Pro, Qwen 3.8 27B, GLM-5.3-Flash et les modèles :free ne sont pas simplement "disponibles"
- Ils deviennent des **ressources sélectionnables dynamiquement** par chaque agent en fonction de la mission
- Le **Model Router + quota tracking + fallback multi-gateway** donne l'impression d'un pool pratiquement inépuisable
- **Qwen local** sert de dernier fallback sans quota distant

🎯 **Objectif :** AIO-CLI devient un coding agent robuste, intelligent, multi-modèles, multi-provider, autonome, vérifiable et performant — pas simplement un wrapper autour de plusieurs APIs.

---

**Document Propriétaire :** AIO-CLI Core Team  
**Classification :** Architecture Reference  
**Prochaine Review:** Après Phase 5 (Global Router)
