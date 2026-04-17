# Wave 24 — MARS Repo Modifications

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` inline o invoca l'agente custom `mars-backend-dev` (in `.claude/agents/mars-backend-dev.md`). Questo wave lavora sul repo MARS (`SkaRomance/MARS`), NON sul repo Rumore corrente.

**Goal:** Estendere MARS con endpoint/schema/componenti che supportano l'integrazione del modulo Rumore (e futuri moduli rischio) come thin plugin.

**Architecture:** Aggiungo 9 modifiche additive (M1-M9) alla repo MARS su branch `noise-module-integration`. Nessun breaking change: schema v1.0 rimane valido, JWT legacy rimane valido, endpoint esistenti intatti.

**Tech Stack:** NestJS 10 + Prisma 5.18 + PostgreSQL 16 + Zod + pnpm + Turbo + React 19 + Vite + BullMQ + passport-jwt + argon2

**Repo target:** `C:/Users/Salvatore Romano/Desktop/MARS_inspect` (già clonato in sessione precedente; se non c'è, Task 1 lo ri-clona)

**Stima:** 14-16h. Parallelizzabile con Wave 25.

---

## Pre-requisiti

- Accesso write a `git@github.com:SkaRomance/MARS.git`
- pnpm installato (`npm install -g pnpm`)
- PostgreSQL 16 locale attivo
- Node 20+ installato
- Credenziali di test per DB locale

---

## Task 1: Setup workspace MARS

**Files:**
- Create: `C:/Users/Salvatore Romano/Desktop/MARS_inspect/.git/` (clone se non esiste)
- Modify: — (solo git)

- [ ] **Step 1.1: Verifica se repo esiste, altrimenti clone**

```bash
cd "C:/Users/Salvatore Romano/Desktop"
if [ ! -d "MARS_inspect/.git" ]; then
  rm -rf MARS_inspect
  git clone https://github.com/SkaRomance/MARS.git MARS_inspect
fi
cd MARS_inspect
git fetch origin
```

Expected: repo clonato o aggiornato.

- [ ] **Step 1.2: Crea branch `noise-module-integration`**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_inspect"
git checkout master 2>/dev/null || git checkout main
git pull origin $(git branch --show-current)
git checkout -b noise-module-integration
```

Expected: branch creato e checked out.

- [ ] **Step 1.3: Install dependencies**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_inspect"
pnpm install
```

Expected: no errori install. Log "done" con pacchetti.

- [ ] **Step 1.4: Baseline test run**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_inspect/apps/api"
pnpm run test -- --passWithNoTests 2>&1 | tail -20
```

Expected: baseline test count annotato (registra numero di test in questo report).

- [ ] **Step 1.5: Commit branch setup**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_inspect"
# Nessun cambio file ancora; solo registra start
git log -1 --oneline > /tmp/mars-baseline-sha.txt
```

Expected: SHA baseline salvato.

---

## Task 2 — M5: JWT claim `tenant_id` opzionale

Questo è primo perché M1 /me deve usarlo.

**Files:**
- Modify: `apps/api/src/auth/auth.service.ts` (aggiungi tenant_id al payload `issueTokens`)
- Modify: `apps/api/src/auth/strategies/jwt.strategy.ts` (propaga tenant_id nel request user)
- Test: `apps/api/src/auth/auth.service.spec.ts`

- [ ] **Step 2.1: Leggi il file esistente auth.service.ts**

```bash
cat "C:/Users/Salvatore Romano/Desktop/MARS_inspect/apps/api/src/auth/auth.service.ts"
```

Annota metodo `issueTokens` (firma e body corrente).

- [ ] **Step 2.2: Scrivi test failing per tenant_id nel payload**

File: `apps/api/src/auth/auth.service.spec.ts` (aggiungi test alla suite esistente)

```typescript
describe('issueTokens with tenant_id', () => {
  it('includes tenant_id in access token payload when user belongs to a single tenant', async () => {
    const user = { id: 'user-uuid', email: 'a@b.com', tenants: [{ id: 'tenant-uuid' }] };
    const tokens = await service.issueTokens(user as any);

    const jwt = require('jsonwebtoken');
    const decoded = jwt.decode(tokens.accessToken);
    expect(decoded.tenant_id).toBe('tenant-uuid');
    expect(decoded.sub).toBe('user-uuid');
  });

  it('omits tenant_id when user belongs to multiple tenants (ambiguous)', async () => {
    const user = {
      id: 'user-uuid',
      email: 'a@b.com',
      tenants: [{ id: 't1' }, { id: 't2' }],
    };
    const tokens = await service.issueTokens(user as any);

    const jwt = require('jsonwebtoken');
    const decoded = jwt.decode(tokens.accessToken);
    expect(decoded.tenant_id).toBeUndefined();
  });
});
```

- [ ] **Step 2.3: Run test — atteso FAIL**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_inspect/apps/api"
pnpm run test -- auth.service.spec.ts -t "tenant_id"
```

Expected: FAIL (payload non contiene tenant_id).

- [ ] **Step 2.4: Modifica `issueTokens` per aggiungere tenant_id**

File: `apps/api/src/auth/auth.service.ts`

Nel metodo `issueTokens`, trova la sezione che costruisce `payload` per access token. Modifica così:

```typescript
async issueTokens(user: User & { tenants?: { id: string }[] }) {
  const basePayload: Record<string, unknown> = {
    sub: user.id,
    email: user.email,
  };

  // M5: Include tenant_id only if user belongs to exactly one tenant (unambiguous)
  if (user.tenants && user.tenants.length === 1) {
    basePayload.tenant_id = user.tenants[0].id;
  }

  const accessToken = await this.jwtService.signAsync(
    { ...basePayload, type: 'access' },
    {
      secret: this.configService.get('JWT_ACCESS_SECRET'),
      expiresIn: this.configService.get('ACCESS_TOKEN_TTL', '900s'),
    },
  );

  const refreshToken = await this.jwtService.signAsync(
    { ...basePayload, type: 'refresh' },
    {
      secret: this.configService.get('JWT_REFRESH_SECRET'),
      expiresIn: this.configService.get('REFRESH_TOKEN_TTL', '7d'),
    },
  );

  return { accessToken, refreshToken };
}
```

- [ ] **Step 2.5: Modifica jwt.strategy.ts per propagare tenant_id**

File: `apps/api/src/auth/strategies/jwt.strategy.ts`

Nel metodo `validate`, aggiungi:

```typescript
async validate(payload: any) {
  return {
    sub: payload.sub,
    email: payload.email,
    tenantId: payload.tenant_id,  // M5: può essere undefined (legacy token o multi-tenant user)
    type: payload.type,
  };
}
```

- [ ] **Step 2.6: Run test — atteso PASS**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_inspect/apps/api"
pnpm run test -- auth.service.spec.ts -t "tenant_id"
```

Expected: 2/2 PASS.

- [ ] **Step 2.7: Run full auth test suite — regression check**

```bash
pnpm run test -- auth.service.spec.ts
pnpm run test -- auth.controller.spec.ts
```

Expected: tutti PASS, no regressioni.

- [ ] **Step 2.8: Commit**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_inspect"
git add apps/api/src/auth/auth.service.ts apps/api/src/auth/strategies/jwt.strategy.ts apps/api/src/auth/auth.service.spec.ts
git commit -m "M5: Add optional tenant_id claim to JWT tokens

Backward compatible: legacy tokens without tenant_id work as before.
Only populated when user belongs to exactly one tenant (unambiguous).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 — M1: Endpoint `GET /me`

**Files:**
- Create: `apps/api/src/auth/dto/me-response.dto.ts` (tipo response)
- Modify: `apps/api/src/auth/auth.controller.ts` (aggiungi route GET /me)
- Modify: `apps/api/src/auth/auth.service.ts` (aggiungi metodo `resolveCurrentUser`)
- Test: `apps/api/src/auth/auth.controller.spec.ts`

- [ ] **Step 3.1: Crea DTO response**

File: `apps/api/src/auth/dto/me-response.dto.ts`

```typescript
export interface MeResponseDto {
  userId: string;
  email: string;
  fullName: string | null;
  tenantId: string | null;
  tenants: Array<{ id: string; name: string; role: string }>;
  enabledModules: string[];
  rolesByCompany: Record<string, string[]>;
}
```

- [ ] **Step 3.2: Scrivi test failing**

File: `apps/api/src/auth/auth.controller.spec.ts`

```typescript
describe('GET /me', () => {
  it('returns current user with tenants and enabled modules', async () => {
    const response = await request(app.getHttpServer())
      .get('/auth/me')
      .set('Authorization', `Bearer ${accessToken}`)
      .expect(200);

    expect(response.body).toHaveProperty('userId');
    expect(response.body).toHaveProperty('email');
    expect(response.body).toHaveProperty('tenants');
    expect(response.body).toHaveProperty('enabledModules');
    expect(Array.isArray(response.body.tenants)).toBe(true);
    expect(Array.isArray(response.body.enabledModules)).toBe(true);
  });

  it('returns 401 without auth header', async () => {
    await request(app.getHttpServer()).get('/auth/me').expect(401);
  });
});
```

- [ ] **Step 3.3: Run — atteso FAIL (route non esiste)**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_inspect/apps/api"
pnpm run test -- auth.controller.spec.ts -t "GET /me"
```

