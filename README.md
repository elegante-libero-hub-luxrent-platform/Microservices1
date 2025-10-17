# User & Profile Service (Microservice 1)

This service is part of a **luxury fashion rental platform**, responsible for **user accounts**, **membership levels**, and **public user profiles**.

---

## ✅ Features Implemented

### 👤 User Management
- Full CRUD (Create, Read, Update, Delete)
- Fields:
  - Name  
  - Email (unique)  
  - US Phone (`+1XXXXXXXXXX`, unique)  
  - Membership Tier (`FREE`, `PRO`, `PROMAX`)  
  - Plaintext Password (**demo only**, not hashed yet)
- Email & Phone uniqueness enforced

### 🪪 Profile Management
- Separated `Profile` resource linked to `User` via `user_id`
- Fields:
  - `username` (unique public handle)
  - `display_name`
  - `avatar_url`
  - `bio`
  - `style_tags` (for fashion preferences)
- One-to-one relationship (1 User → 1 Profile)

### 🚧 Not Implemented Yet
- Authentication / JWT Tokens
- Persistent Database (currently in-memory)
- Role / Admin system

---

## 🛠 Tech Stack

| Component | Technology |
|----------|------------|
| Language | Python 3.10+ |
| Framework | FastAPI |
| Data Models | Pydantic v2 |
| Server | Uvicorn |
| Storage | In-Memory (temporary) |

---

## 🚀 Run Locally

```bash
# 1️⃣ Create Virtual Environment
python -m venv venv

# 2️⃣ Activate Virtual Environment
# Windows (Git Bash)
source venv/Scripts/activate
# macOS/Linux
source venv/bin/activate

# 3️⃣ Install Dependencies
pip install -r requirements.txt

# 4️⃣ Start Service
python main.py
# or
uvicorn main:app --reload
