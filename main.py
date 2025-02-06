from github_monitor import GitHubMonitor
from config import GITHUB_TOKEN, EMAIL_CONFIG

def main():
    # 创建监控实例
    monitor = GitHubMonitor(GITHUB_TOKEN, EMAIL_CONFIG)
    
    # 要监控的GitHub用户名列表
    usernames = [
        "123", 
        "123",
        "123"  # 直接在这里添加新的作者
    ]
    
    # 开始监控（每小时检查一次）
    monitor.monitor_users(usernames, check_interval=3600)

if __name__ == "__main__":
    main() 