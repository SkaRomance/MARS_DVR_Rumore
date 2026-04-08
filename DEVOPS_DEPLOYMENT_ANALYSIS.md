# DevOps Deployment Analysis - MARS DVR Rumore Module

## Executive Summary

Analisi infrastrutturale e operativa per il deployment del modulo DVR Rischio Rumore MARS. Il percorso prevede un inizio on-premise (MVP) con evoluzione verso cloud hybrid in fase successiva.

---

## 1. Deployment Architecture

### 1.1 Architettura Target - MVP On-Premise

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LOAD BALANCER                               │
│                    (Nginx/HAProxy - SSL Termination)                │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
          ┌─────────▼─────────┐       ┌─────────▼─────────┐
          │   APP SERVER 1    │       │   APP SERVER 2    │
          │   (Docker)        │       │   (Docker)        │
          │   - Node.js API   │       │   - Node.js API   │
          │   - Python AI     │       │   - Python AI     │
          └─────────┬─────────┘       └─────────┬─────────┘
                    │                           │
                    └─────────────┬─────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
  ┌───────▼────────┐    ┌─────────▼────────┐    ┌────────▼────────┐
  │   PostgreSQL   │    │      Redis       │    │   File Storage  │
  │   (Primary +   │    │   (Cache/Queue)  │    │   (Attachments,  │
  │    Standby)    │    │                  │    │   Reports)      │
  └────────────────┘    └──────────────────┘    └─────────────────┘
```

### 1.2 Componenti Architetturali

#### Application Tier
- **API Gateway / Backend**: Node.js (Express/Fastify)
- **AI Processing Engine**: Python (FastAPI/Flask)
- **Background Jobs**: Redis Queue / Bull
- **File Processing**: Worker nodes per generazione report

#### Data Tier
- **Primary Database**: PostgreSQL 15+ (con estensioni: PostGIS opzionale per mapping, pg_trgm per full-text search)
- **Cache Layer**: Redis 7+ (session management, cache query frequenti, rate limiting)
- **Object Storage**: NFS / S3-compatible (MinIO per on-premise)

#### Integration Layer
- **DVR Integration Endpoint**: REST API verso modulo DVR generale
- **External Data Sources**: Cache locale per ATECO, normative, knowledge base

### 1.3 Architettura Rete e Sicurezza

#### Network Segmentation
```
Internet
    │
    ▼
┌─────────────────┐
│   DMZ Zone      │ ← Load Balancer, WAF
└────────┬────────┘
         │
┌────────▼────────┐
│ Application Zone│ ← App Servers, AI Engine
└────────┬────────┘
         │
┌────────▼────────┐
│   Data Zone     │ ← PostgreSQL, Redis, Storage
└─────────────────┘
```

#### Security Groups / Firewall Rules
- **DMZ → App**: Solo HTTPS (443), SSH (22) da subnet admin
- **App → Data**: PostgreSQL (5432), Redis (6379)
- **App → Storage**: NFS/S3 API
- **Data Tier**: Zero ingress da Internet, solo da App Zone

---

## 2. Container Strategy

### 2.1 Containerizzazione Docker

#### Strategia Base
La containerizzazione offre vantaggi immediati anche per deployment on-premise:
- **Isolamento** tra componente API, AI Engine, e workers
- **Reproducibility** tra dev, staging, production
- **Resource limits** per prevenire noisy neighbor
- **Rolling updates** semplificati

#### Immagini Docker Richieste

| Componente | Base Image | Dimensione Stimata | Cache Strategy |
|------------|-----------|-------------------|----------------|
| API Server | node:20-alpine | ~150MB | Multi-stage, layer caching |
| AI Engine | python:3.11-slim | ~400MB | Model layer separato |
| PostgreSQL | postgres:15-alpine | ~80MB | Volume per dati |
| Redis | redis:7-alpine | ~30MB | Persistenza opzionale |
| Nginx | nginx:alpine | ~25MB | Config mounted |
| Worker | node:20-alpine | ~150MB | Condivisa con API |

#### Multi-stage Build Pattern
```
Build Stage 1: Dependencies
Build Stage 2: Build/transpile
Build Stage 3: Production image (minimal)

Benefici:
- Immagine finale <200MB per API
- Build cache ottimizzato
- Security scanning su immagine finale
- No dev dependencies in production
```

### 2.2 Container Registry

#### On-Premise Registry
- **Opzione A**: Docker Registry self-hosted (open source)
- **Opzione B**: Harbor (enterprise, con vulnerability scanning)
- **Opzione C**: Nexus Repository (con supporto artefatti multipli)

**Raccomandazione MVP**: Docker Registry base con filesystem backend

#### Tagging Strategy
```
Format: {component}:{version}-{environment}-{build}

