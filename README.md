# agent-homework

Agent 方向作业 · 任务一：用 uv 管理环境与依赖，用 asyncio + httpx 并发请求多个 HTTP 接口，汇总每条结果。

## 环境要求

- Python 3.11+（版本由 `.python-version` 固定为 3.11）
- uv 0.13+

## 快速开始

```powershell
uv sync                      # 按 uv.lock 精确安装依赖并创建 .venv
Copy-Item .env.example .env  # 首次运行才需要；.env 不入库
uv run main.py               # 跑起来
```

## 运行效果

真实输出（2026-11-19，三个 B 站接口，耗时与响应体积随网络波动）：

```
2026-11-19 13:17:17,477 INFO    agent_homework | 开始：3 个地址，并发 6，超时 10.0s
[ok     ] 200     136.6ms     8250B  https://api.bilibili.com/x/web-interface/popular?ps=5
[ok     ] 200     147.1ms   153324B  https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all
[ok     ] 200     103.7ms     6930B  https://api.bilibili.com/x/web-interface/newlist?rid=1&ps=5
------------------------------------------------------------------------
完成 3/3（失败 0），墙钟 235.8ms
2026-11-19 13:17:17,713 INFO    agent_homework | 完成 3/3，墙钟 236ms
```

三条请求各自要 100～150ms，实际耗时只有 235.8ms 而不是三者相加——这就是并发的结果。

退出码：全部成功为 `0`，有失败为 `1`，参数错误为 `2`。

## 命令行参数

| 参数 | 说明 |
| --- | --- |
| `-u, --url` | 目标地址，可重复；不传则用内置的 3 个 B 站接口 |
| `-c, --concurrency` | 最大并发数，默认 6（可用 `CONCURRENCY` 覆盖） |
| `-t, --timeout` | 单请求超时秒数，默认 10（可用 `REQUEST_TIMEOUT` 覆盖） |
| `--json [PATH]` | 输出 JSON 结果：给路径则写文件，省略值则打印到 stdout |
| `--log-level` | `DEBUG` / `INFO` / `WARNING` / `ERROR`，默认 `INFO` |

```powershell
uv run main.py -u https://example.com -u https://example.org -c 2 -t 5
uv run main.py --json out.json
uv run main.py --help
```

## 目录结构

```
agent-任务一/
├── main.py                  # 入口：转调包内的 main()
├── agent_homework/
│   └── __init__.py          # 全部逻辑：Result / fetch_one / fetch_all / render / main
├── tests/test_render.py     # 纯函数单元测试（不联网）
├── pyproject.toml           # 依赖、dev 组、ruff 与 pytest 配置
├── uv.lock                  # 锁定的依赖版本，保证他人可复现
├── .python-version          # 3.11
├── .env.example             # 环境变量模板（提交入库）
├── .gitignore               # 排除 .venv / __pycache__ / .env*
└── README.md
```

## 为什么不用 src/ 布局

本项目路径是 `C:\Users\Admin（无密码）\Desktop\agent-任务一`，含中文和全角括号。用 src 布局并让 uv 以可编辑方式安装本包时，uv 会在 `.venv\Lib\site-packages\` 下生成一个 `agent_homework.pth`，内容是 UTF-8 编码的绝对路径；而 Python 3.11 的 `site` 模块在 Windows 上固定用系统 locale（GBK）读 `.pth`，于是解释器一启动就崩：

```
Fatal Python error: init_import_site: Failed to import the site module
UnicodeDecodeError: 'gbk' codec can't decode byte 0x80 in position 52: illegal multibyte sequence
```

注意 `-X utf8` 和 `PYTHONUTF8=1` 都救不了——`site` 读 `.pth` 走的是 `locale.getencoding()`，不受 UTF-8 模式影响。

解决办法是让环境里**不存在**这个 `.pth`：

1. 改成扁平布局，包 `agent_homework/` 直接放项目根，Python 运行 `main.py` 时项目根本来就在 `sys.path[0]`；
2. 在 `pyproject.toml` 里设 `[tool.uv] package = false`，uv 就不再把本项目当安装包处理（代价是 `uv run agent-homework` 这条 console script 没了，用 `uv run main.py` 代替）。

这么改之后 `uv sync` 只装第三方依赖，`.venv` 里不再有 `.pth`，无论怎么重装都不会再崩。

## 密钥与配置分离

`.env` 存本机配置，**不入库**；仓库里只提交 `.env.example` 模板。`.gitignore` 用 `.env` 与 `.env.*` 两条规则排除，再用 `!.env.example` 把模板放回来。

代码里用 `load_dotenv(override=False)` 读取：真实环境变量优先于 `.env` 文件，这样 CI 或生产环境直接注入变量时，不会被本地文件覆盖。

`.env` 里含空格的值（比如 User-Agent）**必须用双引号包住**，否则 uv 加载时会解析失败、变量直接丢失。

## 测试与静态检查

```powershell
uv run pytest -q      # 3 passed
uv run ruff check .   # All checks passed!
```

测试只覆盖纯函数（`summarize` / `render` / `Result` 不可变性），不发真实请求，因此离线也能跑。

## 踩过的坑

- **三个接口一开始全返回 412**：B 站会拦默认的 httpx User-Agent。给 `httpx.AsyncClient` 加上浏览器 UA 后恢复 200，这个 UA 现在可以通过 `.env` 里的 `HTTP_USER_AGENT` 覆盖。
- **一次 `IndentationError`**：`async with` 块内的缩进和外层不一致，Python 直接报错退出，对齐后重新跑通。
- **首次 push 被拒**：远程仓库初始化时带了 README，与本地历史无关。确认远程没有需要保留的提交后用 `git push -f` 覆盖；正常协作场景应先 `git pull --allow-unrelated-histories`，强制推送只用于清理自己新建的空仓库。
- **解释器启动即崩（`UnicodeDecodeError: 'gbk'`）**：见上面「为什么不用 src/ 布局」一节，中文路径 + 可编辑安装生成的 `.pth` 是元凶。