Expected: FAIL.

- [ ] **Step 3.4: Implementa `resolveCurrentUser` in auth.service.ts**

Aggiungi al `AuthService`:

```typescript
async resolveCurrentUser(userId: string): Promise<MeResponseDto> {
  const user = await this.prisma.user.findUnique({
    where: { id: userId },
    include: {
      tenantMemberships: {
        include: {
          tenant: {
            select: { id: true, name: true, moduleScope: true, modules: true },
          },
        },
      },
      studioMemberships: {
        select: { studioId: true, role: true },
      },
    },
  });

  if (!user) {
    throw new NotFoundException('User not found');
  }

  // Build tenants array
  const tenants = user.tenantMemberships.map((m) => ({
    id: m.tenant.id,
    name: m.tenant.name,
    role: m.role,
  }));

  // Build enabledModules from first/single tenant (if unambiguous)
  let enabledModules: string[] = [];
  let tenantId: string | null = null;
  if (tenants.length === 1) {
    tenantId = tenants[0].id;
    const tenant = user.tenantMemberships[0].tenant;
    enabledModules = this.extractModulesFromScope(tenant.moduleScope, tenant.modules);
  }

  // Build rolesByCompany (empty for now, placeholder for future)
  const rolesByCompany: Record<string, string[]> = {};

  return {
    userId: user.id,
    email: user.email,
    fullName: user.fullName ?? null,
    tenantId,
    tenants,
    enabledModules,
    rolesByCompany,
  };
}

private extractModulesFromScope(scope: string, modulesJson: any): string[] {
  // scope: "dvr" | "food-safety" | "both"
  // modulesJson: JSON field with additional modules (optional)
  const baseModules: string[] = [];
  if (scope === 'dvr' || scope === 'both') baseModules.push('dvr');
  if (scope === 'food-safety' || scope === 'both') baseModules.push('food-safety');

  if (modulesJson && typeof modulesJson === 'object') {
    for (const [key, enabled] of Object.entries(modulesJson)) {
      if (enabled === true && !baseModules.includes(key)) {
        baseModules.push(key);
      }
    }
  }

  return baseModules;
}
```

- [ ] **Step 3.5: Aggiungi route in auth.controller.ts**

```typescript
import { Get, UseGuards, Req } from '@nestjs/common';
import { JwtAuthGuard } from './guards/jwt-auth.guard';
import { MeResponseDto } from './dto/me-response.dto';

// dentro AuthController class

@Get('me')
@UseGuards(JwtAuthGuard)
async me(@Req() req: any): Promise<MeResponseDto> {
  return this.authService.resolveCurrentUser(req.user.sub);
}
```

- [ ] **Step 3.6: Run test — atteso PASS**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_inspect/apps/api"
pnpm run test -- auth.controller.spec.ts -t "GET /me"
```

Expected: 2/2 PASS.

- [ ] **Step 3.7: Commit**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_inspect"
git add apps/api/src/auth/
git commit -m "M1: Add GET /me endpoint with tenants and enabled modules

Returns resolved user context including tenantId (single-tenant users),
array of tenants, and enabledModules derived from moduleScope + modules JSON.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 — M6: `POST /client-app/compliance/modules/verify/:moduleKey`

**Files:**
- Modify: `apps/api/src/client-app/client-app.controller.ts` (aggiungi route)
- Modify: `apps/api/src/client-app/client-app.service.ts` (aggiungi `verifyModuleAccess`)
- Test: `apps/api/src/client-app/client-app.controller.spec.ts`

- [ ] **Step 4.1: Scrivi test failing**

Aggiungi al controller spec:

```typescript
describe('POST /client-app/compliance/modules/verify/:moduleKey', () => {
  it('returns 200 when module is enabled for tenant', async () => {
    // assume tenant has "noise" in modules JSON and dvr scope
    const tenant = await createTenantWithModules({ dvr: true, noise: true });
    const token = await issueTokenForTenant(tenant.id);

    await request(app.getHttpServer())
      .post('/client-app/compliance/modules/verify/noise')
      .set('Authorization', `Bearer ${token}`)
      .expect(200)
      .expect({ enabled: true, moduleKey: 'noise' });
  });

  it('returns 402 Payment Required when module not purchased', async () => {
    const tenant = await createTenantWithModules({ dvr: true }); // no "noise"
    const token = await issueTokenForTenant(tenant.id);

    await request(app.getHttpServer())
      .post('/client-app/compliance/modules/verify/noise')
      .set('Authorization', `Bearer ${token}`)
      .expect(402);
  });

  it('returns 403 when moduleKey is unknown', async () => {
    const tenant = await createTenantWithModules({ dvr: true });
    const token = await issueTokenForTenant(tenant.id);

    await request(app.getHttpServer())
      .post('/client-app/compliance/modules/verify/unknown-module')
      .set('Authorization', `Bearer ${token}`)
      .expect(403);
  });
});
```

- [ ] **Step 4.2: Run test — FAIL**

```bash
pnpm run test -- client-app.controller.spec.ts -t "verify"
```

- [ ] **Step 4.3: Implementa service method**

In `client-app.service.ts` aggiungi:

```typescript
private readonly KNOWN_MODULES = [
  'dvr',
  'food-safety',
  'noise',
  'vibrations',
  'chemical',
  'biological',
  'roa',
  'emf',
  'microclimate',
  'stress',
  'mmc',
  'videoterminals',
] as const;

async verifyModuleAccess(
  tenantId: string,
  moduleKey: string,
): Promise<{ status: 'enabled' | 'not-purchased' | 'unknown'; moduleKey: string }> {
  if (!this.KNOWN_MODULES.includes(moduleKey as any)) {
    return { status: 'unknown', moduleKey };
  }

  const tenant = await this.prisma.tenant.findUnique({
    where: { id: tenantId },
    select: { moduleScope: true, modules: true },
  });

  if (!tenant) {
    return { status: 'unknown', moduleKey };
  }

  // Base scope check (dvr / food-safety)
  if (moduleKey === 'dvr' && (tenant.moduleScope === 'dvr' || tenant.moduleScope === 'both')) {
    return { status: 'enabled', moduleKey };
  }
  if (moduleKey === 'food-safety' && (tenant.moduleScope === 'food-safety' || tenant.moduleScope === 'both')) {
    return { status: 'enabled', moduleKey };
  }

  // Extended modules in JSON field
  const modulesObj = (tenant.modules as Record<string, boolean>) ?? {};
  if (modulesObj[moduleKey] === true) {
    return { status: 'enabled', moduleKey };
  }

  return { status: 'not-purchased', moduleKey };
}
```

- [ ] **Step 4.4: Aggiungi route in controller**

```typescript
@Post('compliance/modules/verify/:moduleKey')
@UseGuards(JwtAuthGuard)
@HttpCode(HttpStatus.OK)
async verifyModule(
  @Param('moduleKey') moduleKey: string,
  @Req() req: any,
  @Res() res: Response,
) {
  const tenantId = req.user.tenantId;
  if (!tenantId) {
    return res.status(HttpStatus.CONFLICT).json({ error: 'Multi-tenant user, tenant required in request' });
  }

  const result = await this.clientAppService.verifyModuleAccess(tenantId, moduleKey);

  switch (result.status) {
    case 'enabled':
      return res.status(HttpStatus.OK).json({ enabled: true, moduleKey: result.moduleKey });
    case 'not-purchased':
      return res.status(HttpStatus.PAYMENT_REQUIRED).json({ enabled: false, moduleKey: result.moduleKey, reason: 'not-purchased' });
    case 'unknown':
      return res.status(HttpStatus.FORBIDDEN).json({ enabled: false, moduleKey: result.moduleKey, reason: 'unknown-module' });
  }
}
```

- [ ] **Step 4.5: Run test — atteso PASS**

```bash
pnpm run test -- client-app.controller.spec.ts -t "verify"
```

Expected: 3/3 PASS.

- [ ] **Step 4.6: Commit**

```bash
git add apps/api/src/client-app/
git commit -m "M6: Add POST /client-app/compliance/modules/verify/:moduleKey

