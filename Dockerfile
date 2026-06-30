FROM python:3.12-slim

# 设置时区为东八区，保证 09:00 是北京时间
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY cb_push.py .

# 默认以守护进程方式运行，每天到点推送
CMD ["python", "cb_push.py"]
