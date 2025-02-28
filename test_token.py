import requests
from datetime import datetime
import sys

class Colors:
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    ENDC = '\033[0m'

def test_token(token):
    """测试 GitHub Token 的权限"""
    session = requests.Session()
    if token:
        session.headers.update({'Authorization': f'token {token}'})
    
    print(f"\n{Colors.BLUE}开始测试 GitHub Token...{Colors.ENDC}\n")
    
    # 1. 测试基本认证
    try:
        response = session.get('https://api.github.com/user')
        if response.status_code == 200:
            user_data = response.json()
            print(f"{Colors.GREEN}✓ Token 认证成功{Colors.ENDC}")
            print(f"Token 所属用户: {user_data.get('login')}")
            print(f"用户类型: {user_data.get('type')}")
        else:
            print(f"{Colors.RED}✗ Token 认证失败 (状态码: {response.status_code}){Colors.ENDC}")
            return False
    except Exception as e:
        print(f"{Colors.RED}✗ Token 认证测试出错: {str(e)}{Colors.ENDC}")
        return False

    # 2. 测试API速率限制
    try:
        response = session.get('https://api.github.com/rate_limit')
        if response.status_code == 200:
            limits = response.json()
            core_limit = limits['resources']['core']
            print(f"\n{Colors.BLUE}API 速率限制信息:{Colors.ENDC}")
            print(f"剩余请求次数: {core_limit['remaining']}/{core_limit['limit']}")
            reset_time = datetime.fromtimestamp(core_limit['reset']).strftime('%Y-%m-%d %H:%M:%S')
            print(f"重置时间: {reset_time}")
        else:
            print(f"{Colors.RED}✗ 无法获取速率限制信息{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.RED}✗ 检查速率限制时出错: {str(e)}{Colors.ENDC}")

    # 3. 测试特定用户的仓库访问
    test_user = "airdropinsiders"
    print(f"\n{Colors.BLUE}测试访问用户 {test_user} 的仓库:{Colors.ENDC}")
    
    try:
        # 测试用户信息访问
        response = session.get(f'https://api.github.com/users/{test_user}')
        if response.status_code == 200:
            print(f"{Colors.GREEN}✓ 可以访问用户信息{Colors.ENDC}")
        else:
            print(f"{Colors.RED}✗ 无法访问用户信息 (状态码: {response.status_code}){Colors.ENDC}")
            print(f"错误信息: {response.text}")

        # 测试仓库列表访问
        response = session.get(f'https://api.github.com/users/{test_user}/repos')
        if response.status_code == 200:
            repos = response.json()
            print(f"{Colors.GREEN}✓ 可以访问用户仓库列表{Colors.ENDC}")
            print(f"仓库数量: {len(repos)}")
            
            # 测试第一个仓库的提交访问
            if repos:
                first_repo = repos[0]['name']
                response = session.get(f'https://api.github.com/repos/{test_user}/{first_repo}/commits')
                if response.status_code == 200:
                    print(f"{Colors.GREEN}✓ 可以访问仓库提交记录{Colors.ENDC}")
                else:
                    print(f"{Colors.RED}✗ 无法访问仓库提交记录 (状态码: {response.status_code}){Colors.ENDC}")
                    print(f"错误信息: {response.text}")
        else:
            print(f"{Colors.RED}✗ 无法访问用户仓库列表 (状态码: {response.status_code}){Colors.ENDC}")
            print(f"错误信息: {response.text}")
            
    except Exception as e:
        print(f"{Colors.RED}✗ 测试仓库访问时出错: {str(e)}{Colors.ENDC}")

if __name__ == "__main__":
    # 从 config.py 导入 token
    try:
        from config import GITHUB_TOKEN
        test_token(GITHUB_TOKEN)
    except ImportError:
        print(f"{Colors.RED}错误: 无法从 config.py 导入 GITHUB_TOKEN{Colors.ENDC}")
        sys.exit(1) 