Self-service endpoint for external modules to verify access.
Returns 200 (enabled), 402 (not purchased), 403 (unknown module).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 — M4: DVR Contract v1.1 schema + Zod

**Files:**
- Create: `packages/contracts/schemas/dvr.descriptor.v1.1.json` (JSON Schema v1.1)
- Modify: `packages/contracts/src/dvr-contract.ts` (aggiungi Zod type v1.1)
- Test: `packages/contracts/test/dvr-contract.test.ts`

- [ ] **Step 5.1: Leggi schema v1.0 esistente**

```bash
cat "C:/Users/Salvatore Romano/Desktop/MARS_inspect/packages/contracts/schemas/dvr.descriptor.v1.json" | head -100
```

Annota struttura principale.

- [ ] **Step 5.2: Crea schema v1.1 copiando v1.0 e aggiungendo module_extensions**

File: `packages/contracts/schemas/dvr.descriptor.v1.1.json`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://mars.local/schemas/dvr.descriptor.v1.1.json",
  "title": "DVR Descriptor v1.1",
  "description": "DVR generale con supporto moduli rischio specifici tramite module_extensions. Retrocompatibile con v1.0.",
  "type": "object",
  "required": ["schemaVersion", "companyData"],
  "properties": {
    "schemaVersion": { "type": "string", "const": "1.1.0" },
    "companyData": { "$ref": "./dvr.descriptor.v1.json#/properties/companyData" },
    "workPhases": { "$ref": "./dvr.descriptor.v1.json#/properties/workPhases" },
    "phaseEquipments": { "$ref": "./dvr.descriptor.v1.json#/properties/phaseEquipments" },
    "risks": { "$ref": "./dvr.descriptor.v1.json#/properties/risks" },
    "actions": { "$ref": "./dvr.descriptor.v1.json#/properties/actions" },
    "safetyRoles": { "$ref": "./dvr.descriptor.v1.json#/properties/safetyRoles" },
    "trainings": { "$ref": "./dvr.descriptor.v1.json#/properties/trainings" },
    "periodicChecks": { "$ref": "./dvr.descriptor.v1.json#/properties/periodicChecks" },
    "incidents": { "$ref": "./dvr.descriptor.v1.json#/properties/incidents" },
    "nearMisses": { "$ref": "./dvr.descriptor.v1.json#/properties/nearMisses" },
    "liftingEquipmentChecks": { "$ref": "./dvr.descriptor.v1.json#/properties/liftingEquipmentChecks" },
    "dpiAssignments": { "$ref": "./dvr.descriptor.v1.json#/properties/dpiAssignments" },
    "module_extensions": {
      "type": "object",
      "description": "Dati specifici per ogni modulo rischio attivo. Chiavi dinamiche = moduleKey (noise, vibrations, chemical, ecc.)",
      "additionalProperties": {
        "type": "object",
        "required": ["module_version", "last_sync_at"],
        "properties": {
          "module_version": {
            "type": "string",
            "pattern": "^\\d+\\.\\d+\\.\\d+$",
            "description": "Versione del modulo che ha scritto i dati (semver)"
          },
          "assessment_context_id": {
            "type": "string",
            "format": "uuid",
            "description": "ID interno del modulo per questa assessment"
          },
          "summary": {
            "type": "object",
            "description": "Riepilogo dati modulo per export convenience",
            "additionalProperties": true
          },
          "last_sync_at": {
            "type": "string",
            "format": "date-time",
            "description": "Ultimo sync del modulo verso MARS"
          },
          "data": {
            "type": "object",
            "description": "Payload completo modulo-specifico",
            "additionalProperties": true
          }
        }
      }
    }
  }
}
```

- [ ] **Step 5.3: Scrivi test Zod per v1.1**

File: `packages/contracts/test/dvr-contract.test.ts`

```typescript
import { describe, it, expect } from 'vitest';
import { DvrDescriptorV11Schema, DvrDescriptorV1Schema } from '../src/dvr-contract';

describe('DVR Descriptor v1.1', () => {
  it('parses a minimal v1.1 document with module_extensions', () => {
    const doc = {
      schemaVersion: '1.1.0',
      companyData: {
        vatNumber: '12345678901',
        legalName: 'ACME Srl',
        atecoCode: '62.02.00',
      },
      module_extensions: {
        noise: {
          module_version: '0.1.0',
          assessment_context_id: '550e8400-e29b-41d4-a716-446655440000',
          last_sync_at: '2026-04-17T10:00:00Z',
          summary: { lex_8h: 85.2, risk_band: 'ORANGE' },
          data: { phases: [] },
        },
      },
    };

    const result = DvrDescriptorV11Schema.safeParse(doc);
    expect(result.success).toBe(true);
  });

  it('rejects v1.1 document with invalid module_version format', () => {
    const doc = {
      schemaVersion: '1.1.0',
      companyData: { vatNumber: '12345678901', legalName: 'A', atecoCode: '62.02.00' },
      module_extensions: {
        noise: {
          module_version: 'invalid',
          last_sync_at: '2026-04-17T10:00:00Z',
        },
      },
    };

    const result = DvrDescriptorV11Schema.safeParse(doc);
    expect(result.success).toBe(false);
  });

  it('accepts v1.1 without module_extensions (backward compat with v1.0 shape)', () => {
    const doc = {
      schemaVersion: '1.1.0',
      companyData: { vatNumber: '12345678901', legalName: 'A', atecoCode: '62.02.00' },
    };

    const result = DvrDescriptorV11Schema.safeParse(doc);
    expect(result.success).toBe(true);
  });

  it('v1.0 parser ignores module_extensions (forward compat)', () => {
    const doc = {
      schemaVersion: '1.0.0',
      companyData: { vatNumber: '12345678901', legalName: 'A', atecoCode: '62.02.00' },
    };

    const result = DvrDescriptorV1Schema.safeParse(doc);
    expect(result.success).toBe(true);
  });
});
```

- [ ] **Step 5.4: Run — atteso FAIL (type v1.1 non esiste)**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_inspect/packages/contracts"
pnpm run test
```

- [ ] **Step 5.5: Aggiungi Zod type v1.1**

File: `packages/contracts/src/dvr-contract.ts`

Aggiungi in coda al file:

```typescript
import { z } from 'zod';

// ... existing DvrDescriptorV1Schema ...

const ModuleExtensionSchema = z.object({
  module_version: z.string().regex(/^\d+\.\d+\.\d+$/, 'Must be semver format X.Y.Z'),
  assessment_context_id: z.string().uuid().optional(),
  summary: z.record(z.unknown()).optional(),
  last_sync_at: z.string().datetime(),
  data: z.record(z.unknown()).optional(),
});

export const DvrDescriptorV11Schema = z.object({
  schemaVersion: z.literal('1.1.0'),
  companyData: DvrCompanyDataSchema,  // same as v1.0
  workPhases: z.array(WorkPhaseSchema).optional(),
  phaseEquipments: z.array(PhaseEquipmentSchema).optional(),
  risks: z.array(RiskSchema).optional(),
  actions: z.array(ActionSchema).optional(),
  safetyRoles: z.array(SafetyRoleSchema).optional(),
  trainings: z.array(TrainingSchema).optional(),
  periodicChecks: z.array(PeriodicCheckSchema).optional(),
  incidents: z.array(IncidentSchema).optional(),
  nearMisses: z.array(NearMissSchema).optional(),
  liftingEquipmentChecks: z.array(LiftingEquipmentCheckSchema).optional(),
  dpiAssignments: z.array(DpiAssignmentSchema).optional(),
  module_extensions: z.record(ModuleExtensionSchema).optional(),
});

export type DvrDescriptorV11 = z.infer<typeof DvrDescriptorV11Schema>;

// Union type for parsers that accept either version
export const DvrDescriptorSchema = z.discriminatedUnion('schemaVersion', [
  DvrDescriptorV1Schema,
  DvrDescriptorV11Schema,
]);
export type DvrDescriptor = z.infer<typeof DvrDescriptorSchema>;
```

