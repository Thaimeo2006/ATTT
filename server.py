from multiprocessing import Process, Event, Manager, Lock
from flask import Flask, request, jsonify
from core import Transaction, Block, Wallet, target_to_num, num_to_target
import json
import logging
import os
import requests
import time
import sys
import threading

def load_chain(chain_json):
    target = bytes.fromhex(chain_json["target"])
    chain = []
    for b_dict in chain_json["chain"]:
        block = Block.from_dict(b_dict)
        chain.append(block)
    return chain, target
    
def init_chain(wallet, event=None):
    first_transaction = Transaction.create_reward(wallet.get_address(), 50)
    genesis_block = Block.create_for_mine(b"\x00"*32, bytes.fromhex("1d00ffff"), [first_transaction])
    genesis_block.mine(event)
    return [genesis_block], bytes.fromhex("1d00ffff")

def is_valid_chain(chain):
    """Check verification of blockchain"""
    temp_chain = list(chain)
    if len(temp_chain) == 0:
        return False
        
    for i in range(1, len(temp_chain)):
        current_block = temp_chain[i]
        prev_block = temp_chain[i-1]

        #Check previous_block_hash
        if current_block.previous_block_hash != prev_block.get_hash():
            return False
            
        #Block verify
        is_valid, _ = current_block.verify()
        if not is_valid:
            return False
            
    return True

def check_txid_and_get_balance_from_chain(sender, chain, txid=None, check_txid = True):
    balance = 0
    valid_txid = True
    for block in chain:
        for trans in block.transactions_list:
            if check_txid and trans.txid == txid:
                valid_txid = False
                break
            if trans.sender == sender:
                balance -= trans.amount
            if trans.receiver == sender:
                balance += trans.amount
        if check_txid and not valid_txid: break
    return valid_txid, balance

def check_txid_and_get_balance_from_mempool(sender, mempool, txid=None, check_txid = True):
    balance = 0
    valid_txid = True
    for trans in mempool:
        if check_txid and trans.txid == txid:
            valid_txid = False
            break
        if trans.sender == sender:
            balance -= trans.amount
        if trans.receiver == sender:
            balance += trans.amount
    return valid_txid, balance

def clean_mempool(mempool, transactions_list):
    txid_to_remove = [trans.txid for trans in transactions_list]
    remaining_mempool = [trans for trans in list(mempool) if trans.txid not in txid_to_remove]
    mempool[:] = remaining_mempool

def adjust_target(chain, target):
    # BLOCKS_PER_EPOCH, TARGET_TIMESPAN in reality are 2016 and 14 days respectively.
    # If you want to test in local computer, you can set them lower to see the change immediately.
    BLOCKS_PER_EPOCH = 2016 
    TARGET_TIMESPAN = 14 * 24 * 60 * 60
    MAX_TARGET = target_to_num(bytes.fromhex("1d00ffff"))

    # Adjust only if len(chain) is multiples of BLOCK_PER_EPOCH
    if len(chain) % BLOCKS_PER_EPOCH != 0:
        return
    
    last_block = chain[-1]
    first_block_in_epoch = chain[-BLOCKS_PER_EPOCH] 

    actual_timespan = last_block.timestamp - first_block_in_epoch.timestamp

    # If block mining too fast or slow, set the limit
    if actual_timespan < TARGET_TIMESPAN // 4:
        actual_timespan = TARGET_TIMESPAN // 4

    if actual_timespan > TARGET_TIMESPAN * 4:
        actual_timespan = TARGET_TIMESPAN * 4

    # Calculate new target
    current_target_num = target_to_num(target.value)
    new_target_num = (current_target_num * actual_timespan) // TARGET_TIMESPAN

    # Make sure that new target is lower than MAX_TARGET
    if new_target_num > MAX_TARGET:
        new_target_num = MAX_TARGET

    # Update
    old_target_hex = target.value.hex()
    target.value = num_to_target(new_target_num)
    
    logging.info(f"--- ĐIỀU CHỈNH ĐỘ KHÓ ---")
    logging.info(f"Target cũ: {old_target_hex}")
    logging.info(f"Target mới: {target.value.hex()}")

def send_new_transaction(peer_url, tx_dict):
    try:
        requests.post(f"{peer_url}/make_new_transaction?from_server=true", json=tx_dict, timeout=3)
        logging.info(f"[Broadcast TX] Đã gửi giao dịch tới {peer_url}")
    except requests.exceptions.RequestException:
        pass

def broadcast_transaction(transaction, node_ips):
    trans_dict = transaction.to_dict()
    for ip in node_ips:
        t = threading.Thread(target=send_new_transaction, args=(ip, trans_dict), daemon=True)
        t.start()

def send_new_block(peer_url, block_dict):
    try:
        requests.post(f"{peer_url}/get_new_block", json=block_dict, timeout=3)
        logging.info(f"Đã gửi block tới {peer_url}")
    except requests.exceptions.RequestException:
        pass