Esempi:
- mars-api:1.2.0-prod-45
- mars-api:latest-staging
- mars-ai:1.0.0-prod-12
- mars-worker:dev-latest
```

### 2.3 Container Resource Allocation

| Servizio | CPU Request | CPU Limit | Memory Request | Memory Limit |
|----------|------------|-----------|----------------|--------------|
| API Server | 500m | 2000m | 512Mi | 2Gi |
| AI Engine | 1000m | 4000m | 2Gi | 8Gi |
| PostgreSQL | 1000m | 2000m | 1Gi | 4Gi |
| Redis | 250m | 500m | 256Mi | 512Mi |
| Nginx | 100m | 200m | 64Mi | 128Mi |
| Worker | 500m | 2000m | 512Mi | 2Gi |
| Monitoring | 500m | 1000m | 512Mi | 1Gi |

---

## 3. Orchestration Strategy

### 3.1 Docker Compose vs Kubernetes

#### Analisi Comparativa

| Criterio | Docker Compose | Kubernetes (K8s) |
|----------|----------------|------------------|
| Complessità setup | Bassa | Alta |
| Learning curve | Giorni | Settimane/Mesi |
| Scalabilità orizzontale | Manuale | Automatica |
| Self-healing | Limitato | Nativo |
| Service discovery | File-baseddns | DNS interno |
| Secrets management | File/Env | Secrets API |
| Rolling updates | Manuale | Automatico |
| Resource overhead | Minimo | 5-10% cluster |
| Production readiness | Per carichi medio | Enterprise-grade |

### 3.2 Raccomandazione per Fasi

#### Fase MVP (On-Premise) - Docker Compose
**Giustificazione**:
- Deployment limitato (1-2 server)
- Team ops ridotto
- Time-to-market prioritario
- Carico predicibile (utenti interni, batch processing)
- Costi minimi di infrastruttura

**Limitazioni accettate**:
- Scalabilità manuale
- Failover manuale database
- Update con breve downtime

#### Fase 2 (Cloud/Hybrid) - Kubernetes

**Trigger per migrazione**:
- Più di 3 nodi applicativi
- Richiesta alta disponibilità (HA) 99.9%+
- Multi-region deployment
- Team DevOps dedicato disponibile
- Auto-scaling requirement

### 3.3 Docker Compose - Architettura MVP

```yaml
Stack Services:
├── mars-api           (2 replicas)
├── mars-ai            (1 replica, scala per carico)
├── mars-worker        (2 replicas)
├── postgres-primary   (1 instance)
├── postgres-standby   (1 instance - warm standby)
├── redis              (1 instance, con persistenza)
├── nginx              (1 instance)
└── prometheus         (monitoring)
    └── grafana
    └── alertmanager
```

**Deployment Flow**:
```bash
# Principale
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Rollback
docker compose -f docker-compose.yml -f docker-compose.prod.yml rollback
```

---

## 4. Infrastructure as Code (IaC)

### 4.1 Strategia IaC

#### Terraform vs Ansible

| Aspetto | Terraform | Ansible |
|---------|-----------|---------|
| Tipo | Infrastructure provisioning | Configuration management |
| State | Maintained state | State-less |
| Idempotency | Nativo | Richiede attenzione |
| Cloud support | Eccellente | Buono |
| On-premise | Limitato (provider specifici) | Eccellente |
| Learning curve | Medio | Basso |

### 4.2 Architettura IaC Raccomandata

```
terraform/
├── modules/
│   ├── network/      # VLAN, firewall rules
│   ├── compute/      # VM provisioning
│   └── storage/      # NFS, backup volumes
├── environments/
│   ├── dev/
│   ├── staging/
│   └── prod/
└── main.tf

ansible/
├── roles/
│   ├── docker/       # Docker installation
│   ├── postgres/     # PostgreSQL setup + tuning
│   ├── redis/        # Redis configuration
│   ├── monitoring/   # Prometheus/Grafana
│   ├── backup/       # Backup automation
│   └── security/     # Hardening
├── inventory/
│   ├── dev.yml
│   ├── staging.yml
│   └── prod.yml
├── playbooks/
│   ├── site.yml      # Full provisioning
│   ├── update.yml    # Rolling update
│   └── backup.yml    # Backup trigger
└── group_vars/
```

### 4.3 Workflow IaC

```
┌──────────────┐
│   Developer  │
│   Push Code  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   CI Server  │
│   Run Tests  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Terraform   │
│   Validate   │
│   Plan       │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Approval   │
│   (Staging)  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Apply      │
│   Ansible    │
│   Configure  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Deploy     │
│   Containers │
└──────────────┘
```

### 4.4 State Management

#### Terraform State
- **Backend**: Terraform Cloud (free tier per team piccoli) o S3-compatible storage
- **Locking**: DynamoDB o PostgreSQL lock table
- **Secrets**: Non in state file, usare variabili ambiente

#### Ansible Dynamic Inventory
- Script python per scoprire nodi dinamici
- Inventory da CMDB esterno o file YAML statico per MVP

---

## 5. Environment Management

### 5.1 Ambiente Strategia

#### Definizione Ambienti

| Ambiente | Scopo | Data | Lifespan | Accesso |
|-----------|------|------|----------|---------|
| **Development** | Sviluppo attivo | Sample/synthetic | Permanente | Dev team |
| **Staging** | Pre-produzione, UAT | Anonymized prod | Permanente | Dev + QA + stakeholder |
| **Production** | Live | Real | Permanente | Ops + limitato dev |

### 5.2 Environment Parity

```
Parità richiesta:
├── Container images (stessa versione)
├── Infrastructure (configurazione identica)
├── Dependencies (versioni identiche)
└── Data (struttura, non volume)

