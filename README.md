# 🪙 Python Bitcoin Simulator

Một dự án mô phỏng mạng lưới Blockchain và tiền điện tử (tương tự Bitcoin) được viết hoàn toàn bằng Python. Dự án này phục vụ mục đích giáo dục, giúp hiểu rõ hơn về các cơ chế cốt lõi của một hệ thống tiền điện tử phi tập trung, bao gồm mã hóa, đồng thuận Proof-of-Work (PoW), kiến trúc mạng ngang hàng (P2P), và quản lý ví.

## ✨ Tính năng nổi bật

**Mật mã học & Ví (Wallet)**: Tạo cặp khóa Công khai/Bí mật (Public/Private Keys) bằng thuật toán đường cong elliptic chuẩn SECP256k1 (thông qua thư viện ecdsa).

**Giao dịch (Transactions)**: Tạo, ký số và xác minh các giao dịch. Hỗ trợ giao dịch phần thưởng (Coinbase transaction) cho thợ đào.

**Khai thác & Khối (Mining & Blocks)**: Thuật toán đồng thuận Proof-of-Work (Tìm Nonce): Tính toán Merkle Root cho danh sách giao dịch; tự động điều chỉnh độ khó (Target Adjustment) dựa trên thời gian tạo khối.

**Mạng ngang hàng (P2P Network)**:

- Sử dụng Flask để tạo các node giao tiếp qua HTTP API.

- Đồng bộ hóa chuỗi khối (Blockchain) và giải quyết xung đột (Quy tắc chuỗi dài nhất - Longest Chain Rule).

- Phát sóng (Broadcast) giao dịch và khối mới tới các node khác trong mạng (Mempool).

- Chạy song song quá trình Lắng nghe mạng (Listen) và Đào coin (Mine) bằng multiprocessing.

**Giao diện dòng lệnh (CLI Wallet)**: Tương tác với mạng lưới dễ dàng để kiểm tra số dư, xem chuỗi khối, và gửi tiền.

## 📁 Cấu trúc dự án

Dựa trên mã nguồn, dự án chia thành 3 phần chính (bạn nên lưu thành các file riêng biệt):

- core.py: Chứa logic cốt lõi (Block, Transaction, Wallet, thuật toán Merkle, mã hóa Target).

- server.py: Khởi chạy node P2P, quản lý trạng thái blockchain, API Flask, và tiến trình đào coin.

- wallet.py: Giao diện người dùng dạng dòng lệnh để thao tác với ví.

- requirements.txt: Chứa các thư viện phụ thuộc.

## 🚀 Hướng dẫn Cài đặt

1. Clone kho lưu trữ này về máy:

```bash
git clone https://github.com/Thaimeo2006/ATTT.git
cd ATTT
```

2. Cài đặt các thư viện yêu cầu:
Đảm bảo bạn đang sử dụng Python 3.x. Khuyến nghị sử dụng môi trường ảo (virtual environment).
```bash
pip install -r requirements.txt
```
(Nội dung requirements.txt: ecdsa>=0.9, flask>=3.1, requests>=2.32)

## 🛠 Hướng dẫn Sử dụng
1. Khởi chạy Node mạng (Server / Miner)

Mỗi node cần có một danh sách các IP của node khác để kết nối. Bạn hãy tạo một file node_ips.json (ví dụ: ["http://127.0.0.1:5001"]). Nếu chạy node đầu tiên, file này có thể để trống [].

Chạy node trên một port cụ thể (mặc định là 5000):
```bash
python server.py 5000
```

Lần đầu tiên chạy, hệ thống sẽ tự động tạo một ví (my_wallet.json) và khởi tạo Genesis Block (nếu chưa có node nào khác).

Cách chạy nhiều node trên cùng một máy (để test P2P):
Mở các terminal khác nhau và chạy:

- Terminal 1: python server.py 5000

- Terminal 2: python server.py 5001 (Nhớ cập nhật node_ips.json để chúng trỏ tới nhau).

2. Sử dụng Ví tương tác (CLI)

Khi mạng lưới (hoặc ít nhất 1 node) đang hoạt động, mở một terminal mới và khởi chạy ví:
```Bash
python wallet.py
```

Menu tương tác sẽ hiện ra:
```Plaintext
BLOCKCHAIN CLI WALLET
...
Make a choice by enter the number...
1. Check the current chain (Xem thông tin blockchain hiện tại)
2. Show your balance (Kiểm tra số dư)
3. Make new transaction (Tạo giao dịch gửi coin)
4. Exit (Thoát)
```

Ghi chú khi gửi giao dịch:

- Bạn cần copy địa chỉ ví (chuỗi Public Key dạng hex) của người nhận.

- Nhập số tiền nguyên (int).

- Giao dịch sẽ được đưa vào Mempool, được phát sóng (broadcast), và sẽ hiển thị trừ/cộng tiền sau khi được một thợ đào (miner) đóng gói vào khối mới.

## ⚠️ Lưu ý (Disclaimer)

Đây là một dự án mô phỏng phục vụ hoàn toàn cho mục đích giáo dục và nghiên cứu. Thuật toán mạng (HTTP API thay vì TCP Sockets thuần), quy trình lưu trữ (Lưu ra file JSON), và cơ chế mã hóa mật khẩu chưa được tối ưu hóa cho môi trường sản xuất thực tế. Tuyệt đối không sử dụng mã nguồn này để lưu trữ giá trị tài sản thật.

## 🤝 Đóng góp

Mọi đóng góp, báo lỗi (issues) hay pull requests đều được chào đón để làm cho dự án này trở thành một tài liệu học tập tốt hơn.

License: MIT (Hoặc loại giấy phép bạn muốn sử dụng)