import requests
import smtplib
import json
import time
import threading
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime, timezone
from typing import Dict, List
from queue import Queue
import os
import ssl

# Windows系统启用ANSI支持
if os.name == 'nt':
    os.system('color')

class Colors:
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    ENDC = '\033[0m'  # 结束颜色

class GitHubMonitor:
    def __init__(self, token, email_config):
        self.session = requests.Session()
        if token:
            self.session.headers.update({'Authorization': f'token {token}'})
            # 验证 token
            try:
                response = self.session.get('https://api.github.com/user')
                if response.status_code == 200:
                    print(f"{Colors.GREEN}GitHub Token 验证成功{Colors.ENDC}")
                else:
                    print(f"{Colors.RED}GitHub Token 可能无效: {response.status_code}{Colors.ENDC}")
            except Exception as e:
                print(f"{Colors.RED}验证 GitHub Token 时出错: {str(e)}{Colors.ENDC}")
        self.email_config = email_config
        self.last_check = {}
        self.known_repos = {}
        self.notification_queue = Queue()
        self.update_file = 'update.json'
        self.state_file = 'monitor_state.json'
        self.inaccessible_repos = {}  # 新增：记录无法访问的仓库
        self.load_state()  # 加载上次的状态

    def load_state(self):
        """加载上次保存的监控状态"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    self.known_repos = state.get('repos', {})
                    self.last_check = state.get('last_check', {})
                    self.inaccessible_repos = state.get('inaccessible_repos', {})  # 加载无法访问的仓库记录
                    print(f"{Colors.BLUE}已加载上次的监控状态{Colors.ENDC}")
            else:
                print(f"{Colors.BLUE}未找到历史状态，将创建新的监控状态{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.RED}加载状态文件失败: {str(e)}{Colors.ENDC}")

    def save_state(self):
        """保存当前的监控状态"""
        try:
            state = {
                'repos': self.known_repos,
                'last_check': self.last_check,
                'inaccessible_repos': self.inaccessible_repos,  # 保存无法访问的仓库记录
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            print(f"{Colors.BLUE}已保存当前监控状态{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.RED}保存状态文件失败: {str(e)}{Colors.ENDC}")

    def load_update_history(self):
        """加载历史更新记录"""
        try:
            if os.path.exists(self.update_file):
                with open(self.update_file, 'r', encoding='utf-8') as f:
                    self.update_history = json.load(f)
            else:
                self.update_history = []
        except Exception as e:
            print(f"{Colors.RED}加载更新历史记录失败: {str(e)}{Colors.ENDC}")
            self.update_history = []

    def save_update(self, update_info):
        """保存更新信息到JSON文件"""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            update_record = {
                'timestamp': current_time,
                'subject': update_info['subject'],
                'content': update_info['content']
            }
            
            # 添加新的更新记录
            self.update_history.append(update_record)
            
            # 保存到文件
            with open(self.update_file, 'w', encoding='utf-8') as f:
                json.dump(self.update_history, f, ensure_ascii=False, indent=2)
            
            print(f"{Colors.BLUE}更新信息已保存到 {Colors.YELLOW}{self.update_file}{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.RED}保存更新信息失败: {str(e)}{Colors.ENDC}")

    def get_user_repos(self, username: str) -> List[Dict]:
        """获取用户的所有仓库"""
        url = f'https://api.github.com/users/{username}/repos'
        try:
            response = self.session.get(url)
            
            # 添加详细的错误信息输出
            if response.status_code != 200:
                print(f"{Colors.RED}获取用户 {username} 仓库失败:")
                print(f"状态码: {response.status_code}")
                print(f"响应内容: {response.text}{Colors.ENDC}")
                return []
            
            return response.json()
        except Exception as e:
            print(f"{Colors.RED}获取用户 {username} 仓库时出错: {str(e)}{Colors.ENDC}")
            return []

    def get_repo_commits(self, username: str, repo: str, since: str = None, limit: int = None) -> List[Dict]:
        """获取仓库的提交记录"""
        url = f'https://api.github.com/repos/{username}/{repo}/commits'
        params = {}
        if since:
            params['since'] = since
        if limit:
            params['per_page'] = limit
        
        try:
            response = self.session.get(url, params=params)
            
            # 只在出错时显示详细信息
            if response.status_code != 200:
                print(f"{Colors.RED}获取仓库 {repo} 提交记录失败 (状态码: {response.status_code}){Colors.ENDC}")
                return []
            
            return response.json()
        except Exception as e:
            print(f"{Colors.RED}获取仓库 {repo} 提交记录时出错{Colors.ENDC}")
            return []

    def send_email(self, subject: str, content: str):
        """发送邮件通知"""
        msg = MIMEText(content, 'plain', 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = self.email_config['sender']
        msg['To'] = self.email_config['receiver']

        try:
            if self.email_config['smtp_port'] == 587:
                # 使用 STARTTLS
                server = smtplib.SMTP(self.email_config['smtp_server'], 587)
                server.starttls()  # 升级到 TLS 连接
            else:
                # 使用 SSL
                server = smtplib.SMTP_SSL(self.email_config['smtp_server'], 465)
            
            # 登录并发送
            server.login(self.email_config['sender'], self.email_config['password'])
            server.send_message(msg)
            server.quit()
            
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{current_time}] 邮件发送成功: {subject}")
            
        except Exception as e:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{current_time}] 邮件发送失败: {str(e)}")

    def check_user_activity(self, username):
        """检查用户活动，包括新建仓库和更新"""
        try:
            response = self.session.get(f"https://api.github.com/users/{username}/repos")
            if response.status_code != 200:
                return []
                
            current_repos = response.json()
            notifications = []
            
            # 获取当前所有仓库的最新状态
            current_state = {}
            for repo in current_repos:
                repo_name = repo['name']
                
                # 获取仓库的最后更新时间
                last_updated = repo['updated_at']
                
                # 获取提交记录
                commits = self.get_repo_commits(username, repo_name, limit=5)
                if not commits:  # 如果获取失败，使用仓库的更新时间
                    current_state[repo_name] = {
                        'created_at': repo['created_at'],
                        'updated_at': last_updated,
                        'html_url': repo['html_url'],
                        'has_commits': False
                    }
                    continue
                
                # 记录仓库状态
                current_state[repo_name] = {
                    'created_at': repo['created_at'],
                    'updated_at': last_updated,
                    'html_url': repo['html_url'],
                    'has_commits': True,
                    'latest_commit': commits[0]['commit']['author']['date'] if commits else None
                }
            
            # 首次运行时，只记录状态不发送通知
            if username not in self.known_repos:
                print(f"{Colors.BLUE}首次运行，记录用户 {username} 的初始状态{Colors.ENDC}")
                self.known_repos[username] = current_state
                self.save_state()
                return []
            
            # 对比状态并生成通知
            for repo_name, repo_state in current_state.items():
                # 检查新仓库
                if repo_name not in self.known_repos[username]:
                    notifications.append((
                        f"GitHub通知: {username} 创建了新仓库 {repo_name}",
                        f"新仓库信息:\n仓库名称: {repo_name}\n创建时间: {repo_state['created_at']}\n仓库地址: {repo_state['html_url']}"
                    ))
                    continue
                
                # 检查更新
                old_state = self.known_repos[username][repo_name]
                
                # 比较更新时间
                if repo_state['updated_at'] > old_state['updated_at']:
                    # 确认是真实更新
                    if (repo_state['has_commits'] and 
                        (not old_state.get('latest_commit') or 
                         repo_state['latest_commit'] > old_state.get('latest_commit', ''))):
                        notifications.append((
                            f"GitHub更新通知: {username}/{repo_name}",
                            f"仓库有新的更新\n仓库地址: {repo_state['html_url']}\n"
                            f"更新时间: {repo_state['updated_at']}"
                        ))
            
            # 更新状态
            self.known_repos[username] = current_state
            self.save_state()
            
            return notifications
            
        except Exception as e:
            print(f"{Colors.RED}检查用户 {username} 时出错: {str(e)}{Colors.ENDC}")
            return []

    def check_user_updates(self, username: str):
        """检查单个用户的更新，包括新仓库和现有仓库的更新"""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{Colors.GREEN}{current_time}{Colors.ENDC}] {Colors.BLUE}正在检查用户 {Colors.YELLOW}{username}{Colors.ENDC} {Colors.BLUE}的活动...{Colors.ENDC}")
            
            # 检查新建仓库和更新
            notifications = self.check_user_activity(username)
            
            # 处理所有通知
            for subject, content in notifications:
                update_info = {
                    'subject': subject,
                    'content': content
                }
                # 保存到JSON文件
                self.save_update(update_info)
                # 加入邮件队列
                self.notification_queue.put(update_info)
            
            # 更新最后检查时间
            self.last_check[username] = datetime.now(timezone.utc).isoformat()
            
            if not notifications:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{Colors.GREEN}{current_time}{Colors.ENDC}] {Colors.BLUE}用户 {Colors.YELLOW}{username}{Colors.ENDC} {Colors.BLUE}没有新的更新{Colors.ENDC}")
            
        except Exception as e:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{Colors.GREEN}{current_time}{Colors.ENDC}] {Colors.RED}检查用户 {Colors.YELLOW}{username}{Colors.ENDC} {Colors.RED}时出错: {str(e)}{Colors.ENDC}")

    def notification_sender(self):
        """处理通知队列的线程"""
        while True:
            try:
                notification = self.notification_queue.get()
                self.send_email(notification['subject'], notification['content'])
                self.notification_queue.task_done()
            except Exception as e:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{current_time}] 发送通知时出错: {str(e)}")

    def monitor_users(self, usernames: List[str], check_interval: int = 1800):
        """使用多线程监控多个用户的仓库更新"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{Colors.GREEN}{current_time}{Colors.ENDC}] {Colors.BLUE}开始监控以下用户:{Colors.ENDC}")
        for username in usernames:
            print(f"- {Colors.YELLOW}{username}{Colors.ENDC}")
        print(f"{Colors.BLUE}检查间隔: {check_interval}秒{Colors.ENDC}")
        print(f"{Colors.BLUE}程序已成功启动...{Colors.ENDC}\n")
        
        # 初始化所有用户的最后检查时间
        for username in usernames:
            if username not in self.last_check:
                self.last_check[username] = datetime.now(timezone.utc).isoformat()

        # 启动通知发送线程
        notification_thread = threading.Thread(target=self.notification_sender, daemon=True)
        notification_thread.start()

        status_interval = 900  # 每15分钟显示一次状态（900秒）
        last_status_time = time.time()
        last_check_time = time.time()

        # 立即进行第一次检查
        print(f"[{Colors.GREEN}{current_time}{Colors.ENDC}] {Colors.BLUE}正在进行首次检查...{Colors.ENDC}")
        self._perform_check(usernames)
        last_check_time = time.time()
        next_check_time = datetime.fromtimestamp(last_check_time + check_interval)
        print(f"[{Colors.GREEN}{current_time}{Colors.ENDC}] {Colors.BLUE}首次检查完成{Colors.ENDC}")
        print(f"{Colors.BLUE}下次检查时间: {Colors.YELLOW}{next_check_time.strftime('%Y-%m-%d %H:%M:%S')}{Colors.ENDC}\n")

        while True:
            try:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # 每15分钟显示运行状态
                if time.time() - last_status_time >= status_interval:
                    print(f"\n[{Colors.GREEN}{current_time}{Colors.ENDC}] {Colors.BLUE}监控程序正在运行中...{Colors.ENDC}")
                    print(f"{Colors.BLUE}监控用户: {Colors.YELLOW}{', '.join(usernames)}{Colors.ENDC}")
                    
                    # 计算下次检查时间
                    next_check_time = datetime.fromtimestamp(last_check_time + check_interval)
                    time_until_next_check = (next_check_time - datetime.now()).total_seconds()
                    hours = int(time_until_next_check // 3600)
                    minutes = int((time_until_next_check % 3600) // 60)
                    seconds = int(time_until_next_check % 60)
                    
                    print(f"{Colors.BLUE}下次检查时间: {Colors.YELLOW}{next_check_time.strftime('%Y-%m-%d %H:%M:%S')}{Colors.ENDC}")
                    print(f"{Colors.BLUE}距离下次检查还有: {Colors.YELLOW}{hours:02d}:{minutes:02d}:{seconds:02d}{Colors.ENDC}")
                    print(f"{Colors.BLUE}程序运行正常...{Colors.ENDC}\n")
                    
                    last_status_time = time.time()

                # 检查是否到达检查间隔时间
                if time.time() - last_check_time >= check_interval:
                    print(f"\n[{Colors.GREEN}{current_time}{Colors.ENDC}] {Colors.BLUE}开始新一轮检查...{Colors.ENDC}")
                    self._perform_check(usernames)
                    last_check_time = time.time()
                    next_check_time = datetime.fromtimestamp(last_check_time + check_interval)
                    print(f"[{Colors.GREEN}{current_time}{Colors.ENDC}] {Colors.BLUE}本轮检查完成{Colors.ENDC}")
                    print(f"{Colors.BLUE}下次检查时间: {Colors.YELLOW}{next_check_time.strftime('%Y-%m-%d %H:%M:%S')}{Colors.ENDC}")
                    
                    # 显示初始倒计时
                    time_until_next_check = check_interval
                    hours = int(time_until_next_check // 3600)
                    minutes = int((time_until_next_check % 3600) // 60)
                    seconds = int(time_until_next_check % 60)
                    print(f"{Colors.BLUE}距离下次检查还有: {Colors.YELLOW}{hours:02d}:{minutes:02d}:{seconds:02d}{Colors.ENDC}\n")
                
                # 短暂休眠以减少CPU使用
                time.sleep(10)
                
            except Exception as e:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{Colors.GREEN}{current_time}{Colors.ENDC}] {Colors.RED}监控过程中出现错误: {str(e)}{Colors.ENDC}")
                print(f"{Colors.YELLOW}程序将在60秒后重试...{Colors.ENDC}")
                time.sleep(60)

    def _perform_check(self, usernames):
        """执行实际的检查操作"""
        threads = []
        for username in usernames:
            thread = threading.Thread(target=self.check_user_updates, args=(username,))
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

    def check_rate_limit(self):
        """检查 API 速率限制"""
        try:
            response = self.session.get('https://api.github.com/rate_limit')
            if response.status_code == 200:
                limits = response.json()
                core_limit = limits['resources']['core']
                remaining = core_limit['remaining']
                limit = core_limit['limit']
                reset_time = datetime.fromtimestamp(core_limit['reset']).strftime('%Y-%m-%d %H:%M:%S')
                
                print(f"\n{Colors.BLUE}API 速率限制状态:{Colors.ENDC}")
                print(f"剩余请求次数: {remaining}/{limit}")
                print(f"重置时间: {reset_time}")
                
                if remaining < 10:  # 当剩余请求次数较少时发出警告
                    print(f"{Colors.RED}警告: API 请求次数即将用尽！{Colors.ENDC}")
                    
                return remaining > 0
        except Exception as e:
            print(f"{Colors.RED}检查 API 速率限制时出错: {str(e)}{Colors.ENDC}")
            return True  # 出错时默认继续执行

    def get_with_retry(self, url, params=None, max_retries=3, retry_delay=5):
        """带重试机制的 GET 请求"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params)
                
                if response.status_code == 403 and 'rate limit exceeded' in response.text.lower():
                    print(f"{Colors.RED}API 速率限制已达到，等待重置...{Colors.ENDC}")
                    self.check_rate_limit()  # 显示限制信息
                    return None
                    
                response.raise_for_status()
                return response
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    print(f"{Colors.YELLOW}请求失败，{retry_delay}秒后重试... ({attempt + 1}/{max_retries}){Colors.ENDC}")
                    time.sleep(retry_delay)
                else:
                    print(f"{Colors.RED}请求失败，已达到最大重试次数{Colors.ENDC}")
                    raise 