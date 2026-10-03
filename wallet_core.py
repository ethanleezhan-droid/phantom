"""
wallet_core.py
==============

Headless core of the Phantom Wallet Simulator.

This module contains the EXACT backend logic from ``wallet.py`` — the security
manager (AES/Fernet, RSA-2048 signatures, HMAC-SHA256, SHA-256 hashing), the
data-structures-and-algorithms concepts (linked list, stack, queue, priority
queue, bubble sort), the coin metadata, and the ``WalletBackend`` class.

The only thing removed compared to ``wallet.py`` is the CustomTkinter desktop
GUI, so that the identical wallet/crypto/DSA logic can be served from a web
backend (``app.py``) without a display. No business logic was changed.
"""

import os
import time
import threading
import datetime
import hashlib
import hmac
import secrets
import shutil
import tempfile
from cryptography.fernet import Fernet
from typing import Optional
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment


# ==========================================
# Loading the Terms and Conditions
# ==========================================
def load_text_file(filename):
    """Load text content from data/ directory"""
    try:
        path = os.path.join("data", filename)
        if os.path.exists(path):
            with open(path, "r") as f:
                return f.read().strip()
    except:
        pass
    return ""


ASSETS_PATH = "assets"

if not os.path.exists(ASSETS_PATH):
    os.makedirs(ASSETS_PATH)


# ==========================================
# DSA Concepts
# ==========================================

class Node:
    def __init__(self, data):
        self.data = data
        self.next: Optional['Node'] = None


# DSA Concept: Linked List
class AuditLogLinkedList:
    def __init__(self):
        self.head: Optional[Node] = None
        self.tail: Optional[Node] = None

    def add_log(self, message):
        new_node = Node(message)
        if self.head is None:
            self.head = new_node
            self.tail = new_node
        else:
            if self.tail is not None:
                self.tail.next = new_node
            self.tail = new_node

        try:
            os.makedirs("admin", exist_ok=True)
            with open(os.path.join("admin", "audit_log.txt"), "a") as f:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] {message}\n")
        except Exception:
            pass


# DSA Concept: Stack (Undo Stack)
class UndoStack:
    def __init__(self):
        self.stack = []

    def push(self, transaction):
        self.stack.append(transaction)

    def pop(self):
        if self.stack:
            return self.stack.pop()
        return None

    def peek(self):
        if self.stack:
            return self.stack[-1]
        return None

    def size(self):
        return len(self.stack)


# DSA Concept: Queue (Transaction Queue)
class TransactionQueue:
    def __init__(self):
        self.queue = []

    def enqueue(self, transaction):
        self.queue.append(transaction)

    def dequeue(self):
        if self.queue:
            return self.queue.pop(0)
        return None

    def size(self):
        return len(self.queue)


# DSA Concept: Priority Queue (Priority Mempool)
class PriorityMempool:
    def __init__(self):
        self.mempool = []

    def add_transaction(self, priority, transaction):
        self.mempool.append({"priority": priority, "tx": transaction})
        self.mempool.sort(key=lambda x: x["priority"], reverse=True)

    def get_high_priority_tx(self):
        if self.mempool:
            return self.mempool.pop(0)
        return None

    def size(self):
        return len(self.mempool)


# ==========================================
# IS Concepts
# ==========================================

