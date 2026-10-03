# 🚀 Phantom Wallet Clone (Python)

Phantom Wallet Simulator is a **professional, educational, and security-oriented** Python desktop application that simulates a Phantom-style cryptocurrency wallet with enterprise-grade cryptography, data structures, and a clean modern UI.

It provides a complete crypto wallet experience with deterministic seed phrases, transaction simulation, crypto balances, QR addressing, security logs, and a responsive purple-themed Phantom UI — all inside a **single Python file**.

---

## 📦 Features

### 🧑‍💼 User Interface & Wallet Flow
- Phantom-inspired dark purple UI with smooth layout  
- Create / Import Wallet using **12-seed phrases**  
- View holdings for **7 cryptocurrencies**  
- Send & receive crypto with validation and fees  
- QR Address generation & scanning  
- Sortable transaction history  

### 🛡️ Security & Cryptography
- **Fernet (AES-128-CBC + HMAC-SHA256)** encryption for seed phrases — only encrypted seeds are stored  
- Keys persist in `admin/keys/` (git-ignored), so encrypted data and signatures stay valid across restarts  
- **RSA-2048** digital signatures on every transaction  
- Secure transaction IDs via `secrets`  
- Atomic excel writes via `openpyxl`  

### 📊 Data Structures & Algorithms (DSA)
- **Linked List** → Audit log storage  
- **Stack** → Transaction undo system  
- **Queue** → Transaction processing pipeline  
- **Priority Queue** → Mempool management by transaction amount  
- **Bubble Sort** → Sorting transaction history  

### 📝 Logging System
- `admin/security_log.txt` → Cryptographic logs  
- `admin/audit_log.txt` → Transaction audit logs  
- `admin/wallets.xlsx` → Persistent wallet database  

---

## 📁 Project Structure

```

Phantom-Wallet/
│
├── wallet.py                # Main application (single-file logic)
├── requirements.txt
├── admin/
│   ├── audit_log.txt        # High-level audit trail
│   ├── security_log.txt     # Cryptographic trace logs
│   ├── wallets.xlsx         # Excel wallet storage (atomic writes, encrypted seeds)
│   └── keys/                # Generated on first run, git-ignored
│
├── assets/                  # Icons & visuals
│   ├── phantom_logo.png
│   ├── coin icons...
│
└── data/
└── TERMS_OF_SERVICE.txt

````

---

## 🧪 How to Run

### 🔧 Requirements
- Python 3.9+
- CustomTkinter
- Pillow
- Cryptography
- qrcode
- openpyxl

### ▶️ Steps

```bash
git clone https://github.com/ethanleezhan-droid/phantom.git
cd phantom
pip install -r requirements.txt
python wallet.py
```

On Linux you may also need Tk: `sudo apt install python3-tk`. On Windows and macOS (python.org installer) Tk is included.

## 💡 Credits

Built by **Anas** with dedication, curiosity, and a love for web3 and blockchain.

Special thanks to **ChatGPT** for being the smartest teammate in the room 🤝

---

## ⚖️ License & Reuse

This project is **open for learning and modification**.
Feel free to fork, remix, or improve it, just credit the original author.


---

📬 _Have feedback or want to contribute? Let’s connect!_
## 🔗 Connect With Me

- [LinkedIn](https://www.linkedin.com/in/m-ianas/)
