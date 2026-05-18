import hashlib
import time
import json
import warnings
import copy
from ecdsa import SigningKey, VerifyingKey, SECP256k1
from ecdsa.util import sigencode_der, sigdecode_der

HASH = hashlib.sha256

def target_to_num(target: bytes):
    exponent, coefficient = target[:1], target[1:]
    e, c = int.from_bytes(exponent, "big"), int.from_bytes(coefficient, "big")
    return c * (1<<(8*(e-3)))


def merkle(transactions_list):
    if not transactions_list: return b"\x00"*32
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
        self.signature = signature

    def to_dict(self):
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "amount": self.amount,
            "timestamp": self.timestamp
        }
    
    def get_sign_bytes(self):
        return json.dumps(self.to_dict(), sort_keys=True).encode()

    def get_hash(self):
        all_dict = self.to_dict()
        all_dict["signature"] = self.signature
        return HASH(json.dumps(all_dict, sort_keys = True).encode()).digest()

class Block:
    def __init__(self, previous_block_hash, target, transactions_list, version = bytes.fromhex("00000001")):
        #self.index = index
        self.version = version                              #4 bytes
        self.previous_block_hash = previous_block_hash      #32 bytes
        self.merkle_root = merkle(transactions_list)        #32 bytes
        self.timestamp = time.time()                        #4 bytes
        self.target = target                                #4 bytes
        self.nonce = 0                                      #4 bytes
        self.transactions_list = transactions_list

    def get_hash(self):
        header_bytes = self.version+self.previous_block_hash+self.merkle_root+int(self.timestamp).to_bytes(4, "big")+self.target+self.nonce.to_bytes(4, "big")
        return HASH(header_bytes).digest()
    
    def mine(self):
        num = target_to_num(self.target)
        while True:
            if int.from_bytes(self.get_hash(), "big") < num:
                break
            self.nonce += 1

class blockchain_server:
    def __init__(self):
        self.target = bytes.fromhex("1d00ffff")        
        self.chain = []
        self.add_genesis_block()        
        self.mempool = []
        self.trans_mining = None
        self.block_mining = None

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

class Wallet:
    def __init__(self, username):
        self.username = username
        self.private_key = SigningKey.generate(curve=SECP256k1)
        self.public_key = self.private_key.get_verifying_key()

    def get_address(self):
        public_key_bytes = self.public_key.to_string()
        return HASH(public_key_bytes).hexdigest()
    
    def sign_transaction(self, data):
        return self.private_key.sign(data, sigencode=sigencode_der)
    


