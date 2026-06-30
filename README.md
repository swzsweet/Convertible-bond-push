# 可转债申购推送

每天早上九点查询当日是否有可申购的可转债，若有则通过 [Bark](https://bark.day.app/) 推送到手机。

## 工作原理

- 数据来源：东方财富可转债申购列表接口
- 判断逻辑：筛选 `网上申购日(PUBLIC_START_DATE)` 等于当天的可转债
- 推送通道：`curl https://api.day.app/<key>/<推送内容>?group=<分组>&copy=<复制内容>`
  - 推送内容包含：转债名称、申购代码、评级、正股、发行规模
  - `copy` 字段默认放申购代码，方便在通知里一键复制

## 配置

通过环境变量配置：

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `BARK_BASE` | 是 | - | Bark 地址，形如 `https://api.day.app/你的key` |
| `BARK_GROUP` | 否 | `可转债` | Bark 推送分组 |
| `PUSH_TIME` | 否 | `09:00` | 每天推送时间 HH:MM（北京时间） |
| `NOTIFY_WHEN_EMPTY` | 否 | `false` | 无可申购时是否也推送一条提示 |
| `REQUEST_TIMEOUT` | 否 | `20` | 网络请求超时秒数 |

## Docker 部署（推荐）

1. 编辑 `docker-compose.yml`，把 `BARK_BASE` 改成你自己的 Bark 地址。
2. 启动：

```bash
docker compose up -d --build
```

3. 查看日志：

```bash
docker compose logs -f
```

容器时区已设为 `Asia/Shanghai`，每天到 `PUSH_TIME` 自动执行。

## 本地运行

```bash
pip install -r requirements.txt

# 立即执行一次（测试用）
BARK_BASE=https://api.day.app/你的key python cb_push.py --once

# 常驻，每天定时执行
BARK_BASE=https://api.day.app/你的key python cb_push.py
```
