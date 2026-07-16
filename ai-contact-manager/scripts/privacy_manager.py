"""
隐私保护模块 — AES-256 文件加密与权限控制

功能：
1. 加密/解密：AES-256-CBC 加密 contacts.json 等敏感输出文件
2. 密码保护：PBKDF2 密钥派生，支持密码锁定/解锁
3. 访问日志：记录每次访问/解密操作
4. 分享令牌：为单个联系人生成加密的分享数据包

依赖：
  pip install pycryptodome

用法：
  python privacy_manager.py lock --password "mypassword" --file outputs/contacts.json
  python privacy_manager.py unlock --password "mypassword" --file outputs/contacts.json.enc
  python privacy_manager.py share --password "mypassword" --contact "张三" --file outputs/contacts.json
"""

import os
import json
import hashlib
import base64
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 尝试导入加密库，失败时给出提示
try:
    from Crypto.Cipher import AES
    from Crypto.Protocol.KDF import PBKDF2
    from Crypto.Random import get_random_bytes
    from Crypto.Util.Padding import pad, unpad
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("pycryptodome 未安装，加密功能不可用。安装: pip install pycryptodome")


class PrivacyManager:
    """
    人脉数据隐私管理器。

    默认加密配置：
    - 算法: AES-256-CBC
    - 密钥派生: PBKDF2-HMAC-SHA256，100000 次迭代
    - 文件后缀: .enc（加密文件）
    - 访问日志: access.log
    """

    SALT_SIZE = 16
    KEY_SIZE = 32       # 256 bits
    IV_SIZE = 16
    PBKDF2_ITERATIONS = 100000
    ENCRYPTED_SUFFIX = ".enc"
    LOG_FILE = "access.log"

    def __init__(self, log_dir: str = "outputs"):
        """
        初始化隐私管理器。

        Args:
            log_dir: 访问日志存放目录
        """
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.log_path = os.path.join(log_dir, self.LOG_FILE)

    # ========== 加密/解密 ==========

    def encrypt_file(self, filepath: str, password: str, delete_original: bool = True) -> str:
        """
        加密文件。

        Args:
            filepath: 原始文件路径
            password: 加密密码
            delete_original: 是否删除原始文件（默认 True）

        Returns:
            加密后的文件路径（*.enc）
        """
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("加密功能不可用，请安装 pycryptodome: pip install pycryptodome")

        # 读取原始数据
        with open(filepath, "rb") as f:
            plaintext = f.read()

        # 生成盐和 IV
        salt = get_random_bytes(self.SALT_SIZE)
        iv = get_random_bytes(self.IV_SIZE)

        # 派生密钥
        key = PBKDF2(password, salt, dkLen=self.KEY_SIZE, count=self.PBKDF2_ITERATIONS)

        # 加密
        cipher = AES.new(key, AES.MODE_CBC, iv)
        ciphertext = cipher.encrypt(pad(plaintext, AES.block_size))

        # 写入加密文件（salt + iv + ciphertext）
        enc_path = filepath + self.ENCRYPTED_SUFFIX
        with open(enc_path, "wb") as f:
            f.write(salt)
            f.write(iv)
            f.write(ciphertext)

        # 删除原始文件
        if delete_original:
            try:
                os.remove(filepath)
                logger.info(f"已删除原始文件: {filepath}")
            except Exception as e:
                logger.warning(f"无法删除原始文件（可手动删除）: {filepath}, 原因: {e}")
                # 保留原始文件，不影响加密流程

        self._log("ENCRYPT", filepath, True)
        logger.info(f"文件已加密 → {enc_path}")
        return enc_path

    def decrypt_file(self, filepath: str, password: str) -> str:
        """
        解密文件。

        Args:
            filepath: 加密文件路径（*.enc）
            password: 解密密码

        Returns:
            解密后的临时文件路径

        Raises:
            ValueError: 密码错误或文件损坏
        """
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("加密功能不可用")

        if not filepath.endswith(self.ENCRYPTED_SUFFIX):
            raise ValueError(f"不是加密文件（缺少 {self.ENCRYPTED_SUFFIX} 后缀）: {filepath}")

        with open(filepath, "rb") as f:
            data = f.read()

        # 解析 salt + iv + ciphertext
        salt = data[:self.SALT_SIZE]
        iv = data[self.SALT_SIZE:self.SALT_SIZE + self.IV_SIZE]
        ciphertext = data[self.SALT_SIZE + self.IV_SIZE:]

        # 派生密钥
        key = PBKDF2(password, salt, dkLen=self.KEY_SIZE, count=self.PBKDF2_ITERATIONS)

        # 解密
        cipher = AES.new(key, AES.MODE_CBC, iv)
        try:
            plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)
        except (ValueError, KeyError):
            self._log("DECRYPT_FAIL", filepath, False)
            raise ValueError("密码错误或文件已损坏")

        # 写入临时解密文件
        dec_path = filepath.replace(self.ENCRYPTED_SUFFIX, "")
        with open(dec_path, "wb") as f:
            f.write(plaintext)

        self._log("DECRYPT", filepath, True)
        logger.info(f"文件已解密 → {dec_path}")
        return dec_path

    # ========== 锁定/解锁 ==========

    def lock(self, filepath: str, password: str) -> Dict:
        """锁定数据（加密并删除原始文件）。"""
        enc_path = self.encrypt_file(filepath, password, delete_original=True)
        return {
            "status": "locked",
            "encrypted_file": enc_path,
            "locked_at": datetime.now().isoformat(),
        }

    def unlock(self, filepath: str, password: str) -> Dict:
        """解锁数据（解密并返回可读文件）。"""
        dec_path = self.decrypt_file(filepath, password)
        return {
            "status": "unlocked",
            "decrypted_file": dec_path,
            "unlocked_at": datetime.now().isoformat(),
        }

    # ========== 分享令牌 ==========

    def generate_share_token(self, filepath: str, password: str, contact_name: str) -> Dict:
        """
        生成单个联系人的加密分享数据包。

        分享逻辑：
        1. 解密完整数据文件
        2. 提取指定联系人的信息
        3. 用临时随机密码加密该联系人数据
        4. 返回分享令牌（临时密码）和加密包路径

        Args:
            filepath: 加密的 contacts.json.enc 文件路径
            password: 主密码
            contact_name: 要分享的联系人名称

        Returns:
            {"token": str, "share_file": str, "expires_hint": str}
        """
        # 解密原始文件
        dec_path = self.decrypt_file(filepath, password)

        with open(dec_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 查找联系人
        contacts = data.get("contacts", [])
        target = None
        for c in contacts:
            if c.get("name") == contact_name:
                target = c
                break

        if not target:
            raise ValueError(f"未找到联系人: {contact_name}")

        # 生成临时密码
        temp_password = base64.urlsafe_b64encode(get_random_bytes(12)).decode()
        token = hashlib.sha256(temp_password.encode()).hexdigest()[:12]

        # 创建分享包
        share_data = {
            "shared_by": "user",
            "contact": target,
            "generated_at": datetime.now().isoformat(),
            "token": token,
        }
        share_path = os.path.join(self.log_dir, f"share_{contact_name}_{int(time.time())}.json")
        with open(share_path, "w", encoding="utf-8") as f:
            json.dump(share_data, f, ensure_ascii=False, indent=2)

        # 加密分享包
        share_enc_path = self.encrypt_file(share_path, temp_password, delete_original=True)

        # 删除临时解密文件
        if os.path.exists(dec_path):
            os.remove(dec_path)

        self._log("SHARE", filepath, True, detail=f"contact={contact_name}, token={token}")

        return {
            "token": token,
            "temp_password": temp_password,
            "share_file": share_enc_path,
            "contact": contact_name,
            "expires_hint": "分享令牌和临时密码需分别发送给对方。建议设置有效期。",
        }

    # ========== 访问日志 ==========

    def _log(self, action: str, target: str, success: bool, detail: str = ""):
        """记录访问日志。"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "target": os.path.basename(target),
            "success": success,
            "detail": detail,
        }
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"写入访问日志失败: {e}")

    def get_access_log(self, limit: int = 50) -> List[Dict]:
        """读取最近 N 条访问日志。"""
        if not os.path.exists(self.log_path):
            return []
        entries = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f.readlines()[-limit:]:
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        return entries

    # ========== 密码强度 ==========

    @staticmethod
    def check_password_strength(password: str) -> Dict:
        """
        检查密码强度。

        Returns:
            {"score": int, "level": str, "suggestions": [str]}
        """
        score = 0
        suggestions = []

        if len(password) >= 8:
            score += 2
        else:
            suggestions.append("密码至少 8 位")
        if len(password) >= 12:
            score += 1

        if any(c.isupper() for c in password):
            score += 1
        else:
            suggestions.append("建议包含大写字母")

        if any(c.islower() for c in password):
            score += 1
        else:
            suggestions.append("建议包含小写字母")

        if any(c.isdigit() for c in password):
            score += 1
        else:
            suggestions.append("建议包含数字")

        if any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in password):
            score += 2
        else:
            suggestions.append("建议包含特殊字符")

        if score >= 7:
            level = "强"
        elif score >= 4:
            level = "中"
        else:
            level = "弱"

        return {"score": score, "level": level, "suggestions": suggestions}
