# CLAUDE.md — Engineering Standards & Project Intelligence

> This file is read by Claude Code at session start. It defines how we build,
> what we value, and the non-negotiable standards for every line of code.

---

## 🧠 Who You Are Working With

- **Developer**: sagaraliasjacky
- **Stack philosophy**: Ship fast, build right, scale clean
- **Preferred tools**: Next.js 14+, TypeScript (strict), Supabase, Prisma, Clerk, Stripe, Tailwind, Shadcn/ui
- **AI integration**: Anthropic Claude API (claude-sonnet-4-20250514 default)
- **Deployment**: Vercel (frontend), Supabase (backend/db), Cloudflare (DNS/edge)

---

## ⚙️ Tech Stack Reference

### Frontend
- **Framework**: Next.js 14+ with App Router (not Pages Router)
- **Language**: TypeScript — strict mode, no `any`, no implicit types
- **Styling**: Tailwind CSS + Shadcn/ui components
- **State**: Zustand for global, React Query (TanStack) for server state
- **Forms**: React Hook Form + Zod validation
- **Animation**: Framer Motion for interactions

### Backend
- **API**: Next.js Route Handlers (`app/api/`) — RESTful, typed with Zod
- **Database**: Supabase (Postgres) + Prisma ORM
- **Auth**: Clerk (multi-tenant aware)
- **Payments**: Stripe (subscriptions + webhooks)
- **Email**: Resend + React Email templates
- **Storage**: Supabase Storage

### AI Layer
- **Primary**: Anthropic Claude API
- **Model default**: `claude-sonnet-4-20250514`
- **Pattern**: Streaming responses, tool use where applicable
- **Key**: Read from `ANTHROPIC_API_KEY` env var — never hardcode

### Observability
- **Error tracking**: Sentry
- **Analytics**: PostHog
- **Logging**: Structured JSON logs, never `console.log` in production

---

## 📁 Project Structure Convention

```
src/
├── app/                    # Next.js App Router
│   ├── (auth)/             # Auth group (Clerk)
│   ├── (dashboard)/        # Protected dashboard routes
│   ├── api/                # Route handlers
│   └── layout.tsx          # Root layout
├── components/
│   ├── ui/                 # Shadcn primitives (never modify directly)
│   └── [feature]/          # Feature-scoped components
├── lib/
│   ├── supabase/           # Supabase client + server
│   ├── stripe/             # Stripe helpers
│   ├── claude/             # Anthropic API wrappers
│   └── utils.ts            # Shared utilities (cn(), etc.)
├── hooks/                  # Custom React hooks
├── stores/                 # Zustand stores
├── types/                  # Global TypeScript types
└── config/                 # App-wide config constants
```

---

## 🏗️ Code Standards

### TypeScript
- Strict mode always on (`"strict": true` in tsconfig)
- Explicit return types on all functions
- Zod schemas for all external data (API responses, form inputs, env vars)
- Use `type` for object shapes, `interface` for extensible contracts
- Never use `as` casting unless absolutely unavoidable — add a comment if you do

### React / Next.js
- Server Components by default — opt into `"use client"` only when necessary
- Data fetching in Server Components, mutations via Server Actions
- Co-locate component logic: one folder per feature, not one file per type
- No prop drilling beyond 2 levels — use context or Zustand
- All images through `next/image`, all links through `next/link`

### API Routes
- Every route handler typed with Zod input validation
- Consistent response shape: `{ data, error, meta }`
- Auth checked at the top of every protected route via Clerk `auth()`
- Rate limiting on all public endpoints

### Database
- All queries go through Prisma — no raw SQL except for complex analytics
- Every schema change gets a migration file (`prisma migrate dev`)
- Never expose Prisma client on the client side
- Row Level Security (RLS) enabled on all Supabase tables

### Error Handling
- Never swallow errors silently
- Always log with context: `{ error, userId, route, input }`
- User-facing errors: friendly message only, no stack traces
- Use `Result` pattern for functions that can fail predictably

---

## 🔐 Security Non-Negotiables

- All env vars validated with Zod at startup (`src/env.ts`)
- No secrets in client bundles — use `NEXT_PUBLIC_` prefix only for truly public values
- All webhooks (Stripe, Clerk) verified with signature validation
- CORS locked down on API routes
- Input sanitized before any DB write
- Never log PII (emails, names, payment info)