def broadcast_block(block, node_ips):
    block_dict = block.to_dict()
    
    for ip in node_ips:
        t = threading.Thread(target=send_new_block, args=(ip, block_dict), daemon= True)
        t.start()

def solve_conflicts(chain, target, node_ips):
    """
    Find and replace the state by the longer chain if found
    """
    longest_chain = None
    max_length = len(chain)
    new_target = None

    for peer in node_ips:
        try:
            response = requests.get(f"{peer}/receive_chain", timeout=3)
            if response.status_code == 200:
                chain_json = response.json()
                peer_length = len(chain_json["chain"])
                
                # Chỉ kiểm tra nếu chuỗi của họ DÀI HƠN chuỗi của mình
                if peer_length > max_length:
                    temp_chain, temp_target = load_chain(chain_json)
                    
                    # Xác thực toàn bộ chuỗi của họ
                    if is_valid_chain(temp_chain):
                        max_length = peer_length
                        longest_chain = temp_chain
                        new_target = temp_target
        except requests.exceptions.RequestException:
            continue

    # If found longer valid chain
    if longest_chain:
        chain[:] = longest_chain
        target.value = new_target
        return True
        
    return False

def save_state(chain, target, ip, pw_json):
    try:
        chain_list = [block.to_dict() for block in list(chain)]
        state = {
            "chain": chain_list,
            "target": target.value
        }
        with open("chain.json", "w") as f:
            json.dump(state, f)
        logging.info("Save state successfully.")
    except Exception as e:
        logging.warning(f"Error while saving the state: {e}")

    try:
        with open("ip.json", "w") as f:
            json.dump(list(ip), f)
        logging.info("Save IP list successfully.")
    except Exception as e:
        logging.warning(f"Error while saving IP list: {e}")

    try:
        with open("public_wallet.json", "w") as f:
            json.dump(pw_json, f)
        logging.info("Save public wallet list successfully.")
    except Exception as e:
        logging.warning(f"Error while saving public wallet list: {e}")

def listen(chain, mempool, target, public_wallet, state_lock, event, mempool_lock, pw_lock, node_ips):
    app = Flask(__name__)

    @app.route("/receive_chain", methods = ["GET"])
    def post_chain():
        #Enable another node receive your chain
        with state_lock:
            chain_list = [block.to_dict() for block in list(chain)]
            target_hex = target.value.hex()

        return jsonify({
            "target": target_hex,
            "chain": chain_list
        }), 200
    
    @app.route("/get_new_block", methods= ["POST"])
    def verify_and_add_block():
        block_json = request.get_json()
        try:
            new_block = Block.from_dict(block_json)
        except Exception as e:
            logging.warning(e)
            return jsonify({
                "valid": "False",
                "msg": str(e)
            }), 400  
        #Check server state
        with state_lock:
            if len(chain) == 0:
                return jsonify({
                    "valid": "undefined",
                    "msg": "Server is in setup process."
                }), 400
            for i in range(0, len(chain)-1, 1):
                if (chain[i].get_hash() != chain[i+1].previous_block_hash):
                    raise Exception("Invalid old block!")

            #Check previous block hash and target of new block and out the state_lock
            if chain[-1].get_hash() != new_block.previous_block_hash:
                logging.warning("Previous block hash is not true.")

                will_replace = solve_conflicts(chain, target, node_ips)
                if will_replace:
                    logging.info("Replaced by the longest chain in the network.")

                    event.set()
                    with mempool_lock:
                        for block in chain:
                            clean_mempool(mempool, block.transactions_list)
                    return jsonify({
                        "valid": "False",
                        "msg": "Chain was outdated."
                    })

                return jsonify({
                    "valid": "False",
                    "msg": "Previous block hash is not true."
                }), 400
                
            if target.value != new_block.target:
                logging.warning("Target is different.")
                return jsonify({
                    "valid": "False",
                    "msg": "Target is different."
                }), 400
            
        #Check block
        b, msg = new_block.verify()
        if b:
            event.set()
            with state_lock:
                chain.append(new_block)
                adjust_target(chain, target)
            with mempool_lock:
                clean_mempool(mempool, new_block.transactions_list)
            return jsonify({
                "valid": "True",
                "msg": msg
            }), 200
        else:
            return jsonify({
                "valid": "False",
                "msg": msg
            }), 400
    
    @app.route("/new_wallet", methods= ["POST"])
    def verify_key_and_save():
        response = request.get_json()
        if not response or "public_key" not in response:
            return jsonify({
                "valid": "False",
                "msg": "Bad response. Missing public_key." 
            }), 400
        else:
            new_wallet_public_key = response["public_key"]
        
        with pw_lock:
            if new_wallet_public_key in public_wallet:
                return jsonify({
                    "valid": "False",
                    "msg": "This address was already existed. Please try again."
                }), 400
            else:
                public_wallet.append(new_wallet_public_key)
            return jsonify({
                "valid": "True",
                "msg": "New_wallet created successfully. Now you can make transaction by CLI."
            }), 201
        
    @app.route("/make_new_transaction", methods= ["POST"])
    def verify_add_and_broadcast_transaction():
        #Check if from server node
        is_from_server = request.args.get("from_server")
        response = request.get_json()
        try:
            new_transaction = Transaction.from_dict(response)
        except Exception as e:
            return jsonify({
                "valid": "False",
                "msg": str(e)
            }), 400

        b, msg = new_transaction.verify()
        if not b: return jsonify({
            "valid": "False",
            "msg": msg
        }), 400
        with state_lock:
            valid_in_chain, sender_balance_from_chain = check_txid_and_get_balance_from_chain(new_transaction.sender, chain, new_transaction.txid)
        with mempool_lock:
            valid_in_mempool, sender_balance_from_mempool = check_txid_and_get_balance_from_mempool(new_transaction.sender, mempool, new_transaction.txid)
        if not valid_in_chain or not valid_in_mempool:
            return jsonify({
                "valid": "False",
                "msg": "Txid is duplicated."
            }), 400
        if new_transaction.amount > sender_balance_from_chain+sender_balance_from_mempool:
            return jsonify({
                "valid": "False",
                "msg": "You dont have enough balance."
            }), 400
        with mempool_lock:
            mempool.append(new_transaction)
        
        if not is_from_server:
            broadcast_transaction(new_transaction, node_ips)
        return jsonify({
            "valid": "True",
            "msg": "Transaction was verified successfully, please wait until it added to the chain."
        }), 200
    
    @app.route("/balance/<public_key>", methods= ["GET"])
    def send_balance(public_key):
        with state_lock: _, balance_from_chain = check_txid_and_get_balance_from_chain(public_key, chain, check_txid= False)
        with mempool_lock: _, balance_from_mempool = check_txid_and_get_balance_from_mempool(public_key, mempool, check_txid= False)
        balance = balance_from_chain+balance_from_mempool
        return jsonify({
            "balance": balance,
            "msg": f"Here is the balance of wallet which address {public_key}. If balance equals to zero, maybe this wallet is not exist."
        }), 200

    
    app.run(host = "0.0.0.0", port= 5000, use_reloader= False)