# InfoSec Concept: AES Encryption, RSA Signatures, HMAC Authentication, SHA256 Hashing
class SecurityManager:
    def __init__(self):
        # Fernet (symmetric encryption)
        self.fernet_key = Fernet.generate_key()
        self.cipher = Fernet(self.fernet_key)

        # RSA keys for digital signatures
        from cryptography.hazmat.primitives.asymmetric import rsa
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        self.public_key = self.private_key.public_key()

        # HMAC secret key
        self.hmac_key = secrets.token_bytes(32)

    def sanitize_input(self, user_input):
        if not isinstance(user_input, str):
            return str(user_input)
        return user_input.replace("<", "").replace(">", "").strip()

    def validate_amount(self, amount):
        try:
            val = float(amount)
            return val > 0
        except ValueError:
            return False

    def generate_hash(self, data):
        """SHA256 Hash"""
        encoded = str(data).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()

    def generate_hmac(self, data):
        """HMAC authentication"""
        encoded = str(data).encode('utf-8')
        return hmac.new(self.hmac_key, encoded, hashlib.sha256).hexdigest()

    def encrypt_seed_phrase(self, seed_phrase):
        """AES Encryption (via Fernet) for seed phrase"""
        try:
            seed_str = " ".join(seed_phrase) if isinstance(seed_phrase, list) else seed_phrase
            encrypted = self.cipher.encrypt(seed_str.encode())
            return encrypted.decode()
        except Exception as e:
            return None

    def decrypt_seed_phrase(self, encrypted_seed):
        """Decrypt AES encrypted seed phrase"""
        try:
            decrypted = self.cipher.decrypt(encrypted_seed.encode())
            return decrypted.decode()
        except Exception as e:
            return None

    def sign_transaction(self, tx_data):
        """RSA Digital Signature for transaction"""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        try:
            tx_str = str(tx_data).encode()
            signature = self.private_key.sign(
                tx_str,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return signature.hex()[:64]  # Return first 64 chars
        except Exception as e:
            return None

    def generate_secure_id(self, length=16):
        """Secure random ID generation"""
        return secrets.token_hex(length // 2)


# ==========================================
# COIN METADATA
# ==========================================

COIN_METADATA = {
    "BTC": {"name": "Bitcoin", "icon": "bitcoin_btc_icon_transparent.png", "network": "BTC Taproot", "fee": 0.0001, "fee_coin": "BTC"},
    "ETH": {"name": "Ethereum", "icon": "ethereum_eth_icon_transparent.png", "network": "ETH Mainnet", "fee": 0.001, "fee_coin": "ETH"},
    "SOL": {"name": "Solana", "icon": "solana_sol_icon_transparent.png", "network": "Solana", "fee": 0.01, "fee_coin": "SOL"},
    "USDT": {"name": "USDT", "icon": "usdt_tether_icon_transparent.png", "network": "BSC Mainnet", "fee": 0.001, "fee_coin": "BNB", "fee_icon": "binance_bnb_icon_transparent.png"},
    "USDC": {"name": "USDC", "icon": "usdc_usd_coin_icon_transparent.png", "network": "BSC Mainnet", "fee": 0.001, "fee_coin": "BNB", "fee_icon": "binance_bnb_icon_transparent.png"},
    "POL": {"name": "Polygon", "icon": "polygon_matic_icon_transparent.png", "network": "Polygon Network", "fee": 0.2, "fee_coin": "MATIC"},
    "BNB": {"name": "BNB", "icon": "binance_bnb_icon_transparent.png", "network": "BSC Mainnet", "fee": 0.001, "fee_coin": "BNB"},
}


# ==========================================
# CORE WALLET LOGIC
# ==========================================

class WalletBackend:
    def __init__(self):
        self.history = []
        self.holdings = {}
        self.audit_log = AuditLogLinkedList()
        self.security = SecurityManager()
        self.undo_stack = UndoStack()
        self.transaction_queue = TransactionQueue()
        self.priority_mempool = PriorityMempool()

        self.wallet_data: Optional[dict] = None
        self.observers = []

        self.prices = {
            "BTC": 94230.50,
            "ETH": 3450.20,
            "SOL": 145.80,
            "USDT": 1.00,
            "USDC": 1.00,
            "MATIC": 0.85,
            "BNB": 580.40
        }

    def subscribe(self, callback):
        self.observers.append(callback)

    def notify(self):
        for callback in self.observers:
            callback()

    def create_wallet(self, seed_phrase=None):
        try:
            seed_words = ["apple", "river", "wind", "stone", "fire", "star", "moon", "sun", "tree", "ocean", "mountain", "cloud", "earth", "sky", "rain", "snow", "cloud", "beach", "ocean", "forest", "thunder", "silver", "golden", "bright", "swift", "calm"]

            # If importing existing wallet, use provided seed
            if seed_phrase:
                seed = seed_phrase.split()
            else:
                # Create new wallet with random seed
                seed = secrets.SystemRandom().sample(seed_words, 12)

            # DETERMINISTIC ADDRESS: Hash of seed phrase always produces same address
            seed_hash = hashlib.sha256(" ".join(seed).encode()).hexdigest()
            address = "0x" + seed_hash[:40]  # Use first 40 chars of hash

            self.wallet_data = {
                "name": "My Wallet 1",
                "address": address,
                "seed": seed,
                "balance": 0.0,
                "pfp": None
            }

            # DETERMINISTIC HOLDINGS: Use seed hash to generate reproducible amounts
            self.holdings = {}
            seed_int = int(seed_hash, 16)  # Convert hex to int for seeding

            for i, (token, price) in enumerate(self.prices.items()):
                # Use deterministic values based on seed - ENSURE NON-ZERO AMOUNTS
                if token in ["BTC", "ETH", "BNB"]:
                    # Generate amount between 0.5 and 5.0
                    amount = 0.5 + (((seed_int + i * 2000) % 450) / 100.0)
                else:
                    # Generate amount between 10 and 100
                    amount = float(10 + ((seed_int + i * 3000) % 90))

                self.holdings[token] = {"amount": amount, "price": price}

            self.recalculate_balance()
            self.log_wallet_creation(seed, address)
            self.audit_log.add_log(f"Wallet created: {address}")
            self.save_wallet_to_file(status="CREATED")
            self.notify()

        except Exception as e:
            print(f"Error creating wallet: {e}")

    def update_wallet_metadata(self, new_name, new_pfp_path=None):
        if not self.wallet_data:
            return

        clean_name = self.security.sanitize_input(new_name)
        if clean_name:
            self.wallet_data["name"] = clean_name
            # Update wallet name in wallets.txt
            self.update_wallet_in_file()

        if new_pfp_path:
            try:
                filename = os.path.basename(new_pfp_path)
                unique_name = f"{self.security.generate_secure_id(8)}_{filename}"
                dest_path = os.path.join(ASSETS_PATH, unique_name)
                shutil.copy(new_pfp_path, dest_path)
                self.wallet_data["pfp"] = dest_path
                # Save wallet with PFP to wallets.txt with CREATED status
                self.save_wallet_to_file_with_pfp(status="CREATED")
            except Exception as e:
                print(f"Failed to upload PFP: {e}")

        self.audit_log.add_log("Wallet metadata updated")
        self.notify()

    def update_wallet_in_file(self):
        """Update wallet name in wallets.txt when renamed"""
        try:
            os.makedirs("admin", exist_ok=True)
            filename = os.path.join("admin", "wallets.txt")

            if not os.path.exists(filename):
                return

            # Read all lines
            with open(filename, "r") as f:
                lines = f.readlines()

            # Update wallet name in matching address row
            with open(filename, "w") as f:
                for line in lines:
                    if self.wallet_data and self.wallet_data["address"] in line and "|" in line:
                        # Reconstruct the line with updated name
                        parts = line.split("|")
                        if len(parts) >= 6:
                            wallet_id = parts[0].strip()
                            timestamp = parts[2].strip()
                            address = parts[3].strip()
                            balance = f"${self.wallet_data['balance']:>13,.2f}"
                            seed_phrase = parts[5].strip()
                            line = f"{wallet_id:<5} | {self.wallet_data['name']:<15} | {timestamp:<20} | {address:<45} | {balance} | {seed_phrase}\n"
                    f.write(line)
        except Exception as e:
            pass

    def login(self, seed_phrase):
        clean_seed = self.security.sanitize_input(seed_phrase).strip()

        # Validate seed phrase format (must be 12 words)
        words = clean_seed.split()
        if len(words) != 12 or not all(isinstance(w, str) and len(w) > 0 for w in words):
            return False

        # Pass seed phrase to create_wallet for DETERMINISTIC generation
        self.create_wallet(seed_phrase=clean_seed)

        # Restore wallet name and PFP from wallets.txt if it exists (existing wallet)
        wallet_restored = False
        if self.wallet_data is not None:
            wallet_restored = self.restore_wallet_metadata()

        # Always save wallet info (with name, PFP, and status)
        if wallet_restored:
            # IMPORTED wallet - update with IMPORTED status
            self.save_wallet_to_file_with_pfp(status="IMPORTED")
        else:
            # NEW wallet - save with CREATED status
            self.save_wallet_to_file(status="CREATED")

        self.audit_log.add_log("User logged in with seed phrase")
        self.notify()
        return True

    def restore_wallet_metadata(self):
        """Restore wallet name and PFP from wallets.xlsx. Returns True if wallet found."""
        if not self.wallet_data:
            return False
        filename = os.path.join("admin", "wallets.xlsx")
        if not os.path.exists(filename):
            return False

        wb = None
        try:
            wb = load_workbook(filename)
            ws = wb.active

            # Find matching wallet by address (Address is column E = index 4)
            for row in ws.iter_rows(min_row=2, values_only=False):
                if row[4].value == self.wallet_data.get("address"):
                    # Found matching wallet - RESTORE IT
                    if row[1].value:  # Wallet Name
                        self.wallet_data["name"] = row[1].value
                    # Check for PFP file in assets
                    if row[8].value:  # PFP Path
                        pfp_file = row[8].value
                        if os.path.exists(pfp_file):
                            self.wallet_data["pfp"] = pfp_file
                    return True  # Wallet was restored
            return False  # Wallet not found in file (new wallet)
        except Exception as e:
            return False
        finally:
            if wb:
                wb.close()

    def logout(self):
        self.wallet_data = None
        self.audit_log.add_log("User logged out")
        self.notify()

    def log_security_transaction(self, tx):
        """Log transaction with meaningful security data only"""
        os.makedirs("admin", exist_ok=True)
        with open(os.path.join("admin", "security_log.txt"), "a") as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tx_type = tx.get("type", "unknown").upper()
            tx_id = tx.get("id", "unknown")
            tx_hash = tx.get("hash", "unknown")
            token = tx.get("token", "unknown")
            amount = tx.get("amount", 0)

            # Generate cryptographic signatures
            tx_data_str = f"{tx_id}{tx_type}{token}{amount}"
            hmac_sig = self.security.generate_hmac(tx_data_str)
            rsa_sig = self.security.sign_transaction(tx_data_str)

            f.write(f"\n[{timestamp}] {tx_type} | {token} {amount}")

            if tx_type == "SEND":
                recipient = tx.get('recipient', 'N/A')
                fee = tx.get('fee', 0)
                f.write(f" -> {recipient} (Fee: {fee})")

            f.write(f"\nTransaction ID: {tx_id}\n")
            f.write(f"SHA256 Hash: {tx_hash}\n")
            f.write(f"HMAC-SHA256: {hmac_sig}\n")
            f.write(f"RSA-2048 Sig: {rsa_sig}\n")
            f.write(f"{'-'*80}\n")

    def log_wallet_creation(self, seed_phrase, address):
        """Log wallet creation with security details"""
        os.makedirs("admin", exist_ok=True)
        with open(os.path.join("admin", "security_log.txt"), "a") as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Encrypt seed phrase for logging
            encrypted_seed = self.security.encrypt_seed_phrase(seed_phrase)
            seed_hash = self.security.generate_hash(" ".join(seed_phrase))

            f.write(f"\n[{timestamp}] WALLET CREATED\n")
            f.write(f"Address: {address}\n")
            f.write(f"Encrypted Seed (AES-256): {str(encrypted_seed)[:50]}...[PROTECTED]\n")
            f.write(f"Seed Hash (SHA256): {seed_hash}\n")
            f.write(f"{'-'*80}\n")

    def send_transaction_execute(self, recipient, amount, token):
        if not self.security.validate_amount(amount):
            return "Invalid amount"
        amount = float(amount)
        recipient = self.security.sanitize_input(recipient)

        # Get network fee
        fee = COIN_METADATA.get(token, {}).get("fee", 0)
        total_amount = amount + fee

        if token not in self.holdings or self.holdings[token]["amount"] < total_amount:
            return f"❌ Insufficient funds! You have {self.holdings[token]['amount']:.6g} {token}, but need {total_amount:.6g} {token} (including {fee} fee)"

        self.holdings[token]["amount"] -= total_amount
        self.recalculate_balance()

        tx = {
            "id": self.security.generate_secure_id(8),
            "type": "send",
            "token": token,
            "amount": amount,
            "fee": fee,
            "recipient": recipient,
            "time": datetime.datetime.now(),
            "status": "pending",
            "hash": self.security.generate_hash(f"{recipient}{amount}{token}")
        }

        self.history.insert(0, tx)

        # Hook up DSA structures
        self.undo_stack.push(tx)
        self.transaction_queue.enqueue(tx)
        self.priority_mempool.add_transaction(amount, tx)

        # Log security details
        self.log_security_transaction(tx)
        self.audit_log.add_log(f"Sent {amount} {token} to {recipient} with {fee} fee")
        self.notify()

        threading.Thread(target=self._confirm_tx, args=(tx,), daemon=True).start()

        return "✅ Transaction sent successfully!"

    def receive_transaction(self, amount, token):
        # BUG FIX: Ensure token exists before receiving
        if token not in self.holdings:
            self.holdings[token] = {"amount": 0.0, "price": self.prices.get(token, 1.0)}

        tx = {
            "id": self.security.generate_secure_id(8),
            "type": "receive",
            "token": token,
            "amount": amount,
            "time": datetime.datetime.now(),
            "status": "pending",
            "hash": self.security.generate_hash(f"receive{amount}{token}")
        }

        self.history.insert(0, tx)

        # Hook up DSA structures
        self.undo_stack.push(tx)
        self.transaction_queue.enqueue(tx)
        self.priority_mempool.add_transaction(amount, tx)

        # Log security details
        self.log_security_transaction(tx)
        self.audit_log.add_log(f"Received {amount} {token}")
        self.notify()
        threading.Thread(target=self._confirm_receive, args=(tx, amount, token), daemon=True).start()

    def _confirm_tx(self, tx):
        time.sleep(2)
        tx["status"] = "confirmed"
        self.notify()

    def _confirm_receive(self, tx, amount, token):
        time.sleep(2)
        tx["status"] = "confirmed"
        # BUG FIX: Verify token exists before updating
        if token in self.holdings:
            self.holdings[token]["amount"] += amount
            self.recalculate_balance()
        self.notify()

    def recalculate_balance(self):
        total = 0
        for token, data in self.holdings.items():
            total += data["amount"] * data["price"]
        if self.wallet_data:
            self.wallet_data["balance"] = total

    def save_wallet_to_file_with_pfp(self, status="CREATED"):
        """Save wallet with PFP path and status to Excel file using atomic write"""
        os.makedirs("admin", exist_ok=True)
        filename = os.path.join("admin", "wallets.xlsx")
        wb = None
        temp_fd = None
        try:
            # Load or create workbook
            if os.path.exists(filename):
                wb = load_workbook(filename)
                ws = wb.active
            else:
                wb = Workbook()
                ws = wb.active
                ws.title = "Wallets"
                # Add headers
                headers = ["ID", "Wallet Name", "Created", "Last Access", "Address", "Balance", "Status", "Seed Phrase", "PFP Path"]
                ws.append(headers)
                # Style header row
                header_fill = PatternFill(start_color="9945FF", end_color="9945FF", fill_type="solid")
                header_font = Font(bold=True, color="FFFFFF")
                for cell in ws[1]:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal="center", vertical="center")

            # Check if wallet already exists
            wallet_exists = False
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if self.wallet_data:
                for row_idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
                    if row[4].value == self.wallet_data["address"]:
                        # Update existing wallet entry
                        row[1].value = self.wallet_data['name']
                        row[3].value = now
                        row[5].value = self.wallet_data.get('balance', 0)
                        row[6].value = status
                        row[8].value = self.wallet_data.get("pfp", "")
                        wallet_exists = True
                        break

            # If wallet doesn't exist, add new entry
            if not wallet_exists and self.wallet_data:
                wallet_id = len([row for row in ws.iter_rows(min_row=2)]) + 1
                created_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                seed_phrase = " ".join(self.wallet_data.get("seed", []))
                ws.append([
                    wallet_id,
                    self.wallet_data['name'],
                    created_date,
                    created_date,
                    self.wallet_data['address'],
                    self.wallet_data.get('balance', 0),
                    status,
                    seed_phrase,
                    self.wallet_data.get("pfp", "")
                ])

            # Use atomic write: save to temp file first, then rename
            temp_fd, temp_path = tempfile.mkstemp(suffix=".xlsx", dir="admin")
            os.close(temp_fd)
            wb.save(temp_path)
            if os.path.exists(filename):
                os.remove(filename)
            os.rename(temp_path, filename)
        except Exception as e:
            print(f"Error saving wallet to Excel: {e}")
        finally:
            if wb:
                wb.close()

    def save_wallet_to_file(self, status="CREATED"):
        """Save wallet info to admin/wallets.xlsx in Excel format with status tracking using atomic write"""
        if not self.wallet_data:
            return
        os.makedirs("admin", exist_ok=True)
        filename = os.path.join("admin", "wallets.xlsx")
        wb = None
        temp_fd = None
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Load or create workbook
            if os.path.exists(filename):
                wb = load_workbook(filename)
                ws = wb.active
            else:
                wb = Workbook()
                ws = wb.active
                ws.title = "Wallets"
                # Add headers
                headers = ["ID", "Wallet Name", "Created", "Last Access", "Address", "Balance", "Status", "Seed Phrase", "PFP Path"]
                ws.append(headers)
                # Style header row
                header_fill = PatternFill(start_color="9945FF", end_color="9945FF", fill_type="solid")
                header_font = Font(bold=True, color="FFFFFF")
                for cell in ws[1]:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal="center", vertical="center")

            # Get new wallet ID
            wallet_id = len([row for row in ws.iter_rows(min_row=2)]) + 1
            seed_phrase = " ".join(self.wallet_data.get("seed", []))
            address = self.wallet_data.get("address", "0x")
            balance = float(self.wallet_data.get("balance", 0.0))
            name = str(self.wallet_data.get("name", "My Wallet"))
            pfp_path = str(self.wallet_data.get("pfp", ""))

            # Append new wallet row
            ws.append([
                wallet_id,
                name,
                timestamp,
                timestamp,
                address,
                balance,
                status,
                seed_phrase,
                pfp_path
            ])

            # Auto-adjust column widths
            ws.column_dimensions['A'].width = 5
            ws.column_dimensions['B'].width = 18
            ws.column_dimensions['C'].width = 20
            ws.column_dimensions['D'].width = 20
            ws.column_dimensions['E'].width = 50
            ws.column_dimensions['F'].width = 15
            ws.column_dimensions['G'].width = 12
            ws.column_dimensions['H'].width = 50
            ws.column_dimensions['I'].width = 50

            # Use atomic write: save to temp file first, then rename
            temp_fd, temp_path = tempfile.mkstemp(suffix=".xlsx", dir="admin")
            os.close(temp_fd)
            wb.save(temp_path)
            if os.path.exists(filename):
                os.remove(filename)
            os.rename(temp_path, filename)
        except Exception as e:
            print(f"Error saving wallet to Excel: {e}")
        finally:
            if wb:
                wb.close()

    # DSA Concept: Bubble Sort
    def sort_history_by_amount(self, descending=True):
        n = len(self.history)
        for i in range(n):
            for j in range(0, n - i - 1):
                if descending:
                    if self.history[j]['amount'] < self.history[j + 1]['amount']:
                        self.history[j], self.history[j + 1] = self.history[j + 1], self.history[j]
                else:
                    if self.history[j]['amount'] > self.history[j + 1]['amount']:
                        self.history[j], self.history[j + 1] = self.history[j + 1], self.history[j]
        self.notify()