---

## 🚀 Performance Standards

- Lighthouse score target: **95+** on all pages
- Core Web Vitals: LCP < 2.5s, FID < 100ms, CLS < 0.1
- Bundle size: Audit with `@next/bundle-analyzer` before major releases
- Images: WebP/AVIF, lazy loaded, explicit width/height
- Fonts: `next/font` only, preloaded, no layout shift
- API responses: Cache aggressively with proper revalidation strategy

---

## 🧪 Testing Philosophy

- **Unit tests**: Vitest for pure functions and utilities
- **Component tests**: React Testing Library for critical UI
- **E2E tests**: Playwright for auth flows, checkout, and core user journeys
- **Coverage target**: 80%+ on business logic, not UI boilerplate
- Run `pnpm test` before every PR

---

## 📦 Package Management

- **Package manager**: pnpm (not npm, not yarn)
- Lock file committed always (`pnpm-lock.yaml`)
- No unnecessary dependencies — challenge every `npm install`
- Audit regularly: `pnpm audit`
- Keep dependencies updated: `pnpm update --interactive`

---

## 🔄 Git & Workflow

### Commit convention (Conventional Commits)
```
feat: add Stripe subscription webhook handler
fix: resolve Clerk auth redirect loop on /dashboard
chore: update Prisma schema for tenant isolation
refactor: extract AI streaming logic into useStream hook
docs: update CLAUDE.md with new API standards
```

### Branch strategy
- `main` — production, protected, requires PR
- `dev` — integration branch
- `feat/[name]` — feature branches
- `fix/[name]` — bug fixes

### PR rules
- Every PR has a description explaining *why*, not just *what*
- No PR merges with failing tests or TypeScript errors
- Self-review before requesting review

---

## 🤖 Claude Code Behaviour

When working in this codebase, Claude should:

1. **Read before writing** — always check existing patterns before creating new files
2. **Stay in scope** — don't refactor unrelated code unless asked
3. **Type everything** — never leave TypeScript errors or `any` types
4. **Explain big decisions** — if making an architectural choice, say why
5. **Small commits** — prefer multiple focused changes over one giant diff
6. **Check env vars** — if adding a new service, add its env var to `.env.example`
7. **Follow the folder structure** — don't create ad-hoc files in the root
8. **Use existing utilities** — check `lib/` and `hooks/` before reinventing
9. **Write the test** — for any new utility function, add a test alongside it
10. **Ask before deleting** — never delete files without confirming intent

---

## 🌍 Environment Variables

Always maintain `.env.example` with all required keys (no values).
Required vars for full stack:

```env
# App
NEXT_PUBLIC_APP_URL=

# Clerk
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
CLERK_SECRET_KEY=
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up

# Supabase
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

# Database
DATABASE_URL=

# Stripe
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=

# Anthropic
ANTHROPIC_API_KEY=

# Resend
RESEND_API_KEY=

# Sentry
SENTRY_DSN=
NEXT_PUBLIC_SENTRY_DSN=

# PostHog
NEXT_PUBLIC_POSTHOG_KEY=
NEXT_PUBLIC_POSTHOG_HOST=
```

---

## 📋 Common Commands

```bash
pnpm dev              # Start dev server
pnpm build            # Production build
pnpm test             # Run all tests
pnpm lint             # ESLint check
pnpm typecheck        # TypeScript check (no emit)
pnpm db:push          # Push Prisma schema to DB
pnpm db:studio        # Open Prisma Studio
pnpm db:migrate       # Run migrations
pnpm analyze          # Bundle analyzer
```

---

## 💡 Key Principles

> **"Correct, then fast, then clean — in that order."**

- Working > perfect. Ship it, then improve it.
- Simple > clever. Future-you will thank present-you.
- Explicit > implicit. Make the code say what it means.
- Boring tech for infrastructure, innovative tech for product.
- Every feature starts with: *what problem does this solve for the user?*

---

*Last updated: March 2026 | Stack: Next.js 14 · TypeScript · Supabase · Clerk · Stripe · Claude API*
