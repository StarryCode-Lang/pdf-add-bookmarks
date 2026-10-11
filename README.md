# PDF Add Bookmarks

一个为 PDF 添加分层书签的 Skill，支持中英文文本、扫描和混合 PDF。

将本目录放入所用 Agent 的 Skill 目录；具体操作见 [SKILL.md](SKILL.md)。运行只需 `SKILL.md`、`scripts/add_bookmarks.py` 和 `requirements.txt`。

```bash
python -m pip install -r requirements.txt
python scripts/add_bookmarks.py input.pdf
```

扫描页需要 Tesseract 和相应语言包。默认输出 `input_with_bookmarks.pdf`；复杂版面先用 `--analyze` 预览、编辑目录，再用 `--toc` 导入。全部选项：

```bash
python scripts/add_bookmarks.py --help
```

标题识别仍可能漏判；工具保留原始页面，写入前验证文字和渲染一致，不添加 OCR 文本层。

开发验证（无需安装到 Agent）：

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
# 可选：小型网络文本/扫描 PDF 实测，需要联网和 Tesseract eng
python tests/network_smoke.py
```

测试使用合成占位样例及公开网络样本。测试和 CI 仅用于维护，`validation/` 中的本地结果不上传。

MIT License。
