import base64
import os
import shutil
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

KEY = b'12345678901234567890123456789012'  # 32-byte key (AES-256)
BLOCK_SIZE = 16  # AES block size

def encrypt_file(file_path: str) -> str:
    with open(file_path, 'rb') as f:
        data = f.read()
    iv = os.urandom(BLOCK_SIZE)
    cipher = AES.new(KEY, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(data, BLOCK_SIZE))
    return base64.b64encode(encrypted).decode('utf-8') + ":" + base64.b64encode(iv).decode('utf-8')

def save_encrypted_to_destination(encrypted_data: str, destination_folder: str, filename: str):
    os.makedirs(destination_folder, exist_ok=True)
    destination_path = os.path.join(destination_folder, filename)
    with open(destination_path, 'w') as out:
        out.write(encrypted_data)
    print(f"✅ บันทึกไฟล์ที่เข้ารหัสแล้วเป็น {destination_path}")

src = 'script_raw.py'
dst = os.path.join(os.path.dirname(os.path.abspath(src)), 'script.py')

save_encrypted_to_destination(encrypt_file(src), *os.path.split(dst))
