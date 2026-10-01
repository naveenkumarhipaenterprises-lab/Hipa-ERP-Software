# HIPA MASALA — Backend

Django REST API for the HIPA MASALA business portal. It serves the React app in `../frontend`.

**Stack:** Python 3.14 · Django 6.1 · Django REST Framework · MySQL 8.4 · JWT (SimpleJWT) · django-cors-headers · pandas · scikit-learn · python-dotenv

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

### Create the MySQL database

In MySQL (for example `mysql -u root -p`):

```sql
CREATE DATABASE hipa_masala CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- Recommended: a dedicated user instead of root
CREATE USER 'hipa'@'localhost' IDENTIFIED BY 'a-strong-password';
GRANT ALL PRIVILEGES ON hipa_masala.* TO 'hipa'@'localhost';
-- The test runner creates and drops test_hipa_masala:
GRANT ALL PRIVILEGES ON test_hipa_masala.* TO 'hipa'@'localhost';
```

### `.env`

| Variable | Required | Meaning |
|---|---|---|
| `DJANGO_SECRET_KEY` | yes | Long random string. Generate: `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"` |
| `DEBUG` | | `True` only on a developer PC |
| `ALLOWED_HOSTS` | | Comma-separated host names |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | yes | MySQL connection |
| `CORS_ALLOWED_ORIGINS` | | Frontend origin(s); default `http://localhost:5173` |
| `FRONTEND_URL` | | Used in password-reset and invitation links |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL` | | SMTP for resets, invitations and customer offers. Without it, e-mails are printed to the server console |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | | AI Assistant chat with Google Gemini (default model `gemini-3.8-flash`). Empty key = assistant shows "not connected" |
| `MYSQLDUMP_PATH`, `BACKUP_DIR` | | Database backups |
| `JWT_ACCESS_MINUTES` | | Access-token lifetime (default 480 = one working day) |

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
  config/        settings (all from .env), URLs, WSGI/ASGI, PyMySQL driver set-up
  apps/
    core/          roles & permissions, pagination, errors, date ranges, KPI helpers
    accounts/      users (with role), login activity, auth endpoints
    system/        settings, notifications, audit log, backups
    dashboard/  sales/  inventory/  purchase/  marketing/  customers/
    supply_chain/  quality/  finance/  reports/  ai_assistant/
    legacy_production/  migration history of the retired Production module only (label "production"; drops its tables)
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
| Sales | `overview/` · `trend/` · `options/` · `orders/` (GET, POST with `items[]` or single product) · `orders/<id>/` · `orders/<id>/cancel/` · `orders/<id>/convert-to-invoice/` |
| Sales quotations | `sales/quotations/` (GET, POST) · `quotations/<id>/` (GET, PATCH, DELETE draft) · `quotations/<id>/status/` (POST) · `quotations/<id>/pdf/` (`?download=1` to download) · `quotations/<id>/convert-to-order/` · `quotations/<id>/convert-to-invoice/` |
| Sales invoices | `sales/invoices/` (GET, POST direct or `sales_order_id`) · `invoices/<id>/` (GET, PATCH) · `invoices/<id>/cancel/` · `invoices/<id>/pdf/` |
| Sales payments / returns | `sales/payments/` (GET, POST) · `payments/<id>/cancel/` · `sales/returns/` (GET, POST) · `returns/<id>/` (PATCH status) |
| Inventory | `overview/` · `options/` · `items/` (GET, POST) · `items/export/` · `movements/` (GET, POST) |
| Purchase | `purchase/overview/` · `trend/` · `options/` · `suppliers/` (GET, POST) · `suppliers/<id>/` (GET, PATCH, DELETE) · `raw-materials/` (GET, POST) · `raw-materials/<id>/` (GET, PATCH, DELETE) · `material-movements/` (GET, POST) · `purchases/` (GET, POST) · `purchases/<id>/` (GET, PATCH, DELETE) · `purchases/<id>/cancel/` · `goods-receipts/` (GET, POST) · `goods-receipts/<id>/` · `returns/` (GET, POST) · `returns/<id>/` (GET, PATCH status) · `payments/` (GET, POST) · `payments/<id>/` (GET, DELETE scheduled) · `payments/<id>/mark-paid/` |
| Marketing | `overview/` · `performance/` · `audience/` · `options/` · `campaigns/` (GET, POST) · `campaigns/<id>/end/` · `posts/` (GET, POST) |
| Customers | `customers/` (GET, POST) · `customers/<id>/` (GET, PATCH) · `overview/` · `growth/` · `options/` · `export/` · `import/template/` · `import/` · `offers/` |
| Supply chain | `supply-chain/overview/` · `supplier-performance/` · `options/` · `shipments/` (suppliers and purchases are in Purchase) |
| Quality | `overview/` · `trend/` · `options/` · `tests/` (GET, POST) · `standards/` · `audits/` (POST) · `report/` |
| Finance | `overview/` · `revenue-expenses/` · `cash-flow/` · `options/` · `transactions/` (GET, POST) · `budget/` (GET, PUT) |
| Reports | `reports/` (GET, POST) · `overview/` · `preview/?type=&range=` · `export/?type=&range=&format=pdf|xlsx|csv` · `<id>/download/` |
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
| Finance | admin, management, finance | admin, management, finance |
| Settings | admin, management | admin, management (only a Super Admin can manage Super Admins) |

---

## 4. Where data comes from

Most records are entered in the portal. A few kinds are entered in the **Django admin** (`/admin/`) because the portal has no form for them:

| Data | Admin section | Used by |
|---|---|---|
| Shipments (and marking them delivered / delayed) | Supply chain → Shipments | Shipment tracking, on-time delivery. Stock is added by the goods receipt in Purchase, not by the shipment |
| Sales order delivery status | Sales → Sales orders | Order status (cancelling is done in the portal so stock is returned) |
| Daily marketing numbers, top content, audience split | Marketing | Marketing overview, performance and audience charts |
| Quality standards, certifications | Quality | Standards list, certification status |

Stock always changes through movements, so product and material stock can't be edited directly: sales orders take stock out and cancellations put it back; goods receipts (GRN) add the accepted quantity of a purchase; purchase returns take stock out (and put it back if cancelled); raw-material usage is recorded under Purchase → material movements.

**Sales documents:** Customer → Quotation (Draft → Sent → Accepted / Rejected; Expired automatically after its valid-until date, daily and whenever quotations are listed) → Sales Order → Sales Invoice → Payment. Converting a quotation creates a new order or invoice with its own number and copies the customer and lines (price, discount, GST); a quotation converts once. Stock: an order takes stock out; an invoice made from an order does not move stock again; an invoice made without an order takes stock out (and puts it back if cancelled); a sales return marked "restock" puts goods back. Line totals: subtotal − discount + GST; sales figures in reports and analytics are net of GST. Quotation and invoice PDFs use company details from Settings → Company Profile and Tax & Billing, the original logo (`assets/hipa-logo.png`) and Noto Sans (`assets/fonts`, SIL Open Font License) so ₹ prints.

**Purchase rules:** a purchase is one raw material or product from one supplier; total = subtotal − discount + GST. There are no purchase orders and no purchase invoices. Payment status (Pending / Partially Paid / Paid / Overdue) comes from completed supplier payments, completed returns and the payment due date (default: purchase date + the supplier's credit days).

---

## 5. Analytics and AI

`ml/` works only on real records:

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

**Settings → Data & Backup → Back Up Now** runs `mysqldump` and saves a compressed `.sql.gz` file in `BACKUP_DIR` (default `backend/backups`).

### Daily scheduled task

The Windows Task Scheduler task **"HIPA MASALA daily tasks"** runs `scripts/daily_tasks.py` every day at 02:00. If the PC is off at that time, it runs as soon as the PC is next on. It uses `pythonw.exe`, so no window appears. It:

1. runs `run_analytics` (insights);
2. runs `run_backup --scheduled`, which backs up only when **Automatic backup** is on in Settings and deletes backups older than the chosen retention period.

Output is appended to `backend/logs/daily_tasks.log`. To run it now: `Start-ScheduledTask -TaskName "HIPA MASALA daily tasks"`. To recreate it on another PC:

```powershell
$action = New-ScheduledTaskAction -Execute "<backend>\.venv\Scripts\pythonw.exe" -Argument '"<backend>\scripts\daily_tasks.py"' -WorkingDirectory "<backend>"
Register-ScheduledTask -TaskName "HIPA MASALA daily tasks" -Action $action -Trigger (New-ScheduledTaskTrigger -Daily -At 2:00AM) -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable)
```

Each job can also be run by hand: `manage.py run_analytics`, `manage.py run_backup`.

---

## 7. Tests

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test tests
```

