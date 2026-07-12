<img width="436" height="745" alt="Screenshot 2026-07-12 at 21 37 51" src="https://github.com/user-attachments/assets/b53ee224-ad59-4a88-b2c8-a515edbf8a34" />
# 🍛 BachatKhana

**Khana Bachao. Paise Bachao.**

🌍 **Live demo:** [bachatkhana.onrender.com](https://bachatkhana.onrender.com)
*(Free hosting — first load can take 30–50 seconds while the app wakes up. Login OTP appears on screen — demo mode, no SMS needed.)*

BachatKhana is a surplus-food marketplace app that lets local food businesses (sweet shops, bakeries, tiffin services, caterers) sell their end-of-day surplus to nearby customers at 50–70% off — with self-pickup, so every order is margin-positive from day one.

🏙️ **Launch city: Indore, India** — the country's cleanest city and the food capital of Central India.

## 📸 App preview

<img src="screenshot.png" width="320" alt="BachatKhana app screenshot">

---

## ✨ Features

- 📱 **Mobile-first web app** — works on any phone browser, no install needed
- 🔐 **OTP login** — phone-number based auth with sessions (dev mode shows OTP on screen; SMS provider plugs into one function)
- 🌐 **8 languages** — Hinglish, English, हिंदी, मराठी, ગુજરાતી, বাংলা, தமிழ், తెలుగు (full UI switch, Baloo font family across all scripts)
- 🎟️ **Pickup "Parchi" system** — every order generates a unique code (e.g. `IND-4827`); sellers verify it in one tap at handover
- 💳 **Razorpay UPI payments** — real payment flow with server-side HMAC signature verification and idempotent order creation (demo mode when keys are absent)
- 🏪 **Seller dashboard** — list surplus in under 2 minutes, verify parchis, track listings
- 📊 **Live impact counters** — meals saved, customer savings, food rescued (kg)
- 💾 **SQLite database** — listings, orders, users, sessions persist across restarts

## 🛠️ Tech stack

| Layer      | Tech                                             |
|------------|--------------------------------------------------|
| Frontend   | React 18 (single-file, via Babel standalone)     |
| Backend    | Python — Flask + Flask-CORS                      |
| Database   | SQLite                                           |
| Payments   | Razorpay (Orders API + signature verification)   |
| Hosting    | Render (gunicorn)                                |

## 🚀 Run locally

```bash
pip install flask flask-cors razorpay
python backend.py
```

Then open **http://localhost:5050** in your browser.

> Dev mode is ON by default — the login OTP appears on screen and in the terminal, so no SMS setup is needed for testing.

## 🌍 Deploy (Render)

1. Push `backend.py`, `index.html`, and `requirements.txt` to a GitHub repo
2. On [Render](https://render.com): **New → Web Service** → select the repo
3. **Start command:**
   ```bash
   gunicorn backend:app --bind 0.0.0.0:$PORT
   ```
4. Instance type: **Free** → Deploy

## 💳 Enable real payments (Razorpay)

Set these environment variables (on Render: **Environment** tab; locally: paste into the CONFIG section of `backend.py`):

```
RAZORPAY_KEY_ID=rzp_test_xxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxx
```

Without keys, the app runs in **demo payment mode** (full flow, no real money). Test-mode keys let you use Razorpay's sandbox (UPI: `success@razorpay`). Live keys require Razorpay KYC.

> ⚠️ Never commit real keys to the repository.

## 📁 Project structure

```
bachatkhana/
├── backend.py         # Flask server: auth, listings, orders, payments, impact
├── index.html         # Full React app: customer + seller + login (8 languages)
├── requirements.txt   # Python dependencies
├── screenshot.png     # App preview for this README
└── bachatkhana.db     # SQLite database (auto-created — do NOT commit)
```

## 🗺️ Roadmap

- [x] Marketplace core: listings → booking → parchi → verification
- [x] OTP login + sessions
- [x] Razorpay integration (test mode)
- [x] Live deployment on Render
- [ ] SMS OTP provider (MSG91) for production
- [ ] FSSAI-verified seller onboarding + trust badges
- [ ] Persistent managed database (Postgres) for pilot
- [ ] Seller analytics & caterer bulk listings
- [ ] Pilot: Vijay Nagar + Bhawarkua, Indore — 30 shops

## 📌 Status

🚧 **Prototype / pre-pilot.** Built to validate the model with real Indore sellers and customers. Business plan and pitch deck available on request.

---

*Built with ❤️ (and a lot of chai) — because good food belongs on plates, not in bins.*
