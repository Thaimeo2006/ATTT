from core import blockchain_server, Transaction, Wallet, Block
from flask import Flask, request, jsonify
import threading
import time
import requests

app = Flask(__name__)

Server = blockchain_server()
peers = set()
node_wallet = Wallet("Node_owner")

chain_lock = threading.Lock()
stop_mining_event = threading.Event()
is_mining = False

def block_to_dict(block: Block):
    return {
        "version": block.version.hex(),
        "previous_block_hash": block.previous_block_hash.hex(),
        "merkle_root": block.merkle_root.hex(),
        "timestamp": block.timestamp,
        "target": block.target.hex(),
        "nonce": block.nonce,
        "transactions": [trans.to_dict() for trans in block.transactions_list],
    }

def background_mining():
    global is_mining
    
            