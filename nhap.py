import hashlib
import time
import json
import warnings
import copy

HASH = hashlib.sha256

def target_to_num(target: bytes):
    exponent, coefficient = target[:1], target[1:]
    e, c = int.from_bytes(exponent), int.from_bytes(coefficient)
    return c * (1<<(8*(e-3)))


def merkle(transactions_list):
    hash_list = [transaction.get_hash() for transaction in transactions_list]
    result = []
    while len(hash_list)>1:
        l = len(hash_list)
        for i in range(0, l-1, 2):
            result.append(HASH(hash_list[i]+hash_list[i+1]).digest())
        if i == l-1:
            result.append(HASH(hash_list[l-1]*2).digest())

        hash_list = copy.deepcopy(result)
        result.clear()

    return hash_list[0]

class Transaction:
    def __init__(self, sender, receiver, amount, signature = ""):
        #self.index = index
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        self.timestamp = time.time()
        #self.signature = signature

    def to_dict(self):
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "amount": self.amount,
            "timestamp": self.timestamp
        }

    def get_hash(self):
        return hashlib.sha256(json.dumps(self.to_dict()).encode()).digest()

class Block:
    def __init__(self, index, previous_block_hash, target, transactions_list, version = b"\x01"):
        self.index = index
        self.version = version                              #4 bytes
        self.previous_block_hash = previous_block_hash      #32 bytes
        self.merkle_root = merkle(transactions_list)        #32 bytes
        self.timestamp = time.time()                        #4 bytes
        self.target = target                                #4 bytes
        self.nonce = 0                                      #4 bytes
        self.transactions_list = transactions_list

    def get_hash(self):
        header_bytes = self.version+self.previous_block_hash+self.merkle_root+self.timestamp+self.target+self.nonce
        return hashlib.sha256(header_bytes).digest()
    
    def mine(self):
        while True:
            num = target_to_num(self.target)
            if self.get_hash() < num:
                return self

    
class Blockchain:
    def __init__(self):
        self.length = 1
        self.target = bytes.fromhex("1d00ffff")
        genesis_block = Block(0, b"\x00"*32, b"\x00"*32, self.target, 2083236893, [])
        self.chain = [genesis_block]

    def verify_and_add_block(self, new_block: Block):                    #Call only after receive new block
        for i in range(0, self.length-1, 1):
            if (self.chain[0].get_hash() != self.chain[1].previous_block_hash):
                raise Exception("Invalid old block!")
                exit()

        if (self.chain[self.length-1].get_hash() != new_block.previous_block_hash):
            warnings.warn("Invalid new block request!")

        else:
            self.chain.append(new_block)
            self.length += 1
            if self.length%2016 == 0:
                self.reduce_target()

    def reduce_target(self):
        self.target /= 2

    

