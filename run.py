from nhap import *
import time

class candidate_block(Block):
    def __init__(self, index, previous_block_hash, target, nonce, transactions_list, version = b"\x01"):

class Server:
    def __init__(self):
        self.blockchain = Blockchain()
        self.mempool = []

    def mine(self):
        if self.mempool:
            candidate_transactions = self.mempool[0]
            while True:
                candidate_block = Block()
            