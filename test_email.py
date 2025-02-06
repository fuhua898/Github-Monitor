from github_monitor import GitHubMonitor
from config import EMAIL_CONFIG
import sys
import socket
import ssl

def test_gmail_connection():
    """测试与Gmail SMTP服务器的连接"""
    gmail_smtp = "smtp.gmail.com"
    ports_to_test = [587, 465]  # Gmail支持的SMTP端口
    
    print("\n正在测试Gmail连接...")
    
    # 测试基本连接
    try:
        socket.gethostbyname(gmail_smtp)
        print("✓ DNS解析正常")
    except socket.gaierror:
        print("✗ DNS解析失败，请检查网络连接或DNS设置")
        return False

    # 测试各个端口
    for port in ports_to_test:
        print(f"\n测试端口 {port}:")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        
        try:
            # 测试TCP连接
            result = sock.connect_ex((gmail_smtp, port))
            if result == 0:
                print(f"✓ 端口 {port} 连接成功")
                
                # 对于587端口，测试STARTTLS
                if port == 587:
                    try:
                        ssl_context = ssl.create_default_context()
                        with ssl_context.wrap_socket(sock, server_hostname=gmail_smtp) as ssl_sock:
                            print("✓ SSL/TLS连接成功")
                    except ssl.SSLError:
                        print("✗ SSL/TLS连接失败")
            else:
                print(f"✗ 端口 {port} 连接失败")
        except socket.timeout:
            print(f"✗ 端口 {port} 连接超时")
        except Exception as e:
            print(f"✗ 测试端口 {port} 时发生错误: {str(e)}")
        finally:
            sock.close()
    
    return True

def test_email():
    """测试邮件发送功能"""
    # 首先测试Gmail连接
    if not test_gmail_connection():
        print("\n网络环境可能不支持Gmail SMTP服务，请检查：")
        print("1. 确保网络连接稳定")
        print("2. 检查是否使用代理，某些代理可能会阻止SMTP流量")
        print("3. 检查防火墙设置，确保允许SMTP流量")
        print("4. 如果在公司网络环境，请确认是否允许SMTP流量")
        sys.exit(1)

    try:
        # 创建 GitHubMonitor 实例，使用空的 token
        monitor = GitHubMonitor("", EMAIL_CONFIG)
        
        # 发送测试邮件
        test_subject = "GitHub监控 - 邮件测试"
        test_content = """
        这是一封测试邮件。
        如果您收到这封邮件，说明邮件配置正确。
        
        邮件配置信息：
        - SMTP服务器: {smtp_server}
        - SMTP端口: {smtp_port}
        - 发件人: {sender}
        - 收件人: {receiver}
        """.format(**EMAIL_CONFIG)
        
        print("正在发送测试邮件...")
        monitor.send_email(test_subject, test_content)
        
    except Exception as e:
        print(f"测试失败！错误信息：{str(e)}")
        print("\n可能的解决方案：")
        print("1. 检查邮箱服务器地址和端口是否正确")
        print("2. 确认邮箱账号和密码是否正确")
        print("3. 如果使用Gmail，确保：")
        print("   - 已开启两步验证")
        print("   - 使用的是应用专用密码")
        print("   - 允许不够安全的应用访问（如果使用普通密码）")
        print("4. 检查防火墙是否允许SMTP连接")
        sys.exit(1)

if __name__ == "__main__":
    test_email() 