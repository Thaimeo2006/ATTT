import hashlib
import time
import json
import logging
from ecdsa import SigningKey, VerifyingKey, SECP256k1
from ecdsa.util import sigencode_der, sigdecode_der

HASH = hashlib.sha256
VERSION = bytes.fromhex("00000001")             #4 bytes
SEPARATORS = (",", ":")
COINBASE_ADDRESS = bytes.hex(b"COINBASE")

def target_to_num(target: bytes):
    exponent, coefficient = target[:1], target[1:]
    e, c = int.from_bytes(exponent, "big"), int.from_bytes(coefficient, "big")
    return c * (1<<(8*(e-3)))


def merkle(transactions_list):
    if not transactions_list: return b"\x00"*32
    hash_list = [bytes.fromhex(transaction.txid) for transaction in transactions_list]
    result = []
    while len(hash_list)>1:
        l = len(hash_list)
        for i in range(0, l-1, 2):
            result.append(HASH(hash_list[i]+hash_list[i+1]).digest())
        if l%2 != 0:
            result.append(HASH(hash_list[-1]*2).digest())

        hash_list = result[:]
        result.clear()

    return hash_list[0]

class Wallet:
    def __init__(self):
        self.private_key = SigningKey.generate(curve=SECP256k1)
        self.public_key = self.private_key.get_verifying_key()

    @classmethod
    def from_dict(cls, wallet_json):
        wallet = cls.__new__(cls)
        wallet.private_key = SigningKey.from_string(bytes.fromhex(wallet_json["private_key"]), curve=SECP256k1)
        wallet.public_key = wallet.private_key.get_verifying_key()
        return wallet

    def get_address(self):
        return self.public_key.to_string().hex()
    
    def sign_transaction(self, data):
        return self.private_key.sign(data, sigencode=sigencode_der)

class Transaction:
    def __init__(self, sender, receiver, amount):
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        self.timestamp: int = None
        self.signature = None
        self.txid = None

    @classmethod
    def new(cls, sender, receiver, amount):
        t = cls(sender, receiver, amount)
        t.timestamp = int(time.time())
        return t
    
    @classmethod
    def create_reward(cls, receiver, amount):
        t = cls(COINBASE_ADDRESS, receiver, amount)
        t.signature = "0x"+"00"*32
        info = {
            "sender": t.sender,
            "receiver": t.receiver,
            "amount": t.amount,
            "timestamp": t.timestamp,
            "signature" : t.signature
        }
        t.txid = HASH(json.dumps(info, sort_keys= True, separators= SEPARATORS).encode()).hexdigest()
        return t
    
    @classmethod
    def from_dict(cls, trans_json):
        t = cls(trans_json["sender"], trans_json["receiver"], trans_json["amount"])
        t.timestamp, t.signature, t.txid = trans_json["timestamp"], trans_json["signature"], trans_json["txid"]
        return t

    def sign_and_hash(self, wallet: Wallet):
        if wallet.get_address() != self.sender:
            logging.warning("Sign not your transaction???")
            return
        
        info = {
            "sender": self.sender,
            "receiver": self.receiver,
            "amount": self.amount,
            "timestamp": self.timestamp
        }
        data = HASH(json.dumps(info, sort_keys= True, separators= SEPARATORS).encode()).digest()
        self.signature = wallet.private_key.sign(data, sigencode= sigencode_der).hex()
        info["signature"] = self.signature
        self.txid = HASH(json.dumps(info, sort_keys= True, separators= SEPARATORS).encode()).hexdigest()

    def to_dict(self):
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "amount": self.amount,
            "timestamp": self.timestamp,
            "signature": self.signature,
            "txid": self.txid
        }
    
    def verify(self):
        info = {
            "sender": self.sender,
            "receiver": self.receiver,
            "amount": self.amount,
            "timestamp": self.timestamp        
        }
        data = HASH(json.dumps(info, sort_keys= True, separators= SEPARATORS).encode()).digest()

        verify_key = VerifyingKey.from_string(bytes.fromhex(self.sender), curve= SECP256k1)
        try:
            is_valid_signature = verify_key.verify(bytes.fromhex(self.signature), data, sigdecode = sigdecode_der)
        except Exception as e:
            return False, str(e)

        info["signature"] = self.signature
        check_txid = HASH(json.dumps(info, sort_keys=True, separators= SEPARATORS).encode()).hexdigest()
        if self.txid != check_txid:
            return False, "Invalid txid."
        else:
            return True, "Sucessfully verified."


class Block:
    def __init__(self):
        self.version: bytes = VERSION                          
        self.previous_block_hash: bytes = None     
        self.merkle_root: bytes = None   
        self.timestamp: int = None                   
        self.target: bytes = None                               
        self.nonce: int = 0                                      
        self.transactions_list: list = None

    @classmethod
    def create_for_mine(cls, previous_block_hash, target, transactions_list):
        b = cls()
        b.previous_block_hash = previous_block_hash      #32 bytes
        b.merkle_root = merkle(transactions_list)        #32 bytes
        b.timestamp = int(time.time())                   #4 bytes
        b.target = target                                #4 bytes
        b.nonce = 0                                      #4 bytes
        b.transactions_list = transactions_list
        return b
    
    @classmethod
    def from_dict(cls, block_json):
        b = cls()
        b.version = bytes.fromhex(block_json["version"])     
        b.previous_block_hash = bytes.fromhex(block_json["previous_block_hash"])
        b.merkle_root = bytes.fromhex(block_json["merkle_root"])
        b.timestamp = block_json["timestamp"]
        b.target = bytes.fromhex(block_json["target"])
        b.nonce = block_json["nonce"]
        b.transactions_list = [Transaction.from_dict(trans) for trans in block_json["transactions"]]
        return b

    def get_hash(self):
        header_bytes = self.version+self.previous_block_hash+self.merkle_root+self.timestamp.to_bytes(4, "big")+self.target+self.nonce.to_bytes(4, "big")
        return HASH(header_bytes).digest()
    
    def mine(self, event=None) -> bool:
        #Return True if done mining, False if mining is interrupted
        num = target_to_num(self.target)
        for self.nonce in range(0, 1<<32):
            if event is not None and event.is_set():
                return False, "Mining is interrupted since listen process verified and added new block."
            if int.from_bytes(self.get_hash(), "big") < num:
                return True, "Found nonce!"
        return False, "Unluckily, no suitable nonce found."

    def to_dict(self):
        return {
            "version": self.version.hex(),
            "previous_block_hash": self.previous_block_hash.hex(),
            "merkle_root": self.merkle_root.hex(),
            "timestamp": self.timestamp,
            "target": self.target.hex(),
            "nonce": self.nonce,
            "transactions": [trans.to_dict() for trans in self.transactions_list],
        }
    
    def verify(self):
        if self.version != VERSION:
            return False, "Block use another verion."
        if self.timestamp < 0 or self.timestamp > int(time.time()):
            return False, "Start time of mining block process is unreal."
        for trans in self.transactions_list[:-1]:
            b, msg = trans.verify()
            if not b:
                return False, f"{msg} in {trans}"
        reward_trans = self.transactions_list[-1]
        if reward_trans.sender != "COINBASE" or reward_trans.amount != 50:
            return False, "Invalid reward transation"
        if self.merkle_root != merkle(self.transactions_list):
            return False, "Invalid merkle root."
        num = target_to_num(self.target)
        if int.from_bytes(self.get_hash(), "big") >= num:
            return False, "Block was uncompletely mined, hash is still too big."
        return True, "Block passed verification."
