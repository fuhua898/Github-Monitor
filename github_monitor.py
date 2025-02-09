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
        self.email_config = email_config
        self.last_check = {}  # 存储上次检查时间
        self.known_repos = {}  # 存储已知的仓库列表
        self.notification_queue = Queue()  # 用于存储需要发送的通知
        self.update_file = 'update.json'  # 添加更新记录文件
        self.load_update_history()  # 加载历史更新记录

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
        response = self.session.get(url)
        return response.json()

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
            
            # 处理特定的错误状态码
            if response.status_code == 409:  # Conflict - 通常意味着空仓库
                print(f"{Colors.YELLOW}仓库 {repo} 是空仓库{Colors.ENDC}")
                return []
            elif response.status_code == 403:  # Forbidden - 可能是访问权限问题
                print(f"{Colors.YELLOW}无权限访问仓库 {repo} 的提交记录{Colors.ENDC}")
                return []
            elif response.status_code == 404:  # Not Found
                print(f"{Colors.YELLOW}仓库 {repo} 不存在或已被删除{Colors.ENDC}")
                return []
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if not any(code in str(e) for code in ['409', '403', '404']):  # 避免重复打印已处理的错误
                print(f"{Colors.RED}获取仓库 {repo} 提交记录时出错: {str(e)}{Colors.ENDC}")
            return []

    def send_email(self, subject: str, content: str):
        """发送邮件通知"""
        msg = MIMEText(content, 'plain', 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = self.email_config['sender']
        msg['To'] = self.email_config['receiver']

        try:
            if 'qq.com' in self.email_config['smtp_server']:
                # QQ邮箱使用SSL
                server = smtplib.SMTP_SSL(
                    self.email_config['smtp_server'], 
                    self.email_config['smtp_port']
                )
            else:
                # Gmail等其他邮箱使用TLS
                server = smtplib.SMTP(
                    self.email_config['smtp_server'], 
                    self.email_config['smtp_port']
                )
                server.starttls()

            # 打印详细连接信息
            print(f"正在连接到邮件服务器: {self.email_config['smtp_server']}:{self.email_config['smtp_port']}")
            
            # 登录
            print("正在尝试登录...")
            server.login(self.email_config['sender'], self.email_config['password'])
            print("登录成功")
            
            # 发送邮件
            print("正在发送邮件...")
            server.sendmail(
                self.email_config['sender'], 
                [self.email_config['receiver']], 
                msg.as_string()
            )
            
            server.quit()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{current_time}] 邮件发送成功: {subject}")
            
        except smtplib.SMTPAuthenticationError:
            print("邮箱认证失败！可能的原因：")
            print("1. 邮箱账号或密码错误")
            print("2. 如果使用QQ邮箱，请确保使用的是授权码而不是邮箱密码")
            print("3. 如果使用Gmail，请确保使用的是应用专用密码")
            raise
            
        except smtplib.SMTPException as e:
            print(f"SMTP错误: {str(e)}")
            print("可能的原因：")
            print("1. 邮箱服务器设置错误")
            print("2. 端口配置错误")
            print("3. 网络连接问题")
            raise
            
        except Exception as e:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{current_time}] 邮件发送失败: {str(e)}")
            raise

    def check_user_activity(self, username):
        """检查用户活动，包括新建仓库和更新"""
        api_url = f"https://api.github.com/users/{username}/repos"
        try:
            response = self.session.get(api_url)
            response.raise_for_status()
            current_repos = response.json()
            notifications = []
            
            # 获取已知的仓库列表
            if username not in self.known_repos:
                self.known_repos[username] = {}
                print(f"{Colors.BLUE}首次运行，记录用户 {Colors.YELLOW}{username}{Colors.ENDC} {Colors.BLUE}的仓库{Colors.ENDC}")
                
                # 初始化时获取每个仓库的信息
                for repo in current_repos:
                    repo_name = repo['name']
                    # 检查仓库是否可访问
                    commits = self.get_repo_commits(username, repo_name, limit=1)
                    self.known_repos[username][repo_name] = {
                        'created_at': repo['created_at'],
                        'description': repo['description'],
                        'html_url': repo['html_url'],
                        'topics': repo.get('topics', []),
                        'language': repo.get('language', 'Unknown'),
                        'stars': repo.get('stargazers_count', 0),
                        'last_commit': commits[0]['commit']['author']['date'] if commits else None,
                        'is_empty': len(commits) == 0
                    }
                return []
            
            # 检查新仓库和更新
            new_repos = []
            updated_repos = []
            
            for repo in current_repos:
                try:
                    repo_name = repo['name']
                    # 检查新仓库
                    if repo_name not in self.known_repos[username]:
                        new_repos.append({
                            'name': repo_name,
                            'created_at': repo['created_at'],
                            'description': repo['description'],
                            'html_url': repo['html_url'],
                            'topics': repo.get('topics', []),
                            'language': repo.get('language', 'Unknown'),
                            'stars': repo.get('stargazers_count', 0)
                        })
                        self.known_repos[username][repo_name] = {
                            'created_at': repo['created_at'],
                            'description': repo['description'],
                            'html_url': repo['html_url'],
                            'topics': repo.get('topics', []),
                            'language': repo.get('language', 'Unknown'),
                            'stars': repo.get('stargazers_count', 0),
                            'last_commit': None,
                            'is_empty': False
                        }
                        continue  # 新仓库不需要检查更新
                    
                    # 检查仓库更新，使用上次记录的提交时间
                    last_commit_time = self.known_repos[username][repo_name]['last_commit']
                    commits = self.get_repo_commits(username, repo_name, since=last_commit_time, limit=5)
                    
                    if commits and isinstance(commits, list) and len(commits) > 0:
                        # 检查最新提交是否比记录的更新
                        latest_commit = commits[0]
                        latest_commit_time = latest_commit['commit']['author']['date']
                        
                        if last_commit_time is None or latest_commit_time > last_commit_time:
                            # 只有真正有新提交时才添加到更新列表
                            updated_repos.append({
                                'name': repo_name,
                                'commit': latest_commit,
                                'html_url': repo['html_url']
                            })
                            # 更新最后提交时间
                            self.known_repos[username][repo_name]['last_commit'] = latest_commit_time
                except Exception as e:
                    print(f"{Colors.RED}检查仓库 {repo_name} 时出错: {str(e)}{Colors.ENDC}")
                    continue
            
            # 处理新仓库通知
            if new_repos:
                notification = f"GitHub用户 {username} 创建了新的仓库\n"
                notification += "=" * 50 + "\n\n"
                
                for repo in new_repos:
                    notification += f"仓库名称: {repo['name']}\n"
                    notification += f"创建时间: {repo['created_at']}\n"
                    notification += f"主要语言: {repo['language']}\n"
                    notification += f"描述: {repo['description'] or '无描述'}\n"
                    if repo['topics']:
                        notification += f"标签: {', '.join(repo['topics'])}\n"
                    notification += f"Star数: {repo['stars']}\n"
                    notification += f"仓库地址: {repo['html_url']}\n"
                    notification += "-" * 40 + "\n\n"
                
                notifications.append((f"GitHub通知: {username} 创建了 {len(new_repos)} 个新仓库", notification))
            
            # 处理更新通知
            if updated_repos:
                for repo in updated_repos:
                    commit = repo['commit']
                    notification = f"仓库 {repo['name']} 有新的更新:\n\n"
                    notification += f"提交信息: {commit['commit']['message']}\n"
                    notification += f"提交者: {commit['commit']['author']['name']}\n"
                    notification += f"提交时间: {commit['commit']['author']['date']}\n"
                    notification += f"仓库地址: {repo['html_url']}\n"
                    notification += "-" * 40 + "\n"
                    
                    notifications.append((f"GitHub更新通知 - {username}/{repo['name']}", notification))
            
            return notifications
            
        except Exception as e:
            print(f"{Colors.RED}检查用户 {username} 活动时出错: {str(e)}{Colors.ENDC}")
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