**Nota**: Se i types `DvrCompanyDataSchema`, `WorkPhaseSchema` ecc. non esistono ancora come Zod schemas ma sono definiti solo come TypeScript types, estraili dal JSON Schema v1.0 usando una libreria come `json-schema-to-zod` oppure definiscili a mano partendo dal JSON Schema `dvr.descriptor.v1.json`. Verificare file esistente prima di inventare.

- [ ] **Step 5.6: Re-run test — atteso PASS**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_inspect/packages/contracts"
pnpm run test
```

Expected: 4/4 PASS.

- [ ] **Step 5.7: Export type da index**

File: `packages/contracts/src/index.ts`

```typescript
export * from './dvr-contract';  // già dovrebbe esserci, verifica export DvrDescriptorV11 + DvrDescriptorSchema
```

- [ ] **Step 5.8: Commit**

```bash
git add packages/contracts/
git commit -m "M4: Add DVR contract schema v1.1 with module_extensions

Backward compatible: v1.0 parser ignores module_extensions;
v1.1 parser accepts absence of module_extensions.
Zod schema with discriminatedUnion for version-agnostic parsing.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6 — M3: `PUT /dvr-documents/:d/revisions/:r/module-extensions/:key`

**Files:**
- Modify: `apps/api/src/dvr-documents/dvr-documents.controller.ts` (aggiungi route)
- Modify: `apps/api/src/dvr-documents/dvr-documents.service.ts` (aggiungi `updateModuleExtension`)
- Modify: `apps/api/prisma/schema.prisma` (aggiungi campo `snapshot_version` a `DvrDocumentRevision` se manca)
- Create: migration Prisma per version column se manca
- Test: `apps/api/src/dvr-documents/dvr-documents.controller.spec.ts`

- [ ] **Step 6.1: Verifica schema Prisma per optimistic lock**

```bash
grep -A 20 "model DvrDocumentRevision" "C:/Users/Salvatore Romano/Desktop/MARS_inspect/apps/api/prisma/schema.prisma"
```

Verifica se esiste `updatedAt` DateTime o `version` Int. Se c'è `updatedAt`, lo usiamo come lock token. Altrimenti aggiungi `version Int @default(1)`.

- [ ] **Step 6.2: Se necessario, aggiungi `version Int` al model Prisma**

Solo se manca. File: `apps/api/prisma/schema.prisma`

Nel model `DvrDocumentRevision`:
```
version Int @default(1)
```

Genera migration:
```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_inspect/apps/api"
pnpm prisma migrate dev --name add_revision_version_for_optimistic_lock
```

- [ ] **Step 6.3: Scrivi test failing**

Aggiungi a `dvr-documents.controller.spec.ts`:

```typescript
describe('PUT /dvr-documents/:d/revisions/:r/module-extensions/:key', () => {
  let revision;
  let token;

  beforeEach(async () => {
    revision = await createRevisionWithSnapshot();
    token = await issueTokenForTenant(revision.tenantId);
  });

  it('updates module_extensions.noise in snapshot', async () => {
    const payload = {
      module_version: '0.1.0',
      assessment_context_id: '550e8400-e29b-41d4-a716-446655440000',
      last_sync_at: '2026-04-17T10:00:00Z',
      summary: { lex_8h: 85.2, risk_band: 'ORANGE' },
      data: { phases: [] },
    };

    const response = await request(app.getHttpServer())
      .put(`/dvr-documents/${revision.documentId}/revisions/${revision.id}/module-extensions/noise`)
      .set('Authorization', `Bearer ${token}`)
      .set('If-Match', String(revision.version))
      .send(payload)
      .expect(200);

    expect(response.body.version).toBe(revision.version + 1);

    const updated = await prisma.dvrDocumentRevision.findUnique({ where: { id: revision.id } });
    expect(updated!.snapshot.module_extensions.noise.summary.lex_8h).toBe(85.2);
  });

  it('returns 409 Conflict when If-Match version mismatch', async () => {
    await request(app.getHttpServer())
      .put(`/dvr-documents/${revision.documentId}/revisions/${revision.id}/module-extensions/noise`)
      .set('Authorization', `Bearer ${token}`)
      .set('If-Match', '999')  // wrong version
      .send({ module_version: '0.1.0', last_sync_at: '2026-04-17T10:00:00Z' })
      .expect(409);
  });

  it('returns 400 if moduleKey not enabled for tenant', async () => {
    // create tenant without noise module
    const otherRev = await createRevisionWithSnapshot({ enableModules: ['dvr'] });
    const otherToken = await issueTokenForTenant(otherRev.tenantId);

    await request(app.getHttpServer())
      .put(`/dvr-documents/${otherRev.documentId}/revisions/${otherRev.id}/module-extensions/noise`)
      .set('Authorization', `Bearer ${otherToken}`)
      .set('If-Match', String(otherRev.version))
      .send({ module_version: '0.1.0', last_sync_at: '2026-04-17T10:00:00Z' })
      .expect(402);  // not purchased
  });
});
```

- [ ] **Step 6.4: Run — atteso FAIL**

```bash
pnpm run test -- dvr-documents.controller.spec.ts -t "module-extensions"
```

- [ ] **Step 6.5: Implementa service method**

In `dvr-documents.service.ts` aggiungi:

```typescript
async updateModuleExtension(
  documentId: string,
  revisionId: string,
  moduleKey: string,
  payload: unknown,
  expectedVersion: number,
  tenantId: string,
): Promise<{ version: number; updatedAt: Date }> {
  // 1. Verify module enabled for tenant
  const moduleAccess = await this.clientAppService.verifyModuleAccess(tenantId, moduleKey);
  if (moduleAccess.status !== 'enabled') {
    throw new PaymentRequiredException(`Module '${moduleKey}' not enabled for tenant`);
  }

  // 2. Validate payload against ModuleExtensionSchema
  const parseResult = ModuleExtensionSchema.safeParse(payload);
  if (!parseResult.success) {
    throw new BadRequestException({
      message: 'Invalid module extension payload',
      errors: parseResult.error.flatten(),
    });
  }

  // 3. Optimistic lock: atomic update with version check
  const result = await this.prisma.$transaction(async (tx) => {
    const current = await tx.dvrDocumentRevision.findUnique({
      where: { id: revisionId },
      select: { id: true, version: true, snapshot: true, documentId: true, tenantId: true },
    });

    if (!current || current.documentId !== documentId || current.tenantId !== tenantId) {
      throw new NotFoundException('Revision not found');
    }

    if (current.version !== expectedVersion) {
      throw new ConflictException({
        message: 'Version conflict',
        currentVersion: current.version,
        expectedVersion,
      });
    }

    // Merge module_extensions[moduleKey] into snapshot
    const snapshot = (current.snapshot as any) ?? {};
    snapshot.schemaVersion = snapshot.schemaVersion ?? '1.1.0';
    snapshot.module_extensions = snapshot.module_extensions ?? {};
    snapshot.module_extensions[moduleKey] = parseResult.data;

    const updated = await tx.dvrDocumentRevision.update({
      where: { id: revisionId },
      data: {
        snapshot,
        version: { increment: 1 },
      },
      select: { version: true, updatedAt: true },
    });

    // 4. Audit log
    await tx.dvrRevisionAuditLog.create({
      data: {
        revisionId,
        action: 'module_extension_updated',
        actorUserId: null,  // systemic; module can provide header later
        details: { moduleKey, version_before: expectedVersion, version_after: updated.version },
      },
    });

    return updated;
  });

  // 5. Fire webhook event (M7 will implement; here just emit intent)
  this.eventEmitter.emit('dvr.revision.module_extension.updated', {
    documentId,
    revisionId,
    moduleKey,
    tenantId,
    timestamp: new Date().toISOString(),
  });

  return result;
}
```

- [ ] **Step 6.6: Aggiungi route in controller**

```typescript
@Put(':documentId/revisions/:revisionId/module-extensions/:moduleKey')
@UseGuards(JwtAuthGuard)
async updateModuleExtension(
  @Param('documentId') documentId: string,
  @Param('revisionId') revisionId: string,
  @Param('moduleKey') moduleKey: string,
  @Body() payload: unknown,
  @Headers('if-match') ifMatch: string,
  @Req() req: any,
) {
  if (!ifMatch) {
    throw new BadRequestException('If-Match header required for optimistic lock');
  }
  const expectedVersion = parseInt(ifMatch, 10);
  if (Number.isNaN(expectedVersion)) {
    throw new BadRequestException('If-Match must be a valid version number');
  }

  return this.dvrDocumentsService.updateModuleExtension(
    documentId,
    revisionId,
    moduleKey,
    payload,
    expectedVersion,
    req.user.tenantId,
  );
}
```

