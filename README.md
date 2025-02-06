# Github-Monitor
一个用于监控 GitHub 用户活动的自动化工具。可以实时追踪指定用户的仓库更新和新建仓库活动，并通过邮件通知。
## 功能特点

- 监控多个 GitHub 用户的活动
- 检测用户新建仓库
- 追踪仓库的提交更新
- 通过邮件发送实时通知
- 支持多线程并发检查
- 自定义检查时间间隔
- 支持Gmail、QQ邮箱

## 安装步骤

1. 克隆仓库：

   git clone https://github.com/yourusername/github-monitor.git

   cd github-monitor

2. 安装依赖：

   pip install -r requirements.txt

3. 修改配置：

   修改 config.py 中的邮箱配置

   修改 github_monitor.py 中的监控对象

5. 测试邮箱环境

   python test_eamil.py

7. 运行程序：

   python main.py
