# HIPA MASALA — Backend

Django REST API for the HIPA MASALA business portal. It serves the React app in `../frontend`.

**Stack:** Python 3.14 · Django 6.1 · Django REST Framework · Supabase (Postgres) · JWT (SimpleJWT) · django-cors-headers · pandas · scikit-learn · python-dotenv

**Data rule:** there is no seed or demo data. Every figure the API returns is calculated from records people enter. On an empty database, lists are empty, counts are 0, and anything that can't be calculated is `null` or reports `insufficient_data`.

---

## 1. Setup (Windows)

```powershell
cd backend
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env        # then fill in the values (see below)
```

All packages live in the project's virtual environment `backend/.venv` (nothing is installed into the global Python). You don't need to activate it:

- `python manage.py ...` automatically re-runs itself with `.venv`'s Python when started from another Python (see `use_project_venv()` in `manage.py`).
- In VS Code, new terminals put `.venv\Scripts` first on `PATH` (`.vscode/settings.json`), so `python` and `pip` there are the venv's.
- Add a package: `python -m pip install <name>` in a VS Code terminal (or `.\.venv\Scripts\python.exe -m pip install <name>`), then add it with its version to `requirements.txt`.

### Create the Supabase project

The database is Postgres hosted on [Supabase](https://supabase.com). Django connects to it directly.

1. Sign in at <https://supabase.com/dashboard> and click **New project**. Pick a name (e.g. `hipa-masala`), a strong **database password** (keep it in a password manager), and the region nearest you (`South Asia (Mumbai)`). The Free plan is enough to start.
2. When the project is ready, click **Connect** at the top of the dashboard, choose the **Session pooler** connection, and copy the URI. It looks like `postgresql://postgres.<project-ref>:[YOUR-PASSWORD]@aws-0-<region>.pooler.supabase.com:5432/postgres`.
3. In `backend/.env`, set `SUPABASE_DB_URL` to that URI with `[YOUR-PASSWORD]` replaced by your database password. If the password has characters like `@ : / ? #`, URL-encode them (e.g. `@` → `%40`).
4. From **Project Settings → API**, copy the **Project URL** into `SUPABASE_URL` and the **anon public** key into `SUPABASE_ANON_KEY`.
5. Create the tables: `python manage.py migrate` (below). Alternatively paste `supabase/schema.sql` into the dashboard's **SQL Editor** and run it once on the empty project, then run `migrate` once anyway: it only adds Django's content types and permissions.

Every app table has row level security turned on (with no policies), so Supabase's public REST API returns nothing to anyone holding the anon key. Django connects as the table owner and is not affected. This happens automatically after each `migrate`.

To regenerate `supabase/schema.sql` after adding migrations: `python scripts/export_supabase_schema.py` (it migrates a throwaway database on the same server and drops it afterwards).

### `.env`

| Variable | Required | Meaning |
|---|---|---|
| `DJANGO_SECRET_KEY` | yes | Long random string. Generate: `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"` |
| `DEBUG` | | `True` only on a developer PC |
| `ALLOWED_HOSTS` | | Comma-separated host names |
| `SUPABASE_DB_URL` | yes | Supabase Postgres connection string (Session pooler URI) |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | | Supabase project URL and anon key (Project Settings → API) |
| `CORS_ALLOWED_ORIGINS` | | Frontend origin(s); default `http://localhost:5173` |
| `FRONTEND_URL` | | Used in password-reset and invitation links |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL` | | SMTP for resets, invitations and customer offers. Without it, e-mails are printed to the server console |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | | AI Assistant chat with Google Gemini (default model `gemini-3.8-flash`). Empty key = assistant shows "not connected" |
| `PG_DUMP_PATH`, `BACKUP_DIR` | | Database backups (`pg_dump` is found automatically in `C:\Program Files\PostgreSQL\<version>\bin`) |
| `JWT_ACCESS_MINUTES` | | Access-token lifetime (default 480 = one working day). Logout, password change and password reset end the user's sessions on every device straight away |
| `LOGIN_THROTTLE_RATE`, `AI_CHAT_THROTTLE_RATE` | | Failed sign-ins per IP (default `10/min`, also applied to `/admin/` sign-in) and AI chat messages per user (default `20/min`) |
| `NUM_PROXIES` | | Only behind a reverse proxy: how many. Unset = `X-Forwarded-For` is ignored, since anyone can fake it |

`.env` holds secrets: never commit or share it. `.gitignore` already excludes it.

### Create tables and the first admin

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
```

A Django superuser always has the **Super Admin** role in the portal. Other users are invited from **Settings → User Management** (they receive an e-mail to set their password), or added in the Django admin.

### Run

```powershell
python manage.py runserver 8000
```

- API: `http://localhost:8000/api/v1/`
- Django admin: `http://localhost:8000/admin/`

The frontend's dev server forwards `/api` to `http://localhost:8000`, and its `VITE_API_BASE_URL` is `/api/v1`. Start both, then open `http://localhost:5173`.

---

## 2. Project layout

```
backend/
  manage.py  requirements.txt  .env  .env.example  README.md
  config/        settings (all from .env), URLs, WSGI/ASGI
  apps/
    core/          roles & permissions, pagination, errors, date ranges, KPI helpers
    accounts/      users (with role), login activity, auth endpoints
    system/        settings, notifications, audit log, backups
    dashboard/  sales/  inventory/  purchase/  marketing/  customers/
    supply_chain/  quality/  attendance/  finance/ (retired: tables only)  reports/  ai_assistant/
    legacy_production/  migration history of the retired Production module only (label "production"; drops its tables)
  supabase/      schema.sql: the Postgres schema the migrations create (generated)
  services/      audit trail, notifications, backups, report exporters, AI engine client
  scripts/       daily_tasks.py (run by Windows Task Scheduler)
  ml/            forecasting, customer segmentation, anomaly detection, stock-out risk
  tests/         automated tests
```

---

## 3. API

Base path: **`/api/v1/`**. Every endpoint except login, refresh and password reset needs `Authorization: Bearer <access token>`.

The exact request and response shapes are documented in the frontend's `src/api/*.js` files; the backend follows them.

| Area | Endpoints |
|---|---|
| Auth | `POST auth/login/` (username **or** e-mail) · `POST auth/refresh/` · `GET auth/me/` · `POST auth/logout/` · `POST auth/password/forgot/` · `POST auth/password/reset/` · `POST auth/password/change/` |
| Dashboard | `GET dashboard/summary/?range=` · `GET dashboard/sales-trend/?period=` |
| Sales | `overview/` · `trend/` · `options/` · `orders/` (GET, POST with `items[]` or single product) · `orders/<id>/` · `orders/<id>/status/` (POST, next step only) · `orders/<id>/cancel/` · `orders/<id>/convert-to-invoice/` |
| Sales quotations | `sales/quotations/` (GET, POST) · `quotations/<id>/` (GET, PATCH, DELETE draft) · `quotations/<id>/status/` (POST) · `quotations/<id>/pdf/` (`?download=1` to download) · `quotations/<id>/convert-to-order/` · `quotations/<id>/convert-to-invoice/` |
| Sales invoices | `sales/invoices/` (GET, POST direct or `sales_order_id`) · `invoices/<id>/` (GET, PATCH) · `invoices/<id>/cancel/` · `invoices/<id>/pdf/` |
| Sales payments / returns | `sales/payments/` (GET, POST) · `payments/<id>/cancel/` · `sales/returns/` (GET, POST) · `returns/<id>/` (PATCH status) |
| Inventory | `overview/` · `options/` · `items/` (GET with `?active=false` for switched-off products, POST) · `items/<id>/` (GET, PATCH name, price, min/reorder levels, active) · `items/export/` · `movements/` (GET, POST) |
| Purchase | `purchase/overview/` · `trend/` · `options/` · `recommendations/?horizon=30|15|7` · `recommendations/export/` · `suppliers/` (GET, POST) · `suppliers/<id>/` (GET, PATCH, DELETE) · `raw-materials/` (GET, POST) · `raw-materials/<id>/` (GET, PATCH, DELETE) · `material-movements/` (GET, POST) · `purchases/` (GET, POST) · `purchases/<id>/` (GET, PATCH, DELETE) · `purchases/<id>/cancel/` · `goods-receipts/` (GET, POST) · `goods-receipts/<id>/` · `returns/` (GET, POST) · `returns/<id>/` (GET, PATCH status) · `payments/` (GET, POST) · `payments/<id>/` (GET, DELETE scheduled) · `payments/<id>/mark-paid/` · `payments/<id>/cancel/` (POST, made payments) |
| Marketing | `overview/` · `performance/` · `audience/` · `options/` · `campaigns/` (GET, POST) · `campaigns/<id>/end/` · `posts/` (GET, POST) · `posts/<id>/status/` (POST published / cancelled: there is no Instagram/Facebook connection, so posts are published by hand and then marked) |
| Customers | `customers/` (GET, POST) · `customers/<id>/` (GET, PATCH) · `overview/` · `growth/` · `options/` · `export/` · `import/template/` · `import/` · `offers/` |
| Supply chain | `supply-chain/overview/` · `supplier-performance/` · `options/` · `shipments/` (GET, POST from an open purchase or supplier + material) · `shipments/<id>/status/` (POST: In Transit ↔ Delayed, Delivered with date and inward quality result; final) (suppliers and purchases are in Purchase) |
| Quality | `overview/` · `trend/` · `options/` · `tests/` (GET, POST) · `standards/` · `audits/` (GET `?status=`, POST) · `audits/<id>/status/` (POST: completed with findings, from the audit date; or cancelled) · `report/` |
| Attendance | `attendance/status/` · `check-in/` · `check-out/` (POST; server time only, refused while the window is closed) · `history/` (own) · `records/` · `options/` · `employees/` (GET, POST) · `employees/<id>/` (GET, PATCH, DELETE = removed from the list, history kept) · `leave/` (GET own or `?scope=all`, POST) · `leave/<id>/` (PATCH own pending) · `leave/<id>/approve|reject|cancel/` · `calendar/?month=&employee=` · `reports/?type=daily|monthly|employee|leave&date_from=&date_to=&employee=&department=&status=&format=json|pdf|xlsx|csv` · `settings/` (GET, PATCH) |
| Reports | types: sales, quotations, inventory, purchase, marketing, customers, supply_chain, quality, ai_business · `reports/` (GET, POST) · `overview/` · `preview/?type=&range=` · `export/?type=&range=&format=pdf|xlsx|csv` · `<id>/download/` |
| AI assistant | `ai/status/` · `ai/home/` · `ai/chat/` · `ai/conversations/<id>/` |
| Settings | `settings/options/` · `general/` · `company/` · `billing/` (tax & billing defaults, bank details) · `users/` · `users/<id>/` · `notifications/` · `backup/` · `backup/run/` · `integrations/` · `security/` · `security/login-activity/` · `audit-logs/` |
| Notifications | `notifications/` · `notifications/<id>/read/` · `notifications/mark-all-read/` |

**Ranges:** `range=this_month | last_month | last_3_months | this_year`. KPIs are `{ value, change? }`; `change` is the % difference from the previous period of the same length and is left out when there's nothing to compare with.

**Lists** of records are paginated: `?page=&page_size=` (max 100) → `{ count, next, previous, results }`. Small reference lists the frontend expects as plain arrays (chart series, standards, integrations, notification preferences) stay arrays.

**Errors:** validation errors are `{ "field": ["message"] }`; other errors are `{ "detail": "message" }`. Status codes: 400 invalid input, 401 not signed in / session expired, 403 role not allowed, 404 not found, 429 too many login attempts, 503 a feature isn't configured (e-mail, AI engine) or the database is unreachable. Stack traces are never returned; they go to the server log.

### Roles

Enforced on the server for every request (`apps/core/roles.py`), matching the frontend menu:

| Module | Can open | Can change |
|---|---|---|
| Dashboard, AI Assistant, Reports | everyone | everyone (reports: only types for modules they can open) |
| Sales | admin, management, sales, marketing, finance | admin, management, sales |
| Inventory | admin, management, inventory, purchase, supply_chain | admin, management, inventory |
| Purchase | admin, management, purchase, inventory, finance, supply_chain | admin, management, purchase (supplier payments: also finance; raw-material usage: also inventory) |
| Marketing | admin, management, marketing | admin, management, marketing |
| Customers | admin, management, sales, marketing | admin, management, sales (offers: marketing) |
| Supply Chain | admin, management, inventory, quality, purchase, supply_chain | admin, management, inventory, supply_chain |
| Quality | admin, management, quality, purchase | admin, management, quality |
| Attendance | everyone | per user (Settings → Users → Attendance): check in, check out, apply / view all / approve / reject leave, manage employees, view every calendar, reports, settings. A Super Admin has all |
| Settings | admin, management | admin, management (only a Super Admin can manage Super Admins) |

---

## 4. Where data comes from

Most records are entered in the portal. A few kinds are entered in the **Django admin** (`/admin/`) because the portal has no form for them:

| Data | Admin section | Used by |
|---|---|---|
| Daily marketing numbers, top content, audience split | Marketing | Marketing overview, performance and audience charts |
| Quality standards, certifications | Quality | Standards list, certification status |

Stock always changes through movements, so product and material stock can't be edited directly: sales orders take stock out and cancellations put it back; goods receipts (GRN) add the accepted quantity of a purchase; purchase returns take stock out (and put it back if cancelled); raw-material usage is recorded under Purchase → material movements.

**Shipments** are created and tracked in Supply Chain (New Shipment, Track Shipments). Marking one delivered doesn't add stock: the goods receipt in Purchase does.

**Sales orders** move forward one step at a time in the portal: Pending → Processing → In Transit → Delivered (final). Pending and Processing orders can be cancelled, which puts the stock back.

**Attendance** (`apps/attendance`, replaced Accounts on 2026-10-08): the window is open from 05:00 PM to 09:20 AM the next day and closed from 09:20 AM to 05:00 PM, every day (times in Attendance → Settings), decided only by the server clock in Asia/Kolkata; each record is filed under the date its window opened, so a 2 AM check-in belongs to the previous evening. One check-in and one check-out per window, both stamped with the server time; a check-in that is never checked out shows "Not checked out". Absent = a finished window with no check-in and no approved leave (active employees only); there is no holiday list. An employee is linked to a portal login to mark their own attendance; deleting an employee only removes them from the list. Every action checks its own per-user permission on the server (403 without it). **Accounts** was removed from the app: no screens, endpoints, Dashboard Net Profit, report, AI data or payment posting any more. Its tables (`finance_transaction`, `finance_budget`) and their data were kept untouched; the `finance` app stays installed only for that.

**Sales documents:** Customer → Quotation (Draft → Sent → Accepted / Rejected; Expired automatically after its valid-until date, daily and whenever quotations are listed) → Sales Order → Sales Invoice → Payment. Converting a quotation creates a new order or invoice with its own number and copies the customer and lines (price, discount, GST); a quotation converts once. Stock: an order takes stock out; an invoice made from an order does not move stock again; an invoice made without an order takes stock out (and puts it back if cancelled); a sales return marked "restock" puts goods back. Line totals: subtotal − discount + GST; sales figures in reports and analytics are net of GST. Quotation and invoice PDFs use company details from Settings → Company Profile and Tax & Billing, the original logo (`assets/hipa-logo.png`) and Noto Sans (`assets/fonts`, SIL Open Font License) so ₹ prints.

**Purchase rules:** a purchase is one raw material or product from one supplier; total = subtotal − discount + GST. There are no purchase orders and no purchase invoices. Payment status (Pending / Partially Paid / Paid / Overdue) comes from completed supplier payments, completed returns and the payment due date (default: purchase date + the supplier's credit days).

---

## 5. Analytics and AI

`ml/` works only on real records:

- **Purchase recommendations** (`GET purchase/recommendations/?horizon=30|15|7`, `ml/purchasing.py`):
  - *Raw materials:* average daily usage over the last 120 days (usage recorded under Purchase → material movements; needs 14+ days of history with usage on 3+ days), supplier lead time measured from past purchases to their first goods receipt, safety stock = 1.65 × std(daily usage) × √lead time. Recommended quantity = usage over the horizon + safety stock − stock − quantity still to be received. Without any measured lead time the material's own reorder level is used as the reorder point, and the row says so.
  - *Finished products:* the sales forecast (`ml/forecasting.py`, 4+ weeks of sales on 6+ days; its safety stock uses a fixed 7-day lead time) + safety stock − stock − quantity on order.
  - Each row also gives the last and average purchase price, the change since the previous purchase, the supplier with the lowest average price in the last 180 days, an estimated cost and a priority (HIGH when stock plus on-order is at or below the reorder point). Items without enough data are listed in `insufficient` with the reason; when no item qualifies the response is `status: insufficient_data` with "Insufficient data for AI recommendation."
  - Results are cached per horizon (up to 6 hours) and recomputed automatically as soon as purchases, goods receipts, material movements, raw materials, suppliers, products or sales change, or the day changes. The export uses the same cached result.
- **Insights** (stock-out risk, unusual sales days, customer segments with KMeans, quality failure rates) are produced by:

  ```powershell
  .\.venv\Scripts\python.exe manage.py run_analytics
  ```

  It runs daily through the scheduled task described in section 6. Parts without enough data are skipped and recorded as `insufficient_data` in the run summary (Django admin → AI assistant → Analytics runs).

- **AI Assistant chat** uses **Google Gemini** through the official `google-genai` SDK (`services/ai_client.py`).
  1. Create a free key at <https://aistudio.google.com/apikey>.
  2. Put it in `backend/.env` as `GEMINI_API_KEY=...`, then restart the backend. The key is used only on the server; the React app never sees it.
  3. Check it with `python manage.py check_ai`. This confirms the key works and that `GEMINI_MODEL` is available to it.

  With "Use company data" on, each question is sent with a summary of real figures, limited to the modules the user may open, and the answer lists "HIPA MASALA business data" as its source. When the database has no business records yet, the answer starts by saying so, and the model is told not to give example figures. Without a key, `ai/status/` reports `available: false` and chat returns 503. When the free-tier rate limit is reached, chat returns 429 with a "wait a minute" message.

---

## 6. Backups

**Settings → Data & Backup → Back Up Now** runs `pg_dump` on the app's tables (schema `public`) and saves a compressed `hipa_masala-supabase-<date>-<time>.sql.gz` file in `BACKUP_DIR` (default `backend/backups`). Supabase also keeps its own daily backups on paid plans.

`pg_dump` must be the same major version as the Supabase server (17), or newer. On this PC the PostgreSQL 17 command-line tools (no database server) are installed in `C:\Program Files\PostgreSQL\17\bin`; the backup finds the newest `C:\Program Files\PostgreSQL\<version>\bin\pg_dump.exe` by itself. To install them on another PC:

```powershell
winget install --id PostgreSQL.PostgreSQL.17 -e --override "--mode unattended --unattendedmodeui minimal --disable-components server,pgAdmin,stackbuilder"
```

Set `PG_DUMP_PATH` in `.env` only if `pg_dump` lives somewhere else.

Retention (Settings → Data & Backup) deletes only old `hipa_masala-supabase-*.sql.gz` files. Anything else in the folder, such as the earlier MySQL dumps `hipa_masala-<date>.sql.gz`, is never deleted.

### Daily scheduled task

The Windows Task Scheduler task **"HIPA MASALA daily tasks"** starts `scripts/daily_tasks.py` every hour from 09:30 to 18:30. The jobs run **once a day**, at the first start when the PC is awake: the date of the last successful run is kept in `logs/daily_tasks.last`, later starts that day do nothing, and after a failure the next hour tries again. (It used to run at 02:00, but this PC sleeps at night and Windows doesn't catch up a missed run after waking from sleep, so it stopped running.) It uses `pythonw.exe`, so no window appears. It:

1. runs `expire_quotations` (draft / sent quotations past their valid-until date become Expired);
2. runs `send_due_alerts` (purchases not received on time, supplier payments due within 2 days, overdue invoices — each alert once);
3. runs `run_analytics` (insights, including HIGH-priority purchase recommendations shown on the Dashboard and in the AI Business Report);
4. runs `run_backup --scheduled`, which backs up only when **Automatic backup** is on in Settings and deletes this app's backups older than the chosen retention period.

Output is appended to `backend/logs/daily_tasks.log`. To run the jobs again today: `.venv\Scripts\python scripts\daily_tasks.py --force`. To recreate the task on another PC:

```powershell
$action = New-ScheduledTaskAction -Execute "<backend>\.venv\Scripts\pythonw.exe" -Argument '"<backend>\scripts\daily_tasks.py"' -WorkingDirectory "<backend>"
$trigger = New-ScheduledTaskTrigger -Daily -At 09:30
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At 09:30 -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Hours 9)).Repetition
Register-ScheduledTask -TaskName "HIPA MASALA daily tasks" -Action $action -Trigger $trigger -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable)
```

Each job can also be run by hand: `manage.py run_analytics`, `manage.py run_backup`.

### Restore a backup

A backup holds every app table with its data, constraints, indexes and row level security. It restores into an **empty** database, so you never overwrite live data by accident:

1. In the Supabase dashboard create a new project (or ask for a fresh database), and note its Session pooler connection details.
2. Unzip the backup with 7-Zip, or from the backend folder:
   ```powershell
   .\.venv\Scripts\python.exe -c "import gzip,shutil,sys; shutil.copyfileobj(gzip.open(sys.argv[1]), open(sys.argv[2],'wb'))" backups\hipa_masala-supabase-<date>-<time>.sql.gz restore.sql
   ```
3. Load it (psql asks for the database password; `ON_ERROR_STOP` stops at the first problem):
   ```powershell
   & "C:\Program Files\PostgreSQL\17\bin\psql.exe" "host=<pooler-host> port=5432 user=postgres.<project-ref> dbname=postgres sslmode=require" -v ON_ERROR_STOP=1 -f restore.sql
   ```
4. Point `SUPABASE_DB_URL` in `.env` at the restored database, restart the backend, and delete `restore.sql` (it contains all your data in plain text).

This procedure was tested on 2026-10-07: a backup restored into a throw-away database had all 57 tables, 80 foreign keys and row level security, and every row matched the live database.

---

## 7. Tests

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test tests
```

The test runner creates a separate `test_hipa_masala` database on the Supabase server and deletes it afterwards; the real database is never touched. The suite covers login, tokens, password reset, role permissions for every module, every endpoint on an empty database, validation errors, CORS, and full workflows (orders and stock, purchases with goods receipts / returns / supplier payments, quality tests on goods receipts, supply chain, attendance (the window loop, separate check-in / check-out permissions, employees, leave, calendar, reports, settings), reports in all three formats).

---

## 8. Notes and troubleshooting

- **Postgres driver:** `psycopg[binary]`, whose wheel bundles `libpq`, so no local PostgreSQL install is needed. It loads under Windows Smart App Control on this PC.
- **scikit-learn is pinned to 1.9.0 and pandas to 3.0.5** for the same reason: Smart App Control blocks a compiled file in scikit-learn 1.9.1 and in pandas 3.0.6 (`groupby`). Smart App Control can change its verdict later. If a start-up error says `An Application Control policy has blocked this file`, note the package in the error and try its previous release with `python -m pip install "<package>==<version>"`, then update `requirements.txt`.
- The analytics engine (`ml/`: pandas, scikit-learn) is loaded only when an analytics feature or `run_analytics` needs it. If one of its files is ever blocked, only those features return 503 "analytics engine unavailable"; login and every other page keep working.
- `No module named 'rest_framework'` (or `django`) → the command ran on a Python without the project packages and `.venv` is missing. Create it with the setup commands in section 1.
- `Error: That port is already in use` → another backend is already running on 8000; use it, or stop it first.
- `password authentication failed` → check the password inside `SUPABASE_DB_URL` (URL-encode special characters). `connection timed out` / `could not translate host name` → use the **Session pooler** URI (the direct `db.<ref>.supabase.co` host is IPv6-only), and check that the project isn't paused in the Supabase dashboard (free projects pause after a week without use).
- The server refuses to start without `DJANGO_SECRET_KEY` and `SUPABASE_DB_URL`, and says which variable is missing.
- For production: `DEBUG=False`, real `ALLOWED_HOSTS`, HTTPS, a strong Supabase database password, SMTP e-mail, and serve the built frontend with `/api/` proxied to Django.