- [ ] **Step 6.7: Run — atteso PASS**

```bash
pnpm run test -- dvr-documents.controller.spec.ts -t "module-extensions"
```

Expected: 3/3 PASS.

- [ ] **Step 6.8: Commit**

```bash
git add apps/api/src/dvr-documents/ apps/api/prisma/
git commit -m "M3: Add PUT /dvr-documents/:d/revisions/:r/module-extensions/:key

Optimistic lock via If-Match header with revision version.
Validates module access (enabled for tenant via M6).
Merges payload into snapshot.module_extensions[moduleKey].
Increments version, logs audit entry, emits event.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7 — M2: `POST /modules/:key/register-session`

**Files:**
- Create: `apps/api/src/modules/modules.controller.ts`
- Create: `apps/api/src/modules/modules.service.ts`
- Create: `apps/api/src/modules/modules.module.ts`
- Modify: `apps/api/src/app.module.ts` (import ModulesModule)
- Modify: `apps/api/prisma/schema.prisma` (aggiungi model `ModuleSession`)
- Test: `apps/api/src/modules/modules.controller.spec.ts`

- [ ] **Step 7.1: Aggiungi model Prisma**

File: `apps/api/prisma/schema.prisma` (append)

```prisma
model ModuleSession {
  id              String   @id @default(uuid())
  moduleKey       String
  tenantId        String
  userId          String
  dvrDocumentId   String
  revisionId      String
  revisionVersion Int
  startedAt       DateTime @default(now())
  lastHeartbeatAt DateTime @default(now())
  endedAt         DateTime?

  @@index([tenantId, revisionId])
  @@index([moduleKey, startedAt])
}
```

Genera migration:
```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_inspect/apps/api"
pnpm prisma migrate dev --name add_module_session
```

- [ ] **Step 7.2: Scrivi test failing**

File: `apps/api/src/modules/modules.controller.spec.ts`

```typescript
describe('POST /modules/:key/register-session', () => {
  it('creates a session and returns session_id + revision info', async () => {
    const revision = await createRevisionWithSnapshot();
    const token = await issueTokenForTenant(revision.tenantId);

    const response = await request(app.getHttpServer())
      .post('/modules/noise/register-session')
      .set('Authorization', `Bearer ${token}`)
      .send({ documentId: revision.documentId, revisionId: revision.id })
      .expect(201);

    expect(response.body).toMatchObject({
      sessionId: expect.any(String),
      moduleKey: 'noise',
      revisionVersion: revision.version,
      startedAt: expect.any(String),
    });
  });

  it('returns 402 if module not enabled', async () => {
    const revision = await createRevisionWithSnapshot({ enableModules: ['dvr'] });
    const token = await issueTokenForTenant(revision.tenantId);

    await request(app.getHttpServer())
      .post('/modules/noise/register-session')
      .set('Authorization', `Bearer ${token}`)
      .send({ documentId: revision.documentId, revisionId: revision.id })
      .expect(402);
  });
});
```

- [ ] **Step 7.3: Crea service**

File: `apps/api/src/modules/modules.service.ts`

```typescript
import { Injectable, NotFoundException, PaymentRequiredException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { ClientAppService } from '../client-app/client-app.service';

@Injectable()
export class ModulesService {
  constructor(
    private prisma: PrismaService,
    private clientAppService: ClientAppService,
  ) {}

  async registerSession(
    moduleKey: string,
    tenantId: string,
    userId: string,
    documentId: string,
    revisionId: string,
  ) {
    // 1. Verify module access
    const access = await this.clientAppService.verifyModuleAccess(tenantId, moduleKey);
    if (access.status !== 'enabled') {
      throw new PaymentRequiredException(`Module '${moduleKey}' not enabled`);
    }

    // 2. Load revision to get current version
    const revision = await this.prisma.dvrDocumentRevision.findFirst({
      where: { id: revisionId, documentId, tenantId },
      select: { id: true, version: true },
    });
    if (!revision) {
      throw new NotFoundException('Revision not found');
    }

    // 3. Create session
    const session = await this.prisma.moduleSession.create({
      data: {
        moduleKey,
        tenantId,
        userId,
        dvrDocumentId: documentId,
        revisionId,
        revisionVersion: revision.version,
      },
    });

    return {
      sessionId: session.id,
      moduleKey,
      revisionVersion: revision.version,
      startedAt: session.startedAt.toISOString(),
    };
  }

  async heartbeat(sessionId: string, tenantId: string) {
    await this.prisma.moduleSession.update({
      where: { id: sessionId, tenantId } as any,
      data: { lastHeartbeatAt: new Date() },
    });
  }

  async endSession(sessionId: string, tenantId: string) {
    await this.prisma.moduleSession.update({
      where: { id: sessionId, tenantId } as any,
      data: { endedAt: new Date() },
    });
  }
}
```

- [ ] **Step 7.4: Crea controller**

File: `apps/api/src/modules/modules.controller.ts`

```typescript
import { Body, Controller, HttpCode, Param, Post, Req, UseGuards } from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { z } from 'zod';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { ModulesService } from './modules.service';

const RegisterSessionBodySchema = z.object({
  documentId: z.string().uuid(),
  revisionId: z.string().uuid(),
});

@ApiTags('modules')
@Controller('modules')
export class ModulesController {
  constructor(private readonly modulesService: ModulesService) {}

  @Post(':moduleKey/register-session')
  @UseGuards(JwtAuthGuard)
  @HttpCode(201)
  async register(
    @Param('moduleKey') moduleKey: string,
    @Body() body: unknown,
    @Req() req: any,
  ) {
    const parsed = RegisterSessionBodySchema.parse(body);
    return this.modulesService.registerSession(
      moduleKey,
      req.user.tenantId,
      req.user.sub,
      parsed.documentId,
      parsed.revisionId,
    );
  }

  @Post('sessions/:sessionId/heartbeat')
  @UseGuards(JwtAuthGuard)
  @HttpCode(204)
  async heartbeat(@Param('sessionId') sessionId: string, @Req() req: any) {
    await this.modulesService.heartbeat(sessionId, req.user.tenantId);
  }

  @Post('sessions/:sessionId/end')
  @UseGuards(JwtAuthGuard)
  @HttpCode(204)
  async end(@Param('sessionId') sessionId: string, @Req() req: any) {
    await this.modulesService.endSession(sessionId, req.user.tenantId);
  }
}
```

- [ ] **Step 7.5: Crea module file**

File: `apps/api/src/modules/modules.module.ts`

```typescript
import { Module } from '@nestjs/common';
import { ModulesController } from './modules.controller';
import { ModulesService } from './modules.service';
import { PrismaModule } from '../prisma/prisma.module';
import { ClientAppModule } from '../client-app/client-app.module';

@Module({
  imports: [PrismaModule, ClientAppModule],
  controllers: [ModulesController],
  providers: [ModulesService],
  exports: [ModulesService],
})
export class ModulesModule {}
```

- [ ] **Step 7.6: Registra in app.module.ts**

File: `apps/api/src/app.module.ts`

```typescript
import { ModulesModule } from './modules/modules.module';

@Module({
  imports: [
    // ... existing imports
    ModulesModule,
  ],
})
export class AppModule {}
```

- [ ] **Step 7.7: Run test — atteso PASS**

```bash
pnpm run test -- modules.controller.spec.ts
```

Expected: 2/2 PASS.

- [ ] **Step 7.8: Commit**

```bash
git add apps/api/src/modules/ apps/api/src/app.module.ts apps/api/prisma/
git commit -m "M2: Add POST /modules/:key/register-session with heartbeat + end

Session tracking for module integrations. Optimistic lock primitive
(via revisionVersion snapshot). Module can call heartbeat every 30s
and end on UI close.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8 — M7: Webhook outbound eventi DVR

**Files:**
- Create: `apps/api/src/dvr-documents/events/events.service.ts`
- Create: `apps/api/src/dvr-documents/events/events.module.ts`
- Modify: `apps/api/src/dvr-documents/dvr-documents.service.ts` (emit events)
- Modify: `apps/api/.env.example` (aggiungi `MODULE_EVENTS_WEBHOOK_URL`, `MODULE_EVENTS_WEBHOOK_SECRET`)
- Test: `apps/api/src/dvr-documents/events/events.service.spec.ts`

- [ ] **Step 8.1: Aggiungi env vars**

File: `apps/api/.env.example` — append:

```bash
# M7: Webhook outbound for module events (optional)
# When set, MARS POSTs DVR revision events to this URL with HMAC signature.
MODULE_EVENTS_WEBHOOK_URL=
MODULE_EVENTS_WEBHOOK_SECRET=replace_me_hmac_shared_secret
MODULE_EVENTS_WEBHOOK_TIMEOUT_MS=5000
```

- [ ] **Step 8.2: Scrivi test failing**

File: `apps/api/src/dvr-documents/events/events.service.spec.ts`

```typescript
import { Test } from '@nestjs/testing';
import { EventsService } from './events.service';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { of } from 'rxjs';

describe('EventsService', () => {
  let service: EventsService;
  let httpService: { post: jest.Mock };

  beforeEach(async () => {
    httpService = { post: jest.fn().mockReturnValue(of({ data: 'ok' })) };
    const config = { get: jest.fn((key) => {
      if (key === 'MODULE_EVENTS_WEBHOOK_URL') return 'https://module.example/webhook';
      if (key === 'MODULE_EVENTS_WEBHOOK_SECRET') return 'test-secret';
      if (key === 'MODULE_EVENTS_WEBHOOK_TIMEOUT_MS') return 5000;
    }) };

    const moduleRef = await Test.createTestingModule({
      providers: [
        EventsService,
        { provide: HttpService, useValue: httpService },
        { provide: ConfigService, useValue: config },
      ],
    }).compile();

    service = moduleRef.get(EventsService);
  });

  it('sends event with HMAC-SHA256 signature header', async () => {
    const event = {
      eventType: 'revision.updated',
      documentId: 'doc-1',
      revisionId: 'rev-1',
      tenantId: 't-1',
      timestamp: '2026-04-17T10:00:00Z',
      changedFields: ['module_extensions.noise'],
    };

    await service.dispatch(event);

    expect(httpService.post).toHaveBeenCalledWith(
      'https://module.example/webhook',
      event,
      expect.objectContaining({
        headers: expect.objectContaining({
          'X-MARS-Signature': expect.stringMatching(/^sha256=[a-f0-9]{64}$/),
          'X-MARS-Event': 'revision.updated',
          'Content-Type': 'application/json',
        }),
        timeout: 5000,
      }),
    );
  });

  it('skips dispatch when MODULE_EVENTS_WEBHOOK_URL is empty', async () => {
    const configEmpty = { get: jest.fn(() => '') };
    const moduleRef = await Test.createTestingModule({
      providers: [
        EventsService,
        { provide: HttpService, useValue: httpService },
        { provide: ConfigService, useValue: configEmpty },
      ],
    }).compile();
    const emptyService = moduleRef.get(EventsService);

    await emptyService.dispatch({ eventType: 'any' } as any);
    expect(httpService.post).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 8.3: Run — FAIL**

```bash
pnpm run test -- events.service.spec.ts
```

- [ ] **Step 8.4: Implementa EventsService**

File: `apps/api/src/dvr-documents/events/events.service.ts`

```typescript
import { Injectable, Logger } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { firstValueFrom } from 'rxjs';
import * as crypto from 'crypto';

export interface DvrEvent {
  eventType: 'revision.updated' | 'revision.published' | 'revision.archived' | 'revision.module_extension.updated';
  documentId: string;
  revisionId: string;
  tenantId: string;
  timestamp: string;
  changedFields?: string[];
  metadata?: Record<string, unknown>;
}

@Injectable()
export class EventsService {
  private readonly logger = new Logger(EventsService.name);

  constructor(
    private readonly httpService: HttpService,
    private readonly config: ConfigService,
  ) {}

  async dispatch(event: DvrEvent): Promise<void> {
    const url = this.config.get<string>('MODULE_EVENTS_WEBHOOK_URL');
    if (!url) {
      this.logger.debug(`No webhook URL; skipping event ${event.eventType}`);
      return;
    }

    const secret = this.config.get<string>('MODULE_EVENTS_WEBHOOK_SECRET') || '';
    const timeout = Number(this.config.get('MODULE_EVENTS_WEBHOOK_TIMEOUT_MS')) || 5000;

    const body = JSON.stringify(event);
    const signature = crypto
      .createHmac('sha256', secret)
      .update(body)
      .digest('hex');

    try {
      await firstValueFrom(
        this.httpService.post(url, event, {
          headers: {
            'Content-Type': 'application/json',
            'X-MARS-Signature': `sha256=${signature}`,
            'X-MARS-Event': event.eventType,
            'X-MARS-Delivery': crypto.randomUUID(),
          },
          timeout,
        }),
      );
      this.logger.log(`Dispatched event ${event.eventType} for revision ${event.revisionId}`);
    } catch (err: any) {
      this.logger.error(`Webhook dispatch failed: ${err.message}`, err.stack);
      // Do not throw; webhook is best-effort
    }
  }
}
```

- [ ] **Step 8.5: Crea events.module.ts**

```typescript
import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { EventsService } from './events.service';

@Module({
  imports: [HttpModule],
  providers: [EventsService],
  exports: [EventsService],
})
export class EventsModule {}
```

- [ ] **Step 8.6: Wire EventsService in DvrDocumentsService**

In `dvr-documents.service.ts`:

```typescript
import { EventsService } from './events/events.service';

// inject in constructor
constructor(
  private prisma: PrismaService,
  private eventsService: EventsService,
  // ... existing
) {}

// replace eventEmitter.emit calls with:
await this.eventsService.dispatch({
  eventType: 'revision.module_extension.updated',
  documentId,
  revisionId,
  tenantId,
  timestamp: new Date().toISOString(),
  changedFields: [`module_extensions.${moduleKey}`],
});
```

Aggiungi `EventsModule` agli imports del `DvrDocumentsModule`.

- [ ] **Step 8.7: Run test — PASS**

```bash
pnpm run test -- events.service.spec.ts
pnpm run test -- dvr-documents
```

Expected: tutti PASS, no regressioni.

- [ ] **Step 8.8: Commit**

```bash
git add apps/api/src/dvr-documents/events/ apps/api/src/dvr-documents/dvr-documents.service.ts apps/api/.env.example
git commit -m "M7: Add webhook outbound service for DVR revision events

Fires POST to MODULE_EVENTS_WEBHOOK_URL with HMAC-SHA256 signature
on revision.updated, revision.published, revision.archived,
revision.module_extension.updated. Best-effort (no retry, no throw).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9 — M8: `ModuleFrame.tsx` in apps/web

**Files:**
- Create: `apps/web/src/components/modules/ModuleFrame.tsx`
- Create: `apps/web/src/components/modules/useModulePostMessage.ts`
- Modify: `apps/web/.env.example` (VITE_NOISE_MODULE_URL)
- Test: `apps/web/src/components/modules/__tests__/ModuleFrame.test.tsx`

- [ ] **Step 9.1: Crea hook postMessage**

File: `apps/web/src/components/modules/useModulePostMessage.ts`

```typescript
import { useEffect, useRef } from 'react';

export interface ModuleMessage {
  type: 'close' | 'refresh' | 'ready' | 'error';
  payload?: unknown;
}

export function useModulePostMessage(
  iframeRef: React.RefObject<HTMLIFrameElement>,
  expectedOrigin: string,
  onMessage: (msg: ModuleMessage) => void,
) {
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    function handler(ev: MessageEvent) {
      if (ev.origin !== expectedOrigin) return;
      if (typeof ev.data !== 'object' || !ev.data || !('type' in ev.data)) return;
      onMessageRef.current(ev.data as ModuleMessage);
    }
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, [expectedOrigin]);

  function post(msg: ModuleMessage) {
    iframeRef.current?.contentWindow?.postMessage(msg, expectedOrigin);
  }

  return { post };
}
```

- [ ] **Step 9.2: Crea ModuleFrame**

File: `apps/web/src/components/modules/ModuleFrame.tsx`

```typescript
import { useEffect, useRef, useState } from 'react';
import { useModulePostMessage } from './useModulePostMessage';

export interface ModuleFrameProps {
  moduleKey: 'noise' | 'vibrations' | 'chemical' | string;
  moduleUrl: string;
  dvrDocumentId: string;
  revisionId: string;
  accessToken: string;
  onClose: () => void;
}

export function ModuleFrame({
  moduleKey,
  moduleUrl,
  dvrDocumentId,
  revisionId,
  accessToken,
  onClose,
}: ModuleFrameProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [iframeReady, setIframeReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const expectedOrigin = new URL(moduleUrl).origin;

  const { post } = useModulePostMessage(iframeRef, expectedOrigin, (msg) => {
    switch (msg.type) {
      case 'ready':
        setIframeReady(true);
        // Send bootstrap payload once iframe signals ready
        post({
          type: 'ready',
          payload: {
            moduleKey,
            dvrDocumentId,
            revisionId,
            accessToken,
            marsApiBaseUrl: window.location.origin,
          } as any,
        } as any);
        break;
      case 'close':
        onClose();
        break;
      case 'refresh':
        // Parent may want to refetch DVR snapshot
        window.dispatchEvent(new CustomEvent('mars:dvr:refresh', { detail: { revisionId } }));
        break;
      case 'error':
        setError(String((msg.payload as any)?.message ?? 'Module error'));
        break;
    }
  });

  // Fallback: after 10s without ready, show error
  useEffect(() => {
    if (iframeReady) return;
    const timer = setTimeout(() => {
      if (!iframeReady) setError('Module did not respond in 10 seconds');
    }, 10_000);
    return () => clearTimeout(timer);
  }, [iframeReady]);

  return (
    <div className="module-frame-overlay" role="dialog" aria-modal="true">
      <div className="module-frame-header">
        <h2>Modulo {moduleKey}</h2>
        <button onClick={onClose} aria-label="Chiudi modulo">×</button>
      </div>
      {error && <div className="module-frame-error">{error}</div>}
      <iframe
        ref={iframeRef}
        src={moduleUrl}
        title={`Modulo ${moduleKey}`}
        className="module-frame-iframe"
        sandbox="allow-scripts allow-same-origin allow-forms allow-downloads"
        allow="clipboard-read; clipboard-write"
      />
    </div>
  );
}
```

- [ ] **Step 9.3: Aggiungi CSS basic**

File: `apps/web/src/components/modules/ModuleFrame.css`

```css
.module-frame-overlay {
  position: fixed;
  inset: 0;
  background: #fff;
  display: flex;
  flex-direction: column;
  z-index: 9999;
}
.module-frame-header {
  display: flex;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid #e5e7eb;
}
.module-frame-header h2 {
  margin: 0;
  font-size: 16px;
}
.module-frame-header button {
  background: transparent;
  border: none;
  font-size: 24px;
  cursor: pointer;
  line-height: 1;
}
.module-frame-iframe {
  flex: 1;
  width: 100%;
  border: 0;
}
.module-frame-error {
  background: #fee2e2;
  color: #991b1b;
  padding: 10px 20px;
}
```

Importa il CSS in ModuleFrame.tsx:
```typescript
import './ModuleFrame.css';
```

- [ ] **Step 9.4: Env var per URL modulo Rumore**

File: `apps/web/.env.example` — append:

```
VITE_NOISE_MODULE_URL=http://localhost:8085
VITE_VIBRATIONS_MODULE_URL=
```

- [ ] **Step 9.5: Test componente con vitest + testing-library**

File: `apps/web/src/components/modules/__tests__/ModuleFrame.test.tsx`

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { ModuleFrame } from '../ModuleFrame';

describe('ModuleFrame', () => {
  it('renders iframe with correct src', () => {
    const { container } = render(
      <ModuleFrame
        moduleKey="noise"
        moduleUrl="http://localhost:8085"
        dvrDocumentId="doc1"
        revisionId="rev1"
        accessToken="token"
        onClose={vi.fn()}
      />,
    );

    const iframe = container.querySelector('iframe');
    expect(iframe).not.toBeNull();
    expect(iframe?.getAttribute('src')).toBe('http://localhost:8085');
    expect(iframe?.getAttribute('sandbox')).toContain('allow-scripts');
  });

  it('calls onClose when close button clicked', async () => {
    const onClose = vi.fn();
    const { getByLabelText } = render(
      <ModuleFrame
        moduleKey="noise"
        moduleUrl="http://localhost:8085"
        dvrDocumentId="doc1"
        revisionId="rev1"
        accessToken="token"
        onClose={onClose}
      />,
    );

    getByLabelText('Chiudi modulo').click();
    expect(onClose).toHaveBeenCalled();
  });
});
```

- [ ] **Step 9.6: Run test**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_inspect/apps/web"
pnpm run test -- ModuleFrame.test
```

Expected: 2/2 PASS.

- [ ] **Step 9.7: Commit**

```bash
git add apps/web/src/components/modules/ apps/web/.env.example
git commit -m "M8: Add ModuleFrame component for iframe module embedding

Renders module iframe with postMessage handshake.
Parent sends accessToken + DVR context after child signals 'ready'.
Sandbox attributes limit permissions.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10 — M9: ATECO 2025 PDF → JSON → Prisma seed

**Files:**
- Create: `apps/api/scripts/parse-ateco-pdf.ts` (one-off script)
- Create: `apps/api/prisma/seeds/ateco_2025.json` (output of parse)
- Create: `apps/api/prisma/seeds/ateco_2025.ts` (seed runner)
- Modify: `apps/api/prisma/schema.prisma` (model `AtecoCode` se manca)
- Modify: `apps/api/package.json` (script `seed:ateco-2025`)
- Test: `apps/api/scripts/parse-ateco-pdf.test.ts`

- [ ] **Step 10.1: Verifica/aggiungi model Prisma**

```bash
grep -A 10 "model AtecoCode" "C:/Users/Salvatore Romano/Desktop/MARS_inspect/apps/api/prisma/schema.prisma"
```

Se non esiste, aggiungi a `schema.prisma`:

```prisma
model AtecoCode {
  code        String   @id
  description String
  sector      String
  macro       String   // A-U
  parentCode  String?
  version     String   @default("2025")
  createdAt   DateTime @default(now())

  @@index([sector])
  @@index([macro])
  @@index([version])
}
```

Migration:
```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_inspect/apps/api"
pnpm prisma migrate dev --name add_ateco_code_v2025
```

- [ ] **Step 10.2: Scrivi parser PDF test-first**

File: `apps/api/scripts/parse-ateco-pdf.test.ts`

```typescript
import { describe, it, expect } from 'vitest';
import { parseAtecoPdf } from './parse-ateco-pdf';
import * as path from 'path';

describe('parseAtecoPdf', () => {
  it('extracts at least 600 ATECO 2025 codes from PDF', async () => {
    const pdfPath = path.join(__dirname, '../../../Struttura-ATECO-2025-italiano.pdf');
    const codes = await parseAtecoPdf(pdfPath);

    expect(codes.length).toBeGreaterThan(600);
    expect(codes[0]).toMatchObject({
      code: expect.stringMatching(/^\d{2}(\.\d{1,2})?(\.\d{1,2})?(\.\d+)?$/),
      description: expect.any(String),
      macro: expect.stringMatching(/^[A-U]$/),
    });
  });

  it('parent code resolved for subcategories', async () => {
    const codes = await parseAtecoPdf(
      path.join(__dirname, '../../../Struttura-ATECO-2025-italiano.pdf'),
    );
    // es. "01.11.10" has parent "01.11"
    const sub = codes.find((c) => c.code.match(/^\d{2}\.\d{2}\.\d+$/));
    if (sub) {
      expect(sub.parentCode).toBeTruthy();
    }
  });
});
```

- [ ] **Step 10.3: Run — FAIL**

```bash
pnpm run test -- parse-ateco-pdf
```

- [ ] **Step 10.4: Implementa parser**

File: `apps/api/scripts/parse-ateco-pdf.ts`

```typescript
import * as fs from 'fs/promises';
import pdfParse from 'pdf-parse';

export interface AtecoCodeEntry {
  code: string;
  description: string;
  sector: string;
  macro: string;
  parentCode: string | null;
}

/**
 * Parse the ATECO 2025 PDF (Italian classification) into structured codes.
 * PDF format has:
 *   SECTION A — AGRICOLTURA, SILVICOLTURA E PESCA
 *   01 Coltivazioni agricole ...
 *     01.11 Coltivazione di cereali ...
 *       01.11.10 Coltivazione di cereali ...
 */
export async function parseAtecoPdf(filePath: string): Promise<AtecoCodeEntry[]> {
  const buffer = await fs.readFile(filePath);
  const data = await pdfParse(buffer);
  const text = data.text;

  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);
  const codes: AtecoCodeEntry[] = [];
  let currentMacro = '';
  let currentSector = '';

  // Macro section headers: "SEZIONE A - AGRICOLTURA, SILVICOLTURA E PESCA"
  const macroRe = /^SEZIONE\s+([A-U])\s*[-–]\s*(.+)$/i;
  // ATECO code lines: "01.11.10 Coltivazione di cereali"
  const codeRe = /^(\d{2}(?:\.\d{1,2}(?:\.\d{1,2}(?:\.\d+)?)?)?)\s+(.{5,})$/;

  for (const line of lines) {
    const macroMatch = line.match(macroRe);
    if (macroMatch) {
      currentMacro = macroMatch[1].toUpperCase();
      currentSector = macroMatch[2].trim();
      continue;
    }

    const codeMatch = line.match(codeRe);
    if (codeMatch) {
      const code = codeMatch[1];
      const description = codeMatch[2].trim();
      const parentCode = derivParent(code);

      codes.push({
        code,
        description,
        sector: currentSector,
        macro: currentMacro,
        parentCode,
      });
    }
  }

  return codes;
}

