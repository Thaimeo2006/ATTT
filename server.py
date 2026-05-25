from multiprocessing import Process, Queue, Event, Manager, Lock
from flask import Flask, request, jsonify
from core import Transaction, Block, Wallet
import json
import logging
import os
import requests
import time

PORT = 5000

def load_chain(chain_json):
    target = bytes.fromhex(chain_json["target"])
    chain = []
    for b_dict in chain_json["chain"]:
        block = Block.from_dict(b_dict)
        chain.append(block)
    return chain, target
    
def init_chain(event=None):
    first_transaction = Transaction("COINBASE", "00000000", 50)
    genesis_block = Block.create_for_mine(b"\x00"*32, bytes.fromhex("1d00ffff"), [first_transaction])
    genesis_block.mine(event)
    return [genesis_block], bytes.fromhex("1d00ffff")

def clean_mempool(mempool, transactions_list):
    remaining_mempool = [trans for trans in list(mempool) if trans not in transactions_list]
    mempool[:] = remaining_mempool

def adjust_target(target):
    pass

def listen(chain, mempool, target, lock, event):
    app = Flask(__name__)

    @app.route("/receive_chain", methods = ["GET"])
    def post_chain():
        #Enable another node receive your chain
        with lock:
            chain_list = [block.to_dict() for block in list(chain)]
            target_hex = target.value.hex()

        return jsonify({
            "target": target_hex,
            "chain": chain_list
        }), 200
    
    @app.route("/get_new_block", methods= ["POST"])
    def verify_and_add_block():
        block_json = request.json()
        try:
            new_block = Block.from_dict(block_json)
        except Exception as e:
            logging.warning(e)
            return False    
        #Check server state
        with lock:
            for i in range(0, len(chain)-1, 1):
                if (chain[i].get_hash() != chain[i+1].previous_block_hash):
                    raise Exception("Invalid old block!")

            #Check previous block hash and target of new block and out the lock
            if chain[-1] != new_block.previous_block_hash:
                logging.warning("Previous block hash is not true.")
                return False
            if target != new_block.target:
                logging.warning("Target is different.")
                return False
            
        #Check block
        b, msg = new_block.verify()
        if b:
            with lock:
                chain.append(new_block)
                clean_mempool(mempool, new_block.transactions_list)
                adjust_target(target)

        return jsonify({
            "valid": str(b),
            "msg": msg
        })
    
    app.run(host = "0.0.0.0", port= PORT)


def mine(chain, mempool, target, lock, event, wallet_public_key):
    while True:
        if len(mempool) == 0:
            time.sleep(2)
            continue

        reward_transaction = Transaction("COINBASE", wallet_public_key, 50)
        with lock:
            #Append reward transaction to the final of transaction list to mine
            trans_mine = list(mempool)+[reward_transaction]
            block_mine = Block.create_for_mine(chain[-1].get_hash(), target.value, trans_mine)
        mining_done, msg = block_mine.mine(event)
        if not mining_done:
            logging.info(msg)
            continue
        with lock:
            chain.append(block_mine)
            clean_mempool(mempool, trans_mine[-1])
            adjust_target(target)

def send_block():
    pass

if __name__ == "__main__":
    #Global var
    manager = Manager()
    mempool = manager.list([])

    lock = Lock()
    event = Event()

    #Find running server in another node, load chain and target if found
    if not os.path.exists("ip.json"):
        logging.warning("ip.json not found, server will run locally!")
        node_ips = []
        with open("ip.json", "w") as f:
            json.dump([], f)            
    else:
        with open("ip.json", "r") as f:
            node_ips = json.load(f)

    found_server = False
    if node_ips:
        for peer in node_ips:
            try:
                response = requests.get(f"http://{peer}:{PORT}/receive_chain", timeout= 3)
                if response.status_code == 200:
                    loaded_chain, loaded_target = load_chain(response.json())
                    chain = manager.list(loaded_chain)
                    target = manager.Value(bytes, loaded_target)
                    found_server = True
                    break
            except requests.exceptions.RequestException:
                continue
    
    if not found_server:
        #Only you run the server
        if os.path.exists("chain.json"):
            #Load data if this computer used to run server
            with open("chain.json", "r") as f:
                chain_json = json.load(f)
            loaded_chain, loaded_target = load_chain(chain_json)
            chain = manager.list(loaded_chain)
            target = manager.Value(bytes, loaded_target)
        else:
            #Init first block
            loaded_chain, loaded_target = init_chain()
            chain = manager.list(loaded_chain)
            target = manager.Value(bytes, loaded_target)

    #Create wallet
    if os.path.exists("my_wallet.json"):
        #Auto sign in       
        with open("my_wallet.json", "r") as f:
            wallet_json = json.load(f)
        wallet = Wallet.from_dict(wallet_json)
    else:
        #Auto sign up
        wallet = Wallet()
        wallet_json = {
            "private_key": wallet.private_key.to_string().hex()
        }
        with open("my_wallet.json", "w") as f:
            json.dump(wallet_json, f)