The test runner creates a separate `test_hipa_masala` database and deletes it afterwards; the real database is never touched. The suite covers login, tokens, password reset, role permissions for every module, every endpoint on an empty database, validation errors, CORS, and full workflows (orders and stock, purchases with goods receipts / returns / supplier payments, quality tests on goods receipts, supply chain, finance, reports in all three formats).

---

## 8. Notes and troubleshooting

- **MySQL driver:** the project uses PyMySQL (pure Python) instead of `mysqlclient`, because Windows Smart App Control blocks mysqlclient's unsigned DLL on this PC. `config/__init__.py` registers it as `MySQLdb`.
- **scikit-learn is pinned to 1.9.0 and pandas to 3.0.5** for the same reason: Smart App Control blocks a compiled file in scikit-learn 1.9.1 and in pandas 3.0.6 (`groupby`). Smart App Control can change its verdict later. If a start-up error says `An Application Control policy has blocked this file`, note the package in the error and try its previous release with `python -m pip install "<package>==<version>"`, then update `requirements.txt`.
- The analytics engine (`ml/`: pandas, scikit-learn) is loaded only when an analytics feature or `run_analytics` needs it. If one of its files is ever blocked, only those features return 503 "analytics engine unavailable"; login and every other page keep working.
- `No module named 'rest_framework'` (or `django`) → the command ran on a Python without the project packages and `.venv` is missing. Create it with the setup commands in section 1.
- `Error: That port is already in use` → another backend is already running on 8000; use it, or stop it first.
- `Access denied for user` → check `DB_USER` / `DB_PASSWORD` in `.env`. `Can't connect to MySQL server` → start the MySQL80/MySQL84 Windows service.
- The server refuses to start without `DJANGO_SECRET_KEY` and `DB_USER`, and says which variable is missing.
- For production: `DEBUG=False`, real `ALLOWED_HOSTS`, HTTPS, a dedicated MySQL user, SMTP e-mail, and serve the built frontend with `/api/` proxied to Django.
