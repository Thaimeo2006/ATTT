import requests
import json
from core import Wallet, Transaction
import os

print("BLOCKCHAIN CLI WALLET")

with open("node_ips.json", "r") as f:
    peers = json.load(f)

if os.path.exists("my_wallet.json"):
    #Auto sign in       
    with open("my_wallet.json", "r") as f:
        wallet_json = json.load(f)
    wallet = Wallet.from_dict(wallet_json)
    print(f"{wallet.get_address()} is your wallet address and it was signed in automatically.")
else:
    #Auto sign up
    found_valid_key = False
    found_running_server = False
    while True:
        wallet = Wallet()
        public_key_json = {
            "public_key": wallet.get_address()
        }
        for peer in peers:
            try:
                response = requests.post(f"{peer}/new_wallet", json= public_key_json, timeout= 2)
            except requests.exceptions.RequestException:
                continue
            found_running_server = True
            if response.status_code == 201:
                found_valid_key = True
                break

        if not found_running_server:
            raise ConnectionError("Not found running server. Perhaps you have to check your network.")
        if found_valid_key:
            break
    
    with open("my_wallet.json", "w") as f:
        json.dump({"private_key": wallet.private_key.to_string().hex()}, f)
    print(f"{wallet.get_address()} is your wallet address and it was created since my_wallet.json not found.")

while True:
    print("Make a choice by enter the number...")
    print("1. Check the current chain")
    print("2. Show your balance")
    print("3. Make new transaction")
    print("4. Exit")

    choice = input()
    if choice == "1":
        for peer in peers:
            try:
                response = requests.get(f"{peer}/receive_chain", timeout= 2)
            except requests.exceptions.RequestException:
                continue
            print(response.json())
            break

    elif choice == "2":
        for peer in peers:
            try:
                response = requests.get(f"{peer}/balance/{wallet.get_address()}", timeout = 2)
            except requests.exceptions.RequestException:
                continue
            print(response.json())
            break

    elif choice == "3":
        receiver = input("Enter hex value of the receiver: ")
        while True:
            try:
                amount = int(input("Enter the amount (int): "))
            except ValueError:
                print("Invalid amount.")
                continue
            if amount < 0: print("???")
            else: break

        new_transaction = Transaction.new(wallet.get_address(), receiver, amount)
        new_transaction.sign_and_hash(wallet)

        for peer in peers:
            try:
                response = requests.post(f"{peer}/make_new_transaction", json = new_transaction.to_dict(), timeout= 2)
            except requests.exceptions.RequestException:
                print(f"Connect to {peer} failed")
                continue
            print(response.json())
            break

    elif choice == "4":
        break

    else:
        print("Invalid choice.")