function derivParent(code: string): string | null {
  const parts = code.split('.');
  if (parts.length <= 1) return null;
  return parts.slice(0, -1).join('.');
}

// CLI entrypoint: node parse-ateco-pdf.ts <pdf> <output.json>
if (require.main === module) {
  const [, , pdfPath, outJson] = process.argv;
  if (!pdfPath || !outJson) {
    console.error('Usage: tsx parse-ateco-pdf.ts <pdf> <output.json>');
    process.exit(1);
  }
  parseAtecoPdf(pdfPath)
    .then(async (codes) => {
      const output = {
        version: '2025',
        extracted_at: new Date().toISOString(),
        count: codes.length,
        codes,
      };
      await fs.writeFile(outJson, JSON.stringify(output, null, 2), 'utf8');
      console.log(`Extracted ${codes.length} codes → ${outJson}`);
    })
    .catch((err) => {
      console.error(err);
      process.exit(1);
    });
}
```

Dipendenza: `pnpm add -D pdf-parse @types/pdf-parse`.

- [ ] **Step 10.5: Run test — PASS**

```bash
pnpm run test -- parse-ateco-pdf
```

Expected: 2/2 PASS.

- [ ] **Step 10.6: Esegui parse → JSON committato**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_inspect/apps/api"
npx tsx scripts/parse-ateco-pdf.ts ../../Struttura-ATECO-2025-italiano.pdf prisma/seeds/ateco_2025.json
```

