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

class GitHubMonitor:
    def __init__(self, token, email_config):
        self.session = requests.Session()
        if token:
            self.session.headers.update({'Authorization': f'token {token}'})
        self.email_config = email_config
        self.last_check = {}  # 存储上次检查时间
        self.known_repos = {}  # 存储已知的仓库列表
        self.notification_queue = Queue()  # 用于存储需要发送的通知

    def get_user_repos(self, username: str) -> List[Dict]:
        """获取用户的所有仓库"""
        url = f'https://api.github.com/users/{username}/repos'
        response = self.session.get(url)
        return response.json()

    def get_repo_commits(self, username: str, repo: str, since: str = None) -> List[Dict]:
        """获取仓库的提交记录"""
        url = f'https://api.github.com/repos/{username}/{repo}/commits'
        params = {'since': since} if since else {}
        response = self.session.get(url, params=params)
        return response.json()

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
        """检查用户活动，包括新建仓库"""
        api_url = f"https://api.github.com/users/{username}/repos"
        try:
            response = self.session.get(api_url)
            response.raise_for_status()
            current_repos = response.json()
            
            # 获取已知的仓库列表
            if username not in self.known_repos:
                self.known_repos[username] = {repo['name']: repo['created_at'] for repo in current_repos}
                return []  # 首次运行，记录现有仓库但不发送通知
            
            # 检查新仓库
            new_repos = []
            for repo in current_repos:
                if repo['name'] not in self.known_repos[username]:
                    new_repos.append({
                        'name': repo['name'],
                        'created_at': repo['created_at'],
                        'description': repo['description'],
                        'html_url': repo['html_url']
                    })
                    self.known_repos[username][repo['name']] = repo['created_at']
            
            if new_repos:
                # 构建新仓库通知
                notification = f"用户 {username} 创建了新的仓库:\n\n"
                for repo in new_repos:
                    notification += f"仓库名称: {repo['name']}\n"
                    notification += f"创建时间: {repo['created_at']}\n"
                    notification += f"描述: {repo['description'] or '无描述'}\n"
                    notification += f"仓库地址: {repo['html_url']}\n\n"
                
                return [(f"{username} 创建了新仓库", notification)]
            
            return []
            
        except Exception as e:
            print(f"检查用户 {username} 活动时出错: {str(e)}")
            return []

    def check_user_updates(self, username: str):
        """检查单个用户的更新，包括新仓库和现有仓库的更新"""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{current_time}] 正在检查用户 {username} 的活动...")
            
            # 首先检查新建仓库
            notifications = self.check_user_activity(username)
            for subject, content in notifications:
                self.notification_queue.put({
                    'subject': subject,
                    'content': content
                })
            
            # 然后检查现有仓库的更新
            current_repos = self.get_user_repos(username)
            updates_found = False
            
            for repo in current_repos:
                try:
                    repo_name = repo['name']
                    # 获取新的提交
                    commits = self.get_repo_commits(username, repo_name, self.last_check.get(username))
                    
                    if isinstance(commits, list) and commits:  # 确保commits是列表且非空
                        updates_found = True
                        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        print(f"[{current_time}] 检测到 {username}/{repo_name} 有新的更新！")
                        
                        # 构建邮件内容
                        content = f"仓库 {repo_name} 有新的提交:\n\n"
                        for commit in commits:
                            if isinstance(commit, dict) and 'commit' in commit:
                                commit_data = commit['commit']
                                commit_msg = commit_data.get('message', 'No message')
                                commit_author = commit_data.get('author', {}).get('name', 'Unknown')
                                commit_date = commit_data.get('author', {}).get('date', 'Unknown date')
                                content += f"作者: {commit_author}\n"
                                content += f"时间: {commit_date}\n"
                                content += f"信息: {commit_msg}\n"
                                content += "-" * 50 + "\n"
                        
                        # 将通知加入队列
                        self.notification_queue.put({
                            'subject': f"GitHub更新通知 - {username}/{repo_name}",
                            'content': content
                        })
                except Exception as e:
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{current_time}] 检查仓库 {repo_name} 时出错: {str(e)}")
                    continue
            
            if not updates_found:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{current_time}] 用户 {username} 的仓库没有新的更新")
            
            # 更新最后检查时间
            self.last_check[username] = datetime.now(timezone.utc).isoformat()
            
        except Exception as e:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{current_time}] 检查用户 {username} 时出错: {str(e)}")

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

    def monitor_users(self, usernames: List[str], check_interval: int = 3600):
        """使用多线程监控多个用户的仓库更新"""
        print(f"开始监控用户: {', '.join(usernames)}")
        
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

        while True:
            try:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # 每15分钟显示运行状态
                if time.time() - last_status_time >= status_interval:
                    print(f"\n[{current_time}] 监控程序正在运行中...")
                    print(f"监控用户: {', '.join(usernames)}")
                    
                    # 计算下次检查时间
                    next_check_time = datetime.fromtimestamp(last_check_time + check_interval)
                    time_until_next_check = (next_check_time - datetime.now()).total_seconds()
                    if time_until_next_check > 0:
                        next_check_str = next_check_time.strftime("%Y-%m-%d %H:%M:%S")
                        print(f"下次检查时间: {next_check_str} (约 {int(time_until_next_check/60)} 分钟后)")
                    
                    last_status_time = time.time()

                # 检查是否到达检查间隔时间
                if time.time() - last_check_time >= check_interval:
                    print(f"\n[{current_time}] 开始新一轮检查...")
                    
                    # 为每个用户创建检查线程
                    threads = []
                    for username in usernames:
                        thread = threading.Thread(target=self.check_user_updates, args=(username,))
                        threads.append(thread)
                        thread.start()

                    # 等待所有线程完成
                    for thread in threads:
                        thread.join()

                    print(f"[{current_time}] 本轮检查完成")
                    last_check_time = time.time()
                
                # 短暂休眠以减少CPU使用
                time.sleep(60)
                
            except Exception as e:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{current_time}] 监控过程中出现错误: {str(e)}")
                time.sleep(60)  # 发生错误时等待1分钟后重试 