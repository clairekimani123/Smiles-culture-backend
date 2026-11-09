
### Backend — `Smiles-culture-backend/README.md`

```markdown
# Smiles Culture — API

Django REST API powering the Smiles Culture storefront. Handles products,
cart, orders, MPesa STK Push payments, the made-to-order deposit flow, and
owner/customer email notifications.

**Frontend:** https://github.com/clairekimani123/Smiles-culture

---

## Features

- REST API for products, variants, cart, and orders
- MPesa STK Push with idempotent callback handling
- Order state machine: `pending → paid → awaiting_deposit → in_production
  → shipped → delivered`
- **Made-to-order workflow** — out-of-stock items trigger a deposit request
  and an owner notification to set a production timeframe
- Email notifications via Django's mail framework (Resend in production)
- Django admin for the shop owner (order management, timeframe setting)
- Sentry error tracking

## Tech stack

| Layer      | Tool                                    |
|------------|-----------------------------------------|
| Framework  | Django 5 + Django REST Framework        |
| Database   | SQLite (dev) / PostgreSQL (prod)        |
| Payments   | MPesa Daraja API (STK Push + C2B)       |
| Email      | Anymail + Resend                        |
| Static     | WhiteNoise                              |
| Hosting    | [Render / Railway — fill in]            |

## Running locally

```bash
# 1. Clone
git clone https://github.com/clairekimani123/Smiles-culture-backend.git
cd Smiles-culture-backend

# 2. Virtualenv
python -m venv venv
source venv/bin/activate          # macOS/Linux
# venv\Scripts\activate           # Windows

# 3. Install
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Fill in MPesa sandbox credentials and OWNER_EMAIL

# 5. Migrate + seed
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

API at http://localhost:8000, admin at http://localhost:8000/admin.

Environment variables
See .env.example for the full list. The critical ones:

Var	Purpose
SECRET_KEY	Django secret — generate with get_random_secret_key()
OWNER_EMAIL	Where "new order" / "set timeframe" alerts go
MPESA_CALLBACK_URL	Must be public HTTPS — Daraja POSTs here
FRONTEND_URL	Used for CORS and links in emails
Order state machine
text
        ┌─────────┐  paid   ┌──────┐  out of stock  ┌────────────────────┐
 new ──►│ pending │────────►│ paid │───────────────►│ awaiting_deposit   │
        └─────────┘         └──────┘                └────────┬───────────┘
                                                             │ deposit paid
                                                             ▼
                                                   ┌──────────────────┐
                                                   │  in_production   │
                                                   └────────┬─────────┘
                                                            ▼
                                                   ┌──────────────┐
                                                   │   shipped    │──► delivered
                                                   └──────────────┘
Deployment
[Render / Railway steps — fill in after you deploy]

Roadmap
□ Stock decrement with select_for_update() to prevent race conditions
□ Payment reconciliation cron for stuck pending orders
□ Refund flow
□ pytest coverage for the MPesa callback
Author
Claire Kimani — GitHub