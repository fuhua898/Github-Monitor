from github_monitor import GitHubMonitor
from config import GITHUB_TOKEN, EMAIL_CONFIG

def main():
    # 创建监控实例
    monitor = GitHubMonitor(GITHUB_TOKEN, EMAIL_CONFIG)
    
    # 要监控的GitHub用户名列表
    usernames = [ 
        "1",
        "2",
        "3"
    ]
    
    # 开始监控（改为30分钟检查一次）
    monitor.monitor_users(usernames, check_interval=1800)  # 1800秒 = 30分钟

if __name__ == "__main__":
    main() 