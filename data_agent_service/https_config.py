import ssl
import os
from typing import Optional, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class HTTPSConfig:
    """HTTPS配置管理器"""
    
    def __init__(self):
        self.cert_file: Optional[str] = None
        self.key_file: Optional[str] = None
        self.ca_file: Optional[str] = None
        self.ssl_context: Optional[ssl.SSLContext] = None
        self.https_enabled = False
        
        # 从环境变量加载配置
        self._load_from_env()
    
    def _load_from_env(self):
        """从环境变量加载HTTPS配置"""
        self.https_enabled = os.getenv("HTTPS_ONLY", "false").lower() == "true"
        self.cert_file = os.getenv("SSL_CERT_FILE")
        self.key_file = os.getenv("SSL_KEY_FILE")
        self.ca_file = os.getenv("SSL_CA_FILE")
        
        # 检查证书文件路径
        if self.https_enabled:
            if not self.cert_file or not self.key_file:
                logger.warning("HTTPS enabled but SSL certificate files not specified")
                self.https_enabled = False
            else:
                self._validate_cert_files()
    
    def _validate_cert_files(self):
        """验证证书文件是否存在"""
        if self.cert_file and not Path(self.cert_file).exists():
            logger.error(f"SSL certificate file not found: {self.cert_file}")
            self.https_enabled = False
            return
        
        if self.key_file and not Path(self.key_file).exists():
            logger.error(f"SSL private key file not found: {self.key_file}")
            self.https_enabled = False
            return
        
        if self.ca_file and not Path(self.ca_file).exists():
            logger.warning(f"SSL CA file not found: {self.ca_file}")
            self.ca_file = None
    
    def create_ssl_context(self) -> Optional[ssl.SSLContext]:
        """创建SSL上下文"""
        if not self.https_enabled or not self.cert_file or not self.key_file:
            return None
        
        try:
            # 创建SSL上下文
            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            
            # 加载证书和私钥
            context.load_cert_chain(self.cert_file, self.key_file)
            
            # 如果有CA文件，加载它
            if self.ca_file:
                context.load_verify_locations(self.ca_file)
            
            # 安全配置
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
            
            # 可选：要求客户端证书
            client_cert_required = os.getenv("SSL_CLIENT_CERT_REQUIRED", "false").lower() == "true"
            if client_cert_required:
                context.verify_mode = ssl.CERT_REQUIRED
            else:
                context.verify_mode = ssl.CERT_NONE
            
            self.ssl_context = context
            logger.info("SSL context created successfully")
            return context
            
        except Exception as e:
            logger.error(f"Failed to create SSL context: {e}")
            self.https_enabled = False
            return None
    
    def get_uvicorn_ssl_config(self) -> Dict[str, Any]:
        """获取Uvicorn的SSL配置"""
        if not self.https_enabled:
            return {}
        
        config = {
            "ssl_keyfile": self.key_file,
            "ssl_certfile": self.cert_file,
        }
        
        if self.ca_file:
            config["ssl_ca_certs"] = self.ca_file
        
        # SSL版本配置
        config["ssl_version"] = ssl.PROTOCOL_TLS_SERVER
        
        # 密码套件配置
        config["ssl_ciphers"] = 'ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS'
        
        return config
    
    def generate_self_signed_cert(self, cert_dir: str = "./certs") -> bool:
        """生成自签名证书（仅用于开发环境）"""
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            import datetime
            
            # 创建证书目录
            cert_path = Path(cert_dir)
            cert_path.mkdir(exist_ok=True)
            
            # 生成私钥
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            
            # 创建证书主题
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Beijing"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "Beijing"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "QMT Data Agent"),
                x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
            ])
            
            # 创建证书
            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                private_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.datetime.utcnow()
            ).not_valid_after(
                datetime.datetime.utcnow() + datetime.timedelta(days=365)
            ).add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.DNSName("127.0.0.1"),
                    x509.IPAddress("127.0.0.1"),
                ]),
                critical=False,
            ).sign(private_key, hashes.SHA256())
            
            # 保存私钥
            key_file = cert_path / "server.key"
            with open(key_file, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            
            # 保存证书
            cert_file = cert_path / "server.crt"
            with open(cert_file, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            
            # 更新配置
            self.cert_file = str(cert_file)
            self.key_file = str(key_file)
            self.https_enabled = True
            
            logger.info(f"Self-signed certificate generated: {cert_file}")
            logger.warning("Self-signed certificate is for development only!")
            
            return True
            
        except ImportError:
            logger.error("cryptography library not installed. Cannot generate self-signed certificate.")
            logger.info("Install with: pip install cryptography")
            return False
        except Exception as e:
            logger.error(f"Failed to generate self-signed certificate: {e}")
            return False
    
    def get_security_headers(self) -> Dict[str, str]:
        """获取安全响应头"""
        headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
        }
        
        # 如果启用HTTPS，添加HSTS头
        if self.https_enabled:
            headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        
        return headers
    
    def is_https_enabled(self) -> bool:
        """检查是否启用HTTPS"""
        return self.https_enabled
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return {
            "https_enabled": self.https_enabled,
            "cert_file": self.cert_file,
            "key_file": self.key_file,
            "ca_file": self.ca_file,
            "ssl_context_created": self.ssl_context is not None
        }

# 创建全局HTTPS配置实例
https_config = HTTPSConfig()

# 安全响应头中间件
class SecurityHeadersMiddleware:
    """安全响应头中间件"""
    
    def __init__(self):
        self.security_headers = https_config.get_security_headers()
    
    async def __call__(self, request, call_next):
        response = await call_next(request)
        
        # 添加安全响应头
        for header, value in self.security_headers.items():
            response.headers[header] = value
        
        return response

# 创建中间件实例
security_headers_middleware = SecurityHeadersMiddleware()