def mine(chain, mempool, target, state_lock, mempool_lock, event, wallet_public_key, node_ips):
    while True:
        if len(mempool) == 0:
            time.sleep(2)
            continue

        reward_transaction = Transaction.create_reward(wallet_public_key, 50)
        #Append reward transaction to the final of transaction list to mine
        with mempool_lock:
            trans_mine = list(mempool)+[reward_transaction]
        with state_lock: 
            block_mine = Block.create_for_mine(chain[-1].get_hash(), target.value, trans_mine)
        mining_done, msg = block_mine.mine(event)
        if not mining_done:
            logging.info(msg)
            continue
        with state_lock:
            chain.append(block_mine)
            adjust_target(chain, target)
        with mempool_lock:
            clean_mempool(mempool, trans_mine[:-1])

        logging.info("Broadcasting mined block to another node...")
        broadcast_block(block_mine, node_ips)

if __name__ == "__main__":
    #Global var: mempool, chain, target, public_wallet
    manager = Manager()
    mempool = manager.list([])
    

    state_lock = Lock()
    mempool_lock = Lock()
    event = Event()

    pw_lock = Lock()

    #Create own wallet and load public wallet
    if os.path.exists("my_wallet.json"):
        #Auto sign in       
        with open("my_wallet.json", "r") as f:
            wallet_json = json.load(f)
        wallet = Wallet.from_dict(wallet_json)
        with open("public_wallet.json", "r") as f:
            public_wallet = manager.list(json.load(f))
    else:
        #Auto sign up, create empty public_wallet.json and add your own public key to this
        wallet = Wallet()
        wallet_json = {
            "private_key": wallet.private_key.to_string().hex()
        }
        with open("my_wallet.json", "w") as f:
            json.dump(wallet_json, f)
        public_wallet = manager.list([wallet.get_address()])

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
                response = requests.get(f"{peer}/receive_chain", timeout= 3)
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
            loaded_chain, loaded_target = init_chain(wallet)
            chain = manager.list(loaded_chain)
            target = manager.Value(bytes, loaded_target)


    ListenProcess = Process(target= listen, args = (chain, mempool, target, public_wallet, state_lock, event, mempool_lock, pw_lock, node_ips))
    MineProcess = Process(target = mine, args = (chain, mempool, target, state_lock, mempool_lock, event, wallet.get_address(), node_ips))

    ListenProcess.start()
    MineProcess.start()

    try:
        ListenProcess.join()
        MineProcess.join()
    except KeyboardInterrupt:
        logging.info("Shutting down server. Please wait from saving data to Disk...")

        ListenProcess.terminate()
        MineProcess.terminate()
        ListenProcess.join()
        MineProcess.join()
        
        save_state(chain, target, node_ips, list(public_wallet))
        sys.exit(0)
                        