Verifica file generato (count > 600).

- [ ] **Step 10.7: Seed runner**

File: `apps/api/prisma/seeds/ateco_2025.ts`

```typescript
import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';

const prisma = new PrismaClient();

async function main() {
  const json = JSON.parse(
    fs.readFileSync(path.join(__dirname, 'ateco_2025.json'), 'utf8'),
  ) as { codes: Array<{ code: string; description: string; sector: string; macro: string; parentCode: string | null }> };

  console.log(`Seeding ${json.codes.length} ATECO 2025 codes...`);

  // Upsert in batches of 500 for performance
  const batchSize = 500;
  for (let i = 0; i < json.codes.length; i += batchSize) {
    const batch = json.codes.slice(i, i + batchSize);
    await Promise.all(
      batch.map((c) =>
        prisma.atecoCode.upsert({
          where: { code: c.code },
          create: {
            code: c.code,
            description: c.description,
            sector: c.sector,
            macro: c.macro,
            parentCode: c.parentCode,
            version: '2025',
          },
          update: {
            description: c.description,
            sector: c.sector,
            macro: c.macro,
            parentCode: c.parentCode,
            version: '2025',
          },
        }),
      ),
    );
    console.log(`  ${Math.min(i + batchSize, json.codes.length)}/${json.codes.length}`);
  }

  console.log('Done.');
}

main()
  .catch((err) => {
    console.error(err);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
```