Differenze accettabili:
├── Resource sizing (minore in dev)
├── Data volume (ridotto in staging)
├── Feature flags (abilitati per test)
└── Logging verbosity (maggiore in dev)
```

### 5.3 Configuration Management

#### Environment Variables Strategy

```bash
# Gerarchia (dal basso verso l'alto, il più alto vince)
1. Container defaults (nei Dockerfile)
2. docker-compose.yml (defaults per ambiente)
3. .env file (ambiente-specifico, NON commit)
4. Environment variables (CI/CD injection)
5. Secrets manager (sensibili)
```

#### Config Files Structure
```
config/
├── default.json          # Shared config all environments
├── development.json      # Dev overrides
├── staging.json          # Staging overrides
├── production.json       # Prod overrides
└── custom-environment-variables.json  # ENV mapping
```

### 5.4 Feature Flags

**Strumento**: Unleash (open source) o LaunchDarkly

#### Use Cases
- Rollout graduale nuove feature AI
- Test A/B su UI
- Emergency kill-switch per funzionalità instabili
- Gradual rollout per tenant specifici (multi-tenant)

---

## 6. Secrets Management

### 6.1 Strategia Multi-Layer

#### Layer 1: Infrastructure Secrets
- **Cosa**: DB passwords, API keys infra, TLS private keys
- **Dove**: HashiCorp Vault (enterprise) o Ansible Vault (MVP)
- **Accesso**: Solo automation e ops

#### Layer 2: Application Secrets
- **Cosa**: JWT secret, encryption keys, AI API keys
- **Dove**: Vault o Docker Secrets (K8s: Kubernetes Secrets)
- **Accesso**: App containers via injection

#### Layer 3: User Secrets
- **Cosa**: Password utenti, token sessione
- **Dove**: Database (hashed, salted) + Redis (session tokens)
- **Accesso**: Solo applicazione

### 6.2 Secrets Lifecycle

```
┌──────────────┐
│   Create     │ ← Automation generates
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Store      │ ← Vault/Secrets Manager
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Distribute │ ← CI/CD injects at deploy
└──────┬──────┘
       │
       ▼
┌──────────────┐
│   Rotate     │ ← Automatic rotation (30-90 days)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Revoke     │ ← On compromise/offboard
└──────────────┘
```

### 6.3 Secret Detection

**Pre-commit Hooks**: git-secrets, detect-secrets
**CI/CD Stage**: TruffleHog, GitLeaks scan
**Runtime**: Nessun secret in logs, env inspection

### 6.4 MVP Secrets Implementation

```
MVP Fase 1: Ansible Vault
├── File criptati in repo
├── Password in file fuori repo
├── Injection via template Ansible
└── Rotation manuale

MVP Fase 2: Docker Secrets (Swarm)
├── File-based secrets
├── Mounted in container
└── Limited rotation support

Cloud Migration: HashiCorp Vault
├── Dynamic secrets
├── Auto-rotation
├── Lease management
└── Audit logging
```

---

## 7. Monitoring e Logging

### 7.1 Monitoring Stack

#### Architettura Completa

```
┌─────────────────────────────────────────────────────────────────────┐
│                          GRAFANA                                    │
│                    (Visualization, Dashboards, Alerts UI)           │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
          ┌─────────▼─────────┐       ┌─────────▼─────────┐
          │   PROMETHEUS      │       │   LOKI            │
          │   (Metrics DB)    │       │   (Log Aggregation)│
          │   + Alertmanager  │       │                   │
          └─────────┬─────────┘       └─────────┬─────────┘
                    │                           │
          ┌─────────▼─────────┐       ┌─────────▼─────────┐
          │   EXPORTERS       │       │   PROMTAIL        │
          │   - node exporter │       │   (Log Collector) │
          │   - postgres      │       │                   │
          │   - redis         │       │                   │
          │   - custom app   │       │                   │
          └───────────────────┘       └───────────────────┘
```

### 7.2 Metrics Strategy

#### Golden Signals (Four Golden Signals - SRE Book)
1. **Latency**: Tempo di risposta richieste
2. **Traffic**: Richieste per secondo
3. **Errors**: Tasso di errore
4. **Saturation**: Utilizzo risorse

#### Metriche Specifiche per MARS DVR

| Categoria | Metrica | Soglia Warning | Soglia Critical |
|-----------|---------|----------------|-----------------|
| **Application** | Request latency p50 | 200ms | 500ms |
| | Request latency p99 | 1000ms | 2000ms |
| | API error rate | 1% | 5% |
| | AI inference time | 5s | 15s |
| | Active sessions | 80% max | 95% max |
| **Database** | Connection pool usage | 70% | 90% |
| | Query latency p95 | 50ms | 200ms |
| | Replication lag | 10MB | 100MB |
| | Disk usage | 70% | 85% |
| **Cache** | Hit rate | <80% | <50% |
| | Memory usage | 80% | 95% |
| | Connection count | 80% max | 95% max |
| **System** | CPU usage | 70% | 90% |
| | Memory usage | 75% | 90% |
| | Disk I/O wait | 5ms | 20ms |
| | Network saturation | 70% | 85% |

### 7.3 Logging Strategy

#### Log Levels
- **ERROR**: Errori che impattano business logic
- **WARN**: Situazioni anomale ma gestite
- **INFO**: Eventi significativi (audit trail, business events)
- **DEBUG**: Debugging info (solo dev/staging)
- **TRACE**: Detailed trace (mai in prod)

#### Structured Logging Format
```json
{
  "timestamp": "2026-01-15T10:30:00.000Z",
  "level": "INFO",
  "service": "mars-api",
  "version": "1.2.0",
  "trace_id": "abc-123-def",
  "span_id": "span-456",
  "tenant_id": "tenant-789",
  "user_id": "user-101",
  "message": "Assessment created",
  "context": {
    "assessment_id": "ass-2026-001",
    "company_id": "comp-456"
  }
}
```

#### Log Retention Policy
| Log Type | Hot Storage | Cold Storage | Archive |
|----------|-------------|--------------|---------|
| Application | 7 days | 30 days | 1 year |
| Audit trail | 90 days | 1 year | 7 years (compliance) |
| System | 3 days | 14 days | 90 days |
| Security | 30 days | 1 year | 5 years |

### 7.4 Alerting Strategy

#### Escalation Matrix

```
Severity: P1 (Critical - Service Down)
├── Response: Immediate (< 5 min)
├── Notification: PagerDuty + Slack + Email
├── Escalation: On-call → Lead → Manager (15 min)
└── Examples: DB down, API 5xx > 10%

Severity: P2 (High - Degraded Service)
├── Response: < 30 min
├── Notification: Slack + Email
├── Escalation: On-call → Lead (1 hour)
└── Examples: High latency, elevated errors

