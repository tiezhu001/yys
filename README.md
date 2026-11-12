# OAS / OASX 联合开发目录

本目录用于统一访问两个项目，现在是两个真实代码副本组成的联合开发目录，原目录保留作为迁移前回退。

- `oas/`：OAS Python 服务端代码副本
- `oasx/`：OASX Flutter 客户端源码副本
- `docs/`：开发指南、项目分析和结构文档

## 开发启动

服务端：

```powershell
cd D:\script-dev\yys-script-dev\oas
.\.venv\Scripts\python.exe server.py --host 127.0.0.1 --port 22267
```

客户端开发：

```powershell
cd D:\script-dev\yys-script-dev\oasx
flutter pub get
flutter run -d windows
```

也可以直接启动现有 OASX 发布版，并连接 `127.0.0.1:22267`。

## 注意

- `oas` 和 `oasx` 是新联合仓库中的真实目录；原始仓库仍保留在旧路径。
- OAS 的工作目录必须是服务端仓库根目录。
- OASX 的服务端启动按钮仍按整合包 `toolkit` 设计；开发时先手动启动 OAS 服务端，再从 OASX 登录页连接。
- 新根目录使用独立 Git 仓库；`.venv`、日志和构建缓存已写入 `.gitignore`。


