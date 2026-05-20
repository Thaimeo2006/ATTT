from core import *
from flask import Flask, request, jsonify
from threading import Thread, Event, Lock
import time
import requests
import warnings
import os

#global: chain, mempool, target, lock, event
lock = Lock()
event = Event()
event.set()

class blockchain_server:
    def __init__(self):
        self.wallet: Wallet
        if os.path.exists("wallet.json"):
            with open("wallet.json", "r") as f:
                wallet_json = json.load(f)
            self.wallet.username = wallet_json["username"]
            self.wallet.private_key = SigningKey.from_string(bytes.fromhex(wallet_json["private_key"]), curve=SECP256k1)
            self.wallet.public_key = self.wallet.private_key.get_verifying_key()
        else:
            self.wallet = Wallet("Node")
            wallet_json = {
                "username": self.wallet.username,
                "private_key": self.wallet.private_key.to_string.hex()
            }
            with open("wallet.json", "w") as f:
                json.dump(wallet_json, f)

        self.node_ips = json.load("ip.json")
        found_server = False
        if self.node_ips:
            for peer in self.node_ips:
                try:
                    response = requests.get(f"{peer}/chain", timeout= 3)
                    if response.status_code == 200:
                        self.chain = response.json().get("chain")
                        self.target = response.json().get("target")
                        found_server = True
                        break
                except requests.exceptions.RequestException:
                    continue
        
        if not found_server:
            if os.path.exist("chain.json"):
                with open("chain.json", "r") as f:
                    chain_json = json.load(f)
                self.load_chain(chain_json)
                #self.target = bytes.fromhex("1d00ffff")             
            else:
                self.chain = []
                self.add_genesis_block()   


        self.mempool = []
        self.trans_mining = None
        self.block_mining = None
        self.enable_mine = True

    def background_mine(self):

        if not self.enable_mine:
            print("Mining is disabled!")
        else:
            while True:
                if not self.mempool:
                    time.sleep(1)
                    continue
                event.wait()
                with lock:
                    reward_transaction = Transaction("COINBASE", self.wallet.get_address(), 50)
                    self.trans_mining = self.mempool+[reward_transaction]
                    self.block_mining = Block(self.chain[-1].get_hash(), self.target, self.trans_mining)
                    self.block_mining.mine()

                    self.done_mine()


    def add_genesis_block(self):
        first_transaction = Transaction("COINBASE", "00000000", 50)
        genesis_block = Block(b"\x00"*32, self.target, [first_transaction])
        genesis_block.mine()
        self.chain.append(genesis_block)

    def verify_and_add_block(self, new_block: Block):
        l = len(self.chain)                   
        for i in range(0, l-1, 1):
            if (self.chain[i].get_hash() != self.chain[i+1].previous_block_hash):
                raise Exception("Invalid old block!")

        if (self.chain[-1].get_hash() != new_block.previous_block_hash):
            warnings.warn("Invalid new block request!")

        else:
            self.chain.append(new_block)
            l+=1
            if l%2016 == 0:
                self.reduce_target()

    def reduce_target(self):
        pass
        #self.target /= 2

    def mine(self):
        if self.mempool:
            self.trans_mining = self.mempool[:]
            self.block_mining = Block(self.chain[-1].get_hash(), self.target, self.trans_mining)
            self.block_mining.mine()

    def done_mine(self):
        self.chain.append(self.block_mining)

        mined_hash = {trans.get_hash() for trans in self.trans_mining}
        self.mempool = [trans for trans in self.mempool if trans.get_hash() not in mined_hash]
        
        self.block_mining = None
        self.trans_mining = None

    def load_chain(self, chain_json):
        self.target = bytes.fromhex(chain_json["target"])
        self.chain = []
        for b_dict in chain_json["chain"]:
            txs = []
            for tx_dict in b_dict["transactions"]:
                tx = Transaction(tx_dict["sender"], tx_dict["receiver"], tx_dict["amount"], tx_dict.get("signature", ""))
                tx.timestamp = tx_dict["timestamp"]
                txs.append(tx)

            block = Block(
                previous_block_hash=bytes.fromhex(b_dict["previous_block_hash"]),
                target=bytes.fromhex(b_dict["target"]),
                transactions_list=txs,
                version=bytes.fromhex(b_dict["version"])
            )
            block.merkle_root = bytes.fromhex(b_dict["merkle_root"])
            block.timestamp = b_dict["timestamp"]
            block.nonce = b_dict["nonce"]
            self.chain.append(block)

    def save_chain(self):
        chain_json = {
            "chain": [block.to_dict() for block in self.chain],
            "target": self.target.hex()
        }
        with open("chain.json", "w") as f:
            json.dump(chain_json, f, indent= "\t")

app = Flask(__name__)
Server = blockchain_server()

def broadcast_block(block_dict: dict):
    for peer in Server.node_ips:
        url = f"{peer}/receive_new_block"
        try:
            requests.post(url, json = block_dict, timeout=2)
        except requests.exceptions.RequestException:
            warnings.warn(f"Cannot send block to {peer}: Request timed out")

mine_thread = Thread(target= background_mining, daemon= True)
mine_thread.start()
@app.route("/chain", methods= ["GET"])
def get_chain():
    with chain_lock:
        chain_list = [block.to_dict() for block in Server.chain]
        target_hex = Server.target.hex()

    return jsonify({
        "target": target_hex,
        "chain": chain_list
    }), 200

@app.route("/new_wallet", method = ["POST"])
def create_wallet():
    data = request.get_json()
    username = data.get("username")
    new_wallet = Wallet("username")
    return jsonify({
        "username": username,
        "address": new_wallet.get_address,
        "private_key": new_wallet.private_key.to_string().hex(),
        "message": "Sign up successfully (Balance is 0)! Make new transaction to init."
    }), 201

@app.route("/transactions/new", method= ["POST"])
def new_transaction():
    global is_mining
    data = request.get_json()

    trans = Transaction(data["sender"], data["receiver"], data["amount"], data.get("signature", ""))   

    with chain_lock:
        Server.mempool.append(trans)
        print(f"New transaction received. Mempool now is:\n{Server.mempool}")

    if not is_mining:
        is_mining = True

    return jsonify({"message": "Transaction added to mempool!"})

@app.route("/receive_new_block", methods = ["POST"])
def receive_block():
    global is_mining
    block_request = request.get_json()
    print("Received new block from another node!")

    with chain_lock:
        stop_mining_event.set()



if __name__ == "__main__":
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("-o", "--option", required=True, choices= ["on", "off"])
    parser.add_argument("-p", "--port", default = 5000, type= int, help="Port to listen from another node")
    args = parser.parse_args()
