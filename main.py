"""项目入口：`uv run main.py` 启动并发抓取。

真正的逻辑在 agent_homework/__init__.py，这里只做转发。
"""

from agent_homework import main

if __name__ == "__main__":
    raise SystemExit(main())
