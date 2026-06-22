import requests
import json
from core import Wallet, Transaction
import os
import logging

print("BLOCKCHAIN CLI WALLET")

with open("node_ips.json", "r") as f:
    peers = json.load(f)

#Create own wallet and load public wallet
if os.path.exists("my_wallet.json"):
    #Auto sign in
    logging.info("Found my_wallet.json. Auto sign in...")       
    with open("my_wallet.json", "r") as f:
        wallet_json = json.load(f)
    wallet = Wallet.from_dict(wallet_json)
    print(f"{wallet.get_address()} is your wallet address and it was signed in automatically.")
else:
    #Auto sign up
    logging.info("my_wallet.json not found. Creating new wallet...")
    wallet = Wallet()
    wallet_json = {
        "private_key": wallet.private_key.to_string().hex()
    }
    with open("my_wallet.json", "w") as f:
        json.dump(wallet_json, f, indent = 4)
    print(f"{wallet.get_address()} is your wallet address and it was created since my_wallet.json not found.")

while True:
    print("Make a choice by enter the number...")
    print("1. Check the current chain")
    print("2. Show your public key")
    print("3. Show your balance")
    print("4. Make new transaction")
    print("5. Exit")

    choice = input()
    if choice == "1":
        for peer in peers:
            try:
                response = requests.get(f"{peer}/receive_chain", timeout= 2)
            except requests.exceptions.RequestException:
                continue
            print(json.dumps(response.json(), indent = 4))
            break

    elif choice == "2":
        print(wallet.get_address())

    elif choice == "3":
        for peer in peers:
            try:
                response = requests.get(f"{peer}/balance/{wallet.get_address()}", timeout = 2)
            except requests.exceptions.RequestException:
                continue
            print(response.json())
            break

    elif choice == "4":
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

    elif choice == "5":
        break

    else:
        print("Invalid choice.")