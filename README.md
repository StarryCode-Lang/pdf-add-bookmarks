# PDF Add Bookmarks

为中英文文本、扫描和混合 PDF 添加分层书签的轻量 Skill。运行只需 `SKILL.md`、`scripts/add_bookmarks.py`、`requirements.txt`；仓库中的测试文件不参与运行。

```bash
python -m pip install -r requirements.txt
python scripts/add_bookmarks.py input.pdf --json
```

将目录放入 Agent 的 Skill 目录，安装与使用见 [SKILL.md](SKILL.md)。扫描页需 Tesseract 与对应语言包，纯英文使用 `--lang eng`。默认输出 `input_with_bookmarks.pdf`，保留输入，替换输出中的原有书签，不添加 OCR 文字层。

复杂版面先审查建议目录，再导入：

```bash
python scripts/add_bookmarks.py input.pdf --analyze --json
python scripts/add_bookmarks.py input.pdf --toc input_suggested_toc.txt -o output.pdf
```

目录格式：标题与 **PDF 页码（从 1 开始）** 之间使用 TAB、两个以上空格或连续点号；缩进表示层级。**旧版单空格格式需转换**，无页码行不再默认指向第 1 页。

```text
Chapter 1 Introduction  5
  1.1 Background  6
Chapter 2 Methods  12
```

印刷页码可用 `--offset N` 统一调整。其他参数用 `--help` 查看。

- `--json`：stdout 为单个 JSON 对象，进度在 stderr；成功退出码 0，失败 1。`--analyze --json` 返回目录路径、候选标题、层级类型和页码。
- OCR 缺失或失败默认停止。只有接受缺失扫描页的结果时才指定 `--allow-partial`；结果含 `partial: true` 和 `warnings`。OCR 工作进程异常仍报错。
- 默认验证内容流、文字、页面尺寸、链接、批注、附件、元数据；`--verify full` 额外逐页比较像素。写入与验证通过后才替换输出，失败保留已有文件。
- `--type textbook|exam|slides|article` 限定规则；`--generate-toc` 扩展较小加粗标题候选，同时导出目录并生成 PDF。

识别依赖编号、字体和版面规则。复杂排版、数学公式、小标题和低质量扫描可能误判；书签指向页面，未定位到标题坐标。建议目录供审查，不代表无漏检保证。

## 验证

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
# 要求 OCR 测试不可跳过；CI 已强制设置
REQUIRE_OCR=1 python -m pytest -q
# 可选：下载并完整测试两本真实书籍，需要网络、Tesseract eng
python tests/network_smoke.py
```

Windows、Ubuntu、macOS CI 使用 Python 3.12；缺少 OCR 或语言包会失败。网络评测锁定源文件 SHA-256，下载、OCR 原文、书签清单、耗时与校验结果保存在忽略的 `validation/`，不提交书籍或生成文件。

2026-10-14 的实书评测（英文，200 DPI，4 个 OCR 进程）：

| 书籍 | 输入 | 验证范围 |
| --- | --- | --- |
| [Think Python 2e](https://greenteapress.com/thinkpython2/thinkpython2.pdf) | 244 页文字版，清除原书签后识别 | 原书 240 项书签的标题、PDF 页码和层级；忽略编号与标点差异 |
| [Calculus Made Easy](https://archive.org/download/CalculusMadeEasy/Calculus_Made_Easy_Thompson.pdf) | 315 页原始扫描版，本来没有书签或文字层 | 按原书印刷目录独立核对 23 章目标页 |

两书均通过全部页的文字、像素和内容保留校验。文字版匹配 240/240 项参考；扫描版匹配 23/23 章目标页。扫描标题仍有 OCR 拼写误差，额外候选需审查；上述结果不是中文教材或全部小标题的准确率承诺。

MIT License。