Severity: P3 (Medium - Warning)
├── Response: < 4 hours
├── Notification: Slack
├── Escalation: Next business day
└── Examples: Disk space warning, cache hit rate

Severity: P4 (Low - Info)
├── Response: Next business day
├── Notification: Daily digest email
└── Examples: Certificate expiry (30 days)
```

### 7.5 Dashboards

#### Required Dashboards

1. **System Overview**: Infra health, CPU, memory, disk, network
2. **Application Health**: Request rate, latency, errors, throughput
3. **Database Performance**: Query latency, connections, locks, replication
4. **Business Metrics**: Active users, assessments created, AI prompts used
5. **AI/ML Pipeline**: Inference time, queue depth, model performance
6. **Security**: Failed logins, anomalies, audit events
7. **SLA/SLO**: Availability, performance targets tracking

---

## 8. Backup e Recovery

### 8.1 Backup Strategy (3-2-1 Rule)

```
3 copies of data
2 different storage media
1 offsite/offline copy
```

### 8.2 Backup Components

| Component | Type | Frequency | Retention | Method |
|-----------|------|-----------|-----------|--------|
| **PostgreSQL** | Full dump | Daily | 30 days | pg_dump + WAL archiving |
| | WAL archive | Continuous | 7 days | pg_wal |
| | PITR capable | Yes | - | Point-in-time recovery |
| **Redis** | RDB snapshot | Hourly | 7 days | BGSAVE |
| | AOF | Every write | 1 day | Append-only file |
| **Application Files** | Backup | Daily | 30 days | rsync / restic |
| | Documents | Daily | 90 days | Incremental |
| **Configurations** | Backup | On change | Forever | Git |
| **Secrets** | Backup | On rotation | Encrypted offline | Vault backup |

### 8.3 Backup Procedures

#### PostgreSQL Backup

```
Full Backup (Daily 02:00)
├── pg_dump --format=custom --compress=9
├── Integrity check
├── Encryption (AES-256)
├── Upload to backup storage
├── Upload to offsite storage
└── Verify (checksum)

WAL Archiving (Continuous)
├── Archive every WAL segment
├── Compress + encrypt
├── Upload to backup storage
└── Enable PITR (Point-in-Time Recovery)

Schedule:
├── Daily full backup: 02:00 AM
├── WAL archiving: continuous
├── Weekly integrity check
└── Monthly restore test
```

#### File Storage Backup

```
Incremental Backup (Daily)
├── Identify changed files
├── Compress
├── Encrypt
├── Upload to backup storage
├── Weekly full backup
└── Monthly archive backup
```

### 8.4 Recovery Procedures

#### Database Recovery

```
Scenario 1: Point-in-time Recovery (accidental delete)
├── Stop application (maintenance mode)
├── Restore base backup
├── Replay WAL up to target time
├── Verify integrity
├── Start application
└── RTO: 30-60 minutes, RPO: 0 (with WAL)

Scenario 2: Complete Database Loss
├── Provision new database server
├── Restore from latest backup
├── Apply WAL archives
├── Verify integrity
├── Update connection strings
├── Start application
└── RTO: 1-2 hours, RPO: 0-1 hour

Scenario 3: Corrupted Data (logical corruption)
├── Identify corruption scope
├── Export affected tables
├── Restore from backup
├── Apply delta from logs
├── Verify data integrity
└── RTO: 2-4 hours, RPO: 0-1 hour
```

### 8.5 Disaster Recovery (DR)

#### RTO/RPO Targets

| Scenario | RTO | RPO | Priority | DR Site |
|----------|-----|-----|----------|---------|
| Single server failure | 30 min | 0 | P1 | Failover standby |
| Data center failure | 4 hours | 1 hour | P2 | Cold DR site |
| Regional disaster | 24 hours | 24 hours | P3 | Offsite backup |

#### DR Architecture (Future Cloud)

```
PRIMARY SITE (On-Premise)
├── Active Application
├── Primary PostgreSQL
├── Active Redis
└── File Storage

    │ Replication (async)
    │
    ▼

DR SITE (Cloud - AWS/Azure)
├── Minimal standby (cost-optimized)
├── PostgreSQL replica sync
├── Redis replica
└── S3-compatible storage sync
```

#### DR Procedures

```
Phase 1: Assessment (0-30 min)
├── Alert notification
├── Incident commander assigned
├── Impact assessment
└── Decision: failover or restore?

Phase 2: Failover (30-120 min)
├── Promote DR database
├── Update DNS records
├── Start application instances
├── Verify all services
└── Monitor for issues