- [ ] **Step 10.8: package.json script**

File: `apps/api/package.json` — append in `"scripts"`:

```json
"seed:ateco-2025": "tsx prisma/seeds/ateco_2025.ts"
```

- [ ] **Step 10.9: Run seed locale + verifica DB**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_inspect/apps/api"
pnpm run seed:ateco-2025
pnpm prisma db execute --stdin <<'EOF'
SELECT COUNT(*) FROM "AtecoCode" WHERE version = '2025';
EOF
```

Expected: count > 600.

- [ ] **Step 10.10: Commit**

```bash
git add apps/api/scripts/ apps/api/prisma/seeds/ apps/api/prisma/schema.prisma apps/api/package.json apps/api/prisma/migrations/
git commit -m "M9: Parse ATECO 2025 PDF and seed AtecoCode table

Adds pdf-parse dependency, one-off parser script, JSON seed file,
Prisma seed runner, and package script. ~700 codes seeded.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11 — Test finali + lint + PR

- [ ] **Step 11.1: Run full test suite**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_inspect"
pnpm run test
```

Expected: tutti PASS, zero regressioni vs baseline di Step 1.4.

- [ ] **Step 11.2: Lint**

```bash
pnpm run lint
```

Expected: zero errori.

- [ ] **Step 11.3: Format**

```bash
pnpm run format --check
```

Expected: all formatted.

- [ ] **Step 11.4: Build**

```bash
pnpm run build
```

Expected: build success su tutti gli apps/packages.

- [ ] **Step 11.5: Push branch**

```bash
git push -u origin noise-module-integration
```

- [ ] **Step 11.6: Crea PR via gh CLI**

```bash
gh pr create --title "Wave 24: MARS modifications for Noise module integration" --body "$(cat <<'EOF'
## Summary

Wave 24 del plan `docs/superpowers/plans/2026-04-17-wave-24-mars-modifications.md`.

Aggiunge 9 modifiche additive (M1-M9) per supportare l'integrazione del modulo Rumore e futuri moduli rischio come thin plugin:

- M1: GET /me con tenants + enabledModules
- M2: POST /modules/:key/register-session (+heartbeat +end)
- M3: PUT /dvr-documents/.../module-extensions/:key con optimistic lock
- M4: DVR contract schema v1.1 + Zod (backward compat)
- M5: JWT claim tenant_id opzionale
- M6: POST /client-app/compliance/modules/verify/:key (200/402/403)
- M7: Webhook outbound DVR events HMAC-signed
- M8: ModuleFrame.tsx in apps/web con postMessage handshake
- M9: ATECO 2025 PDF → seed (~700 codes)

## Backward compatibility

Zero breaking changes. Tutti gli endpoint legacy intatti. Schema v1.0 resta valido. JWT legacy senza tenant_id resta valido.

## Test plan

- [x] Tutti i test existing passano
- [x] 2 nuovi test per M1, 2 per M5, 3 per M3, 3 per M6, 2 per M2, 2 per M7, 2 per M8, 2 per M9
- [x] Lint + format + build passano
- [ ] Manual: seed ATECO 2025 in DB staging
- [ ] Manual: smoke test /me + verify endpoints con curl
- [ ] Manual: iframe ModuleFrame caricato da apps/web senza errori console

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL restituito.

- [ ] **Step 11.7: Verifica PR CI green**

Attendi GitHub Actions completion. Controlla:
- Tests: green
- Lint: green
- Build: green

---

## Rollback

Se qualcosa va storto:

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_inspect"
git checkout master
git branch -D noise-module-integration  # locale
git push origin --delete noise-module-integration  # remoto (se pushato)

# DB rollback (se hai fatto migrate dev su DB locale):
pnpm prisma migrate resolve --rolled-back <migration-name>
```

Il modulo Rumore continua a funzionare in standalone mode senza modifiche MARS.

---

## Acceptance criteria Wave 24

Tutti i seguenti verdi prima di marcare Wave 24 done:

1. ✅ Branch `noise-module-integration` pushato su `SkaRomance/MARS`
2. ✅ PR aperta e CI green
3. ✅ 9 commit atomici `M<n>: <subject>`
4. ✅ 20+ nuovi test unitari/integration passanti
5. ✅ `pnpm run build` success su tutti i workspaces
6. ✅ `GET /me` chiamabile con token valido → payload corretto
7. ✅ `PUT .../module-extensions/noise` restituisce 409 su version mismatch
8. ✅ ATECO 2025 seed popolato (`SELECT count(*) FROM AtecoCode WHERE version='2025'` > 600)
9. ✅ `ModuleFrame` renderizza iframe senza errori console in apps/web

---

## Next Wave

Dopo merge di W24 (o anche prima, su branch parallelo), procedere con:
**Wave 25 — Rumore DB refactoring** (`2026-04-17-wave-25-db-refactoring.md`)
