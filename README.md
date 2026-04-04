# gh-proxy

## 简介

github release、archive 以及项目文件的加速项目，支持 clone，有 Cloudflare Workers 无服务器版本以及 Python 版本

## 演示

演示站为公共服务，如有大规模使用需求请自行部署

### 原仓库演示（使用 Worker）

[https://gh.api.99988866.xyz/](https://gh.api.99988866.xyz/)

原仓库演示站有点不堪重负

![imagea272c95887343279.png](https://img.maocdn.cn/img/2021/04/24/imagea272c95887343279.png)

当然也欢迎[捐赠](https://github.com/hunshcn/gh-proxy#捐赠)以支持原作者

### 本仓库新增演示（Python 源码）

[https://mirror.serv00.net/](https://mirror.serv00.net/)

## python 版本和 cf worker 版本差异

- python 版本支持进行文件大小限制，超过设定返回原地址 [issue #8](https://github.com/hunshcn/gh-proxy/issues/8)

- python 版本支持特定 user/repo 封禁/白名单 以及 passby [issue #41](https://github.com/hunshcn/gh-proxy/issues/41)

## 使用

直接在 copy 出来的 url 前加`https://gh.api.99988866.xyz/`即可

也可以直接访问，在 input 输入

**_大量使用请自行部署，以上域名仅为演示使用。_**

访问私有仓库可以通过

`git clone https://user:TOKEN@ghproxy.com/https://github.com/xxxx/xxxx` [#71](https://github.com/hunshcn/gh-proxy/issues/71)

以下都是合法输入（仅示例，文件不存在）：

- 分支源码：https://github.com/hunshcn/project/archive/master.zip

- release 源码：https://github.com/hunshcn/project/archive/v0.1.0.tar.gz

- release 文件：https://github.com/hunshcn/project/releases/download/v0.1.0/example.zip

- 分支文件：https://github.com/hunshcn/project/blob/master/filename

- commit 文件：https://github.com/hunshcn/project/blob/1111111111111111111111111111/filename

- gist：https://gist.githubusercontent.com/cielpy/351557e6e465c12986419ac5a4dd2568/raw/cmd.py

## cf worker 版本部署

首页：https://workers.cloudflare.com

注册，登陆，`Start building`，取一个子域名，`Create a Worker`。

复制 [index.js](https://cdn.jsdelivr.net/gh/hunshcn/gh-proxy@master/index.js) 到左侧代码框，`Save and deploy`。如果正常，右侧应显示首页。

`ASSET_URL`是静态资源的 url（实际上就是现在显示出来的那个输入框单页面）

`PREFIX`是前缀，默认（根路径情况为"/"），如果自定义路由为 example.com/gh/\*，请将 PREFIX 改为 '/gh/'，注意，少一个杠都会错！

## Python 版本部署

本项目同时支持本地直接运行和 Docker 运行。

- 本地直接运行适合开发、调试和日常测试
- Docker 适合部署和统一运行环境

如果你只是本地验证功能，不需要使用 Docker，直接按下面的“直接部署”执行即可。

### Docker 部署

当前仓库可直接构建 Docker 镜像，容器内只需要 Python 运行环境，不依赖 Nginx / uWSGI。

```bash
docker build -t gh-proxy:latest .

docker run -d --name gh-proxy \
  -p 8082:8082 \
  --restart=always \
  gh-proxy:latest
```

容器默认执行：

```bash
./scripts/run_app.sh --foreground
```

也就是 Docker 始终以前台模式运行，让容器生命周期由 Docker 管理，而不是依赖 `nohup` 或额外的进程管理工具。

如果需要修改监听端口，直接传入环境变量：

```bash
docker run -d --name gh-proxy \
  -p 8083:8083 \
  -e PORT=8083 \
  --restart=always \
  gh-proxy:latest
```

常见 Docker 启动示例：

```bash
# 1. 指定监听地址和端口
docker run -d --name gh-proxy \
  -p 9000:9000 \
  -e HOST=0.0.0.0 \
  -e PORT=9000 \
  --restart=always \
  gh-proxy:latest

# 2. 指定静态资源地址
docker run -d --name gh-proxy \
  -p 8082:8082 \
  -e ASSET_URL=https://benzbrake.github.io/gh-proxy \
  --restart=always \
  gh-proxy:latest

# 3. 配置 GitHub API 代理和超时
docker run -d --name gh-proxy \
  -p 8082:8082 \
  -e API_PROXY=http://127.0.0.1:7890 \
  -e API_PROXY_SECONDARY=http://127.0.0.1:7891 \
  -e API_PROXY_RETRIES=3 \
  -e API_PROXY_TIMEOUT=15 \
  --restart=always \
  gh-proxy:latest
```

### 直接部署

直接部署是本项目的保留用法，适合本地测试和排查问题，不要求使用 Docker。

#### Linux / macOS

项目已迁移到 [uv](https://github.com/astral-sh/uv) 依赖管理方案，安装速度提升 10-100 倍。

```bash
# 方法 1: 使用 uv（推荐）
chmod +x scripts/run_app.sh
./scripts/run_app.sh

# 方法 2: 使用 pip（兼容模式）
# 如果系统未安装 uv，脚本会自动回退到 pip
```

**安装 uv（可选）：**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Windows

**方法 1: 双击运行（推荐）**
```
双击 scripts\run_app.bat 文件
```

**方法 2: 命令行运行**
```cmd
scripts\run_app.bat
```

**安装 uv（可选，提升安装速度）：**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### 环境变量配置

可通过环境变量自定义配置：

```bash
export HOST=0.0.0.0          # 监听地址
export PORT=8082             # 监听端口
export SIZE_LIMIT=1072668082176  # 文件大小限制（字节）
export ASSET_URL=https://benzbrake.github.io/gh-proxy  # 静态资源 URL
export ENABLE_JSDELIVR=0     # 是否启用 jsDelivr 加速，1 为启用
export API_PROXY=http://127.0.0.1:7890  # GitHub API 主代理，可留空
export API_PROXY_SECONDARY=http://127.0.0.1:7891  # GitHub API 备用代理，可留空
export API_PROXY_RETRIES=3  # 每个代理默认重试 3 次
export API_PROXY_TIMEOUT=15  # GitHub API 单次请求超时（秒）
export DEBUG_MODE=1          # 调试模式，可选
```

环境变量说明：

- `HOST`
  服务监听地址，本地运行和 Docker 都建议使用 `0.0.0.0`
- `PORT`
  服务监听端口；Docker `-p` 的容器侧端口应与这里保持一致
- `SIZE_LIMIT`
  文件大小限制，单位字节；超过该值时返回源链接
- `ASSET_URL`
  首页静态资源地址；如果外部地址不可达，服务仍会启动，但首页会回退到内置占位内容
- `ENABLE_JSDELIVR`
  是否启用 jsDelivr 加速，默认 `0`
- `API_PROXY`
  GitHub API 主代理地址，可为空
- `API_PROXY_SECONDARY`
  GitHub API 备用代理地址，可为空
- `API_PROXY_RETRIES`
  每个代理的最大重试次数，默认 `3`
- `API_PROXY_TIMEOUT`
  GitHub API 单次请求超时时间，单位秒，默认 `15`
- `DEBUG_MODE`
  调试模式，设置为 `1` 时启用 Flask debug 日志；通常通过 `./scripts/run_app.sh --debug` 使用

#### 运行模式

```bash
# 后台运行（默认）
./scripts/run_app.sh

# 停止后台运行的服务
./scripts/kill.sh

# 前台运行（调试 / Docker 用）
./scripts/run_app.sh --foreground

# 调试模式
./scripts/run_app.sh --debug
```

说明：

- 本地直接运行时，`run_app.sh` 默认后台启动，使用 `./scripts/kill.sh` 停止
- Docker 运行时，统一使用 `--foreground` 前台模式
- `scripts/run_in_screen.sh` 已移除，不再使用 `screen` 管理进程

#### 健康检查

```bash
curl http://127.0.0.1:8082/health
```

健康检查始终返回 `200`，并在响应体中给出 GitHub 连通状态：

```json
{"status":"ok","github_reachable":true}
```

如果 GitHub 暂时不可达，接口仍返回 `200`，但会在响应中标记退化状态，便于 Docker 存活检查和人工排障同时使用。

例如：

```json
{"status":"ok","github_reachable":false,"github_check_error":"..."}
```

Docker 镜像内置了 `HEALTHCHECK`，默认就是请求这个接口。

GitHub API 请求会按以下顺序尝试：

1. `API_PROXY`，默认最多尝试 `API_PROXY_RETRIES` 次
2. `API_PROXY_SECONDARY`，默认最多尝试 `API_PROXY_RETRIES` 次
3. 不使用代理直连 1 次

按需求修改`app/main.py`的前几项配置

_注意:_ 可能需要在`return Response(generate(), headers=headers, status=r.status_code)`前加两行

```python3
if 'Transfer-Encoding' in headers:
    headers.pop('Transfer-Encoding')
```

### 注意

- 如果启动机器无法访问 `ASSET_URL` 指向的静态资源地址，服务仍会启动，但首页会回退到内置占位内容
- 如果需要自定义首页静态资源地址，可通过 `ASSET_URL` 环境变量覆盖
- 健康检查中的 GitHub 连通性只作为诊断信息，不会因为 GitHub 暂时不可达而让 `/health` 返回失败

python 版本默认走服务器（2021.3.27 更新）

## Cloudflare Workers 计费

到 `overview` 页面可参看使用情况。免费版每天有 10 万次免费请求，并且有每分钟 1000 次请求的限制。

如果不够用，可升级到 $5 的高级版本，每月可用 1000 万次请求（超出部分 $0.5/百万次请求）。

## Changelog

- 2023.12.02 增加对`api.github.com`的部分支持
- 2023.12.01 增加环境变量支持，指定从仓库更新黑名单（仅 Python 版本支持）
- 2020.04.10 增加对`raw.githubusercontent.com`文件的支持
- 2020.04.09 增加 Python 版本（使用 Flask）
- 2020.03.23 新增了 clone 的支持
- 2020.03.22 初始版本

## 感谢

[原作者](https://hunsh.net)

[jsproxy](https://github.com/EtherDream/jsproxy/)