Phase 3: Failback (Post-recovery)
├── Sync primary with DR
├── Schedule maintenance window
├── Failback to primary
├── Verify monitoring
└── Post-incident review
```

---

## 9. SSL/TLS Certificates

### 9.1 Certificate Strategy

#### Types Required
| Tipo | Uso | Validity | Issuer |
|------|-----|----------|--------|
| **Wildcard Domain** | *.mars.local, *.mars.app | 1 year | Let's Encrypt / CA |
| **Internal Services** | postgres.local, redis.local | 10 years | Self-signed / Internal CA |
| **Client Authentication** | MTLS for APIs | 1 year | Internal CA |

### 9.2 Certificate Management

#### Tool: Cert-Manager (Kubernetes) / Certbot (Docker Compose)

```
Flow:
├── Certbot (MVP)
│   ├── Standalone mode per nuove cert
│   ├── Webroot mode per renewals
│   ├── Auto-renewal via cron
│   └── Integration with Nginx
│
└── Cert-Manager (Cloud/K8s)
    ├── Automatic issuance
    ├── Auto-renewal
    ├── Multiple issuers (Let's Encrypt, CA)
    └── Secret management integration
```

### 9.3 TLS Configuration

#### Modern TLS Settings
```
Protocol Versions: TLS 1.2, TLS 1.3
Cipher Suites: 
  - TLS_AES_256_GCM_SHA384
  - TLS_CHACHA20_POLY1305_SHA256
  - TLS_AES_128_GCM_SHA256
  - ECDHE-RSA-AES256-GCM-SHA384
  - ECDHE-RSA-CHACHA20-POLY1305

HSTS: Strict-Transport-Security: max-age=31536000; includeSubDomains
Certificate Transparency: Enabled
OCSP Stapling: Enabled
```

### 9.4 Certificate Rotation

```
Lifecycle:
├── Issue: 30 days before expiry (Let's Encrypt: 60 days)
├── Deploy: Automated to all services
├── Test: Verify TLS handshake
├── Monitor: Expiry alerts at 30, 14, 7 days
└── Escalate: Manual intervention if auto-renewal fails
```

---

## 10. Load Balancing

### 10.1 Load Balancer Strategy

#### On-Premise (MVP): HAProxy / Nginx

```
┌─────────────────────────────────────────────────────────────────────┐
│                     LOAD BALANCER (Active)                          │
│                    Nginx / HAProxy                                  │
│                                                                     │
│  Features:                                                          │
│  - SSL Termination                                                  │
│  - Round Robin / Least Connections                                  │
│  - Health Checks                                                    │
│  - Rate Limiting                                                    │
│  - Request Routing                                                  │
└─────────────────────────────────────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
        ▼           ▼           ▼
    Server 1    Server 2    Server 3
    (Active)    (Active)    (Active)
```

### 10.2 Load Balancing Algorithms

| Algorithm | Use Case | Pro | Contro |
|-----------|----------|-----|--------|
| **Round Robin** | Uniform servers | Simple | No consideration of load |
| **Least Connections** | Varying request duration | Better distribution | State tracking |
| **IP Hash** | Session affinity needed | Sticky sessions | Uneven distribution |
| **Weighted Round Robin** | Different server capacities | Flexible | Manual weight management |

**Raccomandazione**: Least Connections per applicazione, Weighted se AI Engine ha risorse diverse

### 10.3 Health Checks

```
Active Health Checks (Load Balancer):
├── TCP check (port reachable)
├── HTTP health endpoint (/health)
├── Check frequency: 5 seconds
├── Unhealthy threshold: 3 failures
├── Healthy threshold: 2 successes
└── Timeout: 2 seconds

Passive Health Checks:
├── Mark unhealthy after X failed requests
├── Retry requests to healthy backend
└── Circuit breaker pattern
```

### 10.4 Session Persistence

```
Options:
├── Sticky Sessions (IP Hash)
│   ├── Pro: Simple state handling
│   └── Contro: Unbalanced load
├── Session Store (Redis)
│   ├── Pro: Stateless app servers
│   └── Contro: Redis dependency
└── JWT Tokens (Recommended)
    ├── Pro: Stateless, scalable
    └── Contro: Token management

Raccomandazione: JWT Tokens + Redis for session invalidation
```

### 10.5 Failover Configuration

```
Active-Passive (MVP):
├── Primary LB active
├── Secondary LB standby (keepalived)
├── Virtual IP shared
└── Automatic failover < 5 seconds

Active-Active (Future):
├── Multiple LBs active
├── DNS round-robin or BGP anycast
└── Geographic load balancing (cloud)
```

---

## 11. Database Migrations in Production

### 11.1 Migration Strategy

#### Principles
1. **Backward Compatible**: Nuovo schema deve supportare vecchia versione app
2. **Zero Downtime**: Migrazioni senza service interruption
3. **Reversible**: Ogni migrazione deve avere rollback
4. **Tested**: Migrazioni testate su staging con dati production-like
5. **Audited**: Log completo di ogni migrazione

### 11.2 Migration Workflow

```
┌────────────────────────────────────────────────────────────────┐
│                    MIGRATION WORKFLOW                          │
└────────────────────────────────────────────────────────────────┘

Phase 1: Preparation
├── Schema changes reviewed by DBA
├── Migration script developed
├── Rollback script prepared
├── Impact assessment documented
└── Staging test completed

Phase 2: Pre-Deployment
├── Announcement to stakeholders
├── Maintenance window scheduled (if needed)
├── Backup (full + WAL)
├── Monitoring dashboards ready
└── Rollback procedure documented

Phase 3: Deployment
├── Deploy new application version
├── Run migration scripts
├── Verify data integrity
├── Smoke tests
└── Monitor for issues

Phase 4: Validation
├── Application logs check
├── Performance metrics check
├── Data validation queries
└── User acceptance spot checks

Phase 5: Completion or Rollback
├── If success: Mark migration complete
└── If failure: Execute rollback, restore backup
```

### 11.3 Database Change Types

| Change Type | Impact | Strategy | Downtime |
|-------------|--------|----------|----------|
| **Add table** | Low | Create new table | None |
| **Add column (nullable)** | Low | Add column | None |
| **Add column (NOT NULL)** | Medium | Add nullable → Backfill → Set NOT NULL | None |
| **Add index** | Medium | CREATE INDEX CONCURRENTLY | None |
| **Drop column** | High | Ignore column → Remove code → Drop | None |
| **Change column type** | High | Add new → Migrate → Swap | Possible |
| **Rename column** | Medium | Add new → Dual-write → Migrate → Remove old | None |

### 11.4 Migration Tools

```
MVP: Knex.js / Prisma Migrate
├── Version-controlled migrations
├── Up/down scripts
├── Lock table per migration
└── Automatic rollback

Advanced: Flyway / Liquibase
├── Enterprise features
├── Baseline support
├── Repeatable migrations
└── Schema history table
```

### 11.5 Rollback Procedure

```
Immediate Rollback (< 5 min):
├── Stop deployment
├── Run migration rollback script
├── Redeploy previous application version
├── Verify functionality
└── Post-mortem

Delayed Rollback (> 5 min):
├── Assess data changes since migration
├── Decide: rollback or forward fix
├── If rollback: restore backup + WAL replay
├── If forward: develop and deploy fix
└── Post-mortem
```

---

## 12. Rollback Strategy

### 12.1 Application Rollback

#### Container Rollback (Docker Compose)

```
Scenario: New version has critical bug

Method 1: Tag-based Rollback
├── Identify last known good version
├── Update docker-compose.yml image tag
├── docker compose pull [service]
├── docker compose up -d [service]
└── Verify health checks

Method 2: Container Image Rollback
├── List containers: docker compose ps
├── Find working image: docker images
├── Tag rollback: docker tag mars-api:v1.2 mars-api:rollback
├── Stop current: docker compose stop mars-api
├── Start rollback: docker compose up -d mars-api
└── Monitor for stability

Method 3: Blue-Green (advanced)
├── Blue: current production
├── Green: new version deployed parallel
├── Switch LB to Blue (previous)
└── No downtime rollback
```

### 12.2 Database Rollback

```
Scenario: Migration caused data corruption

Immediate (< 5 min window):
├── Stop application
├── Run migration down script
├── Verify data integrity
├── Start application
└── Time: 5-15 minutes

Delayed (> 5 min, data changes occurred):
├── Stop application (maintenance mode)
├── Assess corruption scope
├── Restore from backup (pre-migration)
├── Replay WAL to point before migration
├── Apply forward data changes (if possible)
├── Start application
└── Time: 1-4 hours
```

### 12.3 Infrastructure Rollback

```
Terraform Rollback:
├── terraform plan -target=module.xxx (dry run)
├── terraform apply -target=module.xxx (apply rollback)
├── State rollback: terraform state pull > backup.json
└── terraform state push backup.json

Ansible Rollback:
├── ansible-playbook rollback.yml -i inventory/prod.yml
├── Limit to affected hosts: --limit "host1,host2"
└── Check: ansible all -m command -a "service status"
```

### 12.4 Complete System Rollback

```
Scenario: Major failure, full restore needed

Steps:
1. Stop all services (maintenance mode)
2. Restore infrastructure from Terraform state
3. Restore database from backup
4. Restore file storage
5. Redeploy last known good containers
6. Verify all services
7. Switch off maintenance mode
8. Monitor intensively for 2 hours

Duration: 2-4 hours
Communication: Users notified throughout
```

### 12.5 Rollback Decision Matrix

| Failure Type | Detection Time | Rollback Time | Strategy |
|--------------|----------------|---------------|----------|
| **Code bug (non-data)** | < 5 min | 5 min | Container rollback |
| **Code bug (> 5 min)** | 5-30 min | 10-15 min | Container rollback |
| **DB migration (no data loss)** | < 5 min | 10 min | Migration rollback |
| **DB migration (data loss)** | Any | 1-4 hours | Backup restore + WAL |
| **Infrastructure failure** | Any | 30 min - 4 hours | Terraform/Ansible rollback |
| **Security breach** | Any | 30 min - 2 hours | Full system isolate + restore |

---

## 13. Cost Analysis

### 13.1 Cost Models

#### Model A: On-Premise MVP (Docker Compose)

**Infrastructure**
| Component | Qty | Specs | Unit Cost/Year | Total/Year |
|-----------|-----|-------|----------------|------------|
| **Application Server** | 2 | 4 vCPU, 16GB RAM, 250GB SSD | €2,400 | €4,800 |
| **Database Server** | 2 | 4 vCPU, 32GB RAM, 500GB SSD | €3,000 | €6,000 |
| **Storage/NFS** | 1 | 2TB RAID | €1,200 | €1,200 |
| **Network/Load Balancer** | 1 | HAProxy VM | €1,000 | €1,000 |
| **Backup Storage** | 1 | 2TB external | €500 | €500 |
| **UPS/Power** | 1 | Redundancy | €300 | €300 |
| **Total Hardware** | - | - | - | **€13,800** |

**Software/Licensing**
| Item | Cost/Year |
|------|-----------|
| OS (Enterprise support) | €0 (Linux) |
| PostgreSQL | €0 (Open source) |
| Redis | €0 (Open source) |
| Docker | €0 (Community) |
| Monitoring (Prometheus/Grafana) | €0 (Open source) |
| SSL Certificates | €0 (Let's Encrypt) |
| **Total Software** | **€0** |

**Operations**
| Item | Cost/Year |
|------|-----------|
| DevOps Engineer (0.25 FTE) | €15,000 |
| DBA consulting (occasional) | €3,000 |
| Power & Cooling | €1,500 |
| Internet/Bandwidth | €1,200 |
| **Total Operations** | **€20,700** |

**One-Time Costs**
| Item | Cost |
|------|------|
| Rack/Cage setup | €2,000 |
| Initial hardware purchase | €12,000 |
| Network configuration | €1,000 |
| **Total One-Time** | **€15,000** |

**MVP On-Premise Total**
| | Year 1 | Year 2+ |
|---|--------|---------|
| Infrastructure | €13,800 | €8,800* |
| Software | €0 | €0 |
| Operations | €20,700 | €20,700 |
| One-time | €15,000 | €0 |
| **TOTAL** | **€49,500** | **€29,500** |

*Assuming 3-year refresh cycle, depreciation spread

---

#### Model B: Cloud (AWS/Azure) - Docker Compose on VMs

**Compute (MVP)**
| Component | Qty | Instance Type | Unit Cost/Month | Total/Month |
|-----------|-----|---------------|-----------------|-------------|
| **App Server** | 2 | t3.large (2 vCPU, 8GB) | €120 | €240 |
| **AI Engine** | 1 | r5.large (2 vCPU, 16GB) | €150 | €150 |
| **Database** | 1 | db.r5.large (PostgreSQL) | €200 | €200 |
| **Redis** | 1 | cache.r5.large | €120 | €120 |
| **NAT Gateway** | 1 | Managed | €30 | €30 |
| **Load Balancer** | 1 | Application LB | €20 | €20 |
| **Total Compute** | - | - | - | **€760** |

**Storage**
| Item | Size | Cost/Month |
|------|------|------------|
| App storage | 100GB | €10 |
| DB storage | 500GB (GP3) | €50 |
| Backup storage | 200GB | €20 |
| S3 (documents) | 100GB | €2 |
| **Total Storage** | - | **€82** |

**Additional Services**
| Service | Cost/Month |
|---------|------------|
| CloudWatch (monitoring) | €30 |
| Secrets Manager | €5 |
| Route 53 (DNS) | €1 |
| Certificate Manager | €0 |
| **Total Services** | **€36** |

**Bandwidth/Data Transfer**
| Item | Cost/Month |
|------|------------|
| Data transfer out | €20 (estimate) |
| **Total Bandwidth** | **€20** |

**Cloud MVP Total**
| | Monthly | Yearly |
|---|---------|---------|
| Compute | €760 | €9,120 |
| Storage | €82 | €984 |
| Services | €36 | €432 |
| Bandwidth | €20 | €240 |
| **TOTAL** | **€898** | **€10,776** |

*Note: Costs can vary +20-30% based on traffic*

---

#### Model C: Cloud (AWS/Azure) - Kubernetes

**EKS/AKS Control Plane**
| Item | Cost/Month |
|------|------------|
| EKS Cluster | €60 |
| **Total Control Plane** | **€60** |

**Compute (Managed Node Groups)**
| Node Type | Qty | Specs | Unit Cost/Month | Total/Month |
|-----------|-----|-------|-----------------|-------------|
| App nodes | 2 | m5.large | €100 | €200 |
| AI nodes | 2 | r5.xlarge | €150 | €300 |
| Worker nodes | 2 | m5.large | €100 | €200 |
| **Total Compute** | - | - | - | **€700** |

**Managed Services**
| Service | Cost/Month |
|---------|------------|
| RDS PostgreSQL (db.r5.large) | €200 |
| ElastiCache Redis | €120 |
| S3 Storage | €5 |
| EBS Volumes | €50 |
| Load Balancer | €40 |
| **Total Managed Services** | **€415** |

**Additional (Same as Model B)**
| | Monthly |
|---|---------|
| Services | €36 |
| Bandwidth | €20 |
| **Total Additional** | **€56** |

**Kubernetes Cloud Total**
| | Monthly | Yearly |
|---|---------|---------|
| Control Plane | €60 | €720 |
| Compute | €700 | €8,400 |
| Managed Services | €415 | €4,980 |
| Additional | €56 | €672 |
| **TOTAL** | **€1,231** | **€14,772** |

---

#### Model D: Hybrid (On-Prem + Cloud Burst)

**On-Premise (Core)**
| | Yearly |
|---|--------|
| Core infrastructure (lighter) | €20,000 |
| Operations | €15,000 |
| **On-Prem Total** | **€35,000** |

**Cloud (Burst/DR)**
| | Monthly | Yearly |
|---|---------|---------|
| DR standby | €200 | €2,400 |
| Burst capacity (avg) | €150 | €1,800 |
| Data transfer | €50 | €600 |
| **Cloud Total** | - | **€4,800** |

**Hybrid Total**
| | Yearly |
|---|--------|
| On-Premise | €35,000 |
| Cloud | €4,800 |
| **TOTAL** | **€39,800** |

---

### 13.2 Cost Comparison Summary

| Model | Year 1 | Year 2 | Year 3 | 3-Year TCO | Pro |
|-------|--------|--------|--------|------------|-----|
| **A: On-Premise** | €49,500 | €29,500 | €29,500 | **€108,500** | Control, no egress fees |
| **B: Cloud (VM)** | €10,776 | €10,776 | €10,776 | **€32,328** | Low upfront, scalable |
| **C: Cloud (K8s)** | €14,772 | €14,772 | €14,772 | **€44,316** | Enterprise features, HA |
| **D: Hybrid** | €39,800 | €39,800 | €39,800 | **€119,400** | Best of both worlds |

### 13.3 Cost Optimization Strategies

#### On-Premise Optimization
- Buy vs Lease: Hardware lease spreads cost over time
- Virtualization: Higher density, fewer physical servers
- Energy efficiency: Reduce power/cooling costs
- Refurbished hardware: 30-50% cost reduction

#### Cloud Optimization
- Reserved Instances: 30-60% discount (1-3 year commitment)
- Spot Instances: 70-90% discount for non-critical workloads
- Right-sizing: Match instance size to actual usage
- Storage tiering: Use S3-IA, Glacier for infrequent access

#### Hybrid Optimization
- Keep steady workload on-prem
- Burst to cloud for peak loads
- Use cloud for DR (minimal standby cost)
- Data gravity: Keep data where processing occurs

### 13.4 Recommendation

#### MVP Phase (Year 1)
**Choice**: On-Premise (Model A)

**Justification**:
- Lowest Year 1 cost if infrastructure exists
- Full control over data (compliance)
- Simplest operations (no cloud expertise needed)
- Predictable costs
- No vendor lock-in

**Risk**: Requires hardware investment, limited scalability

#### Growth Phase (Year 2+)
**Choice**: Evaluate Hybrid (Model D) or Cloud K8s (Model C)

**Migration Triggers**:
- User base growing >50% YoY
- Multi-region requirement
- Team skilled in cloud/K8s
- Compliance allows cloud
- CAPEX constraints

---

## 14. Operational Runbook Summary

### 14.1 Daily Operations

| Task | Frequency | Responsible |
|------|-----------|-------------|
| Health check dashboard | Daily | Ops |
| Backup verification | Daily | Ops |
| Log review (errors) | Daily | Ops |
| Certificate expiry check | Daily | Automated |
| Capacity planning review | Weekly | Ops + Dev |

### 14.2 Incident Response

```
Severity Level | Response Time | Notification | Resolution Target
P1 Critical    | < 15 min      | Ops + Lead + Manager | < 4 hours
P2 High        | < 1 hour      | Ops + Lead           | < 8 hours
P3 Medium      | < 4 hours     | Ops                  | < 48 hours
P4 Low         | < 24 hours    | Daily digest         | < 1 week
```

### 14.3 Maintenance Windows

| Type | Frequency | Duration | Approval |
|------|-----------|----------|----------|
| Security patches | Monthly | 1 hour | Ops lead |
| Minor updates | Monthly | 2 hours | Ops lead |
| Major updates | Quarterly | 4 hours | Manager + Stakeholder |
| Database maintenance | Monthly | 2 hours | DBA |
| DR drill | Quarterly | 1 day | Manager |

---

## 15. Security Checklist

### 15.1 Network Security
- [ ] Firewall rules minimally permissive
- [ ] Network segmentation implemented (DMZ, App, Data zones)
- [ ] Intrusion detection/prevention (IDS/IPS)
- [ ] VPN for admin access
- [ ] Bastion host for SSH/remote access

### 15.2 Application Security
- [ ] Regular dependency scanning (npm audit, Snyk)
- [ ] Container image scanning (Trivy, Clair)
- [ ] OWASP Top 10 mitigations
- [ ] Input validation and sanitization
- [ ] Authentication/authorization hardening
- [ ] Rate limiting implemented
- [ ] CORS properly configured

### 15.3 Data Security
- [ ] Encryption at rest (PostgreSQL TDE, file encryption)
- [ ] Encryption in transit (TLS 1.2+)
- [ ] Database connection encryption
- [ ] Backup encryption
- [ ] Secrets not in code/version control
- [ ] Key rotation policy implemented

### 15.4 Operational Security
- [ ] Principle of least privilege
- [ ] Audit logging enabled
- [ ] Security patching schedule
- [ ] Vulnerability scanning (weekly)
- [ ] Penetration testing (quarterly)
- [ ] Security incident response plan

---

## 16. Summary and Recommendations

### 16.1 MVP Phase (On-Premise)

**Recommended Stack**:
```
Deployment: Docker Compose
Container Registry: Docker Registry (self-hosted)
Infrastructure Provisioning: Ansible
Configuration Management: Ansible
Secrets: Ansible Vault
Monitoring: Prometheus + Grafana + Loki
Logging: Promtail → Loki
Backup: pg_dump + restic
Load Balancer: Nginx/HAProxy
Database: PostgreSQL 15 + Redis 7
```

**Key Advantages**:
- Minimal complexity
- Full control
- Lower Year 1 cost
- No cloud expertise required
- Data sovereignty compliance

### 16.2 Growth Phase (Cloud/Hybrid)

**Recommended Stack**:
```
Deployment: Kubernetes (EKS/AKS)
Infrastructure: Terraform
Secrets: HashiCorp Vault / AWS Secrets Manager
Monitoring: Prometheus Operator + Grafana + Loki
Backup: Cloud-native (RDS snapshots, S3 versioning)
Load Balancer: Cloud LB (ALB/Application Gateway)
Database: Managed PostgreSQL + Redis
```

**Key Advantages**:
- Horizontal scalability
- High availability
- Managed services reduce ops burden
- Auto-scaling
- Multi-region capability

### 16.3 Migration Path

```
MVP (Month 1-12):
├── Docker Compose on-premise
├── Ansible for IaC
├── Basic monitoring
└── Manual scaling, backup

Growth (Month 12-24):
├── Evaluate cloud options
├── Kubernetes training
├── Terraform adoption
├── CI/CD pipeline hardening
└── Monitoring improvements

Scale (Month 24+):
├── Migrate to cloud K8s
├── Implement auto-scaling
├── Multi-region deployment
├── Advanced DR
└── Cost optimization
```

### 16.4 Next Steps

1. **Infrastructure Setup (Week 1-2)**: Provision MVP servers, network config
2. **Container Build (Week 2-3)**: Dockerfile creation, registry setup
3. **Monitoring Setup (Week 3-4)**: Prometheus, Grafana, Loki deployment
4. **Backup Implementation (Week 4-5)**: Backup scripts, scheduling, testing
5. **Security Hardening (Week 5-6)**: Firewall rules, secrets management
6. **Documentation (Week 6-7)**: Runbooks, diagrams, procedures
7. **DR Drill (Week 7-8)**: Failure simulation, recovery test
8. **Production Readiness (Week 8+)**: Final checks, go-live

---

## Appendices

### A. Reference Architecture Diagram

*(Visual diagram will be created separately)*

### B. Sample Dashboard Configurations

*(Grafana dashboard JSON available separately)*

### C. Backup Script Templates

*(Shell scripts available separately)*

### D. Monitoring Alert Rules

*(Prometheus alert rules available separately)*

### E. Security Benchmarks

*(CIS Docker Benchmark, PostgreSQL Hardening Guide available separately)*

---

**Document Version**: 1.0
**Last Updated**: 2026-01-15
**Author**: DevOps Analysis
**Status**: Complete