---
name: pdf-add-bookmarks
description: 为 PDF 添加分层书签和导航目录。适用于用户要求添加 PDF 书签、大纲、目录或索引；支持文本、扫描和混合 PDF，扫描页使用 OCR。Adds hierarchical bookmarks/outline to PDF files for textbooks, exam papers, and slides. Supports text-based, scanned, and mixed PDFs with OCR.
license: MIT
---

# PDF 书签

运行环境：Python 3.10–3.13；使用已安装的 Skill 目录，不假设任何 Agent 的固定路径。安装可使用 `npx skills@1.7.2 add StarryCode-Lang/pdf-add-bookmarks --agent codex --global`；去掉 `--global` 为项目安装，替换 Agent 名称即可用于其他支持标准 Skills 的 Agent。

脚本路径相对于本 Skill 的目录解析；输入、输出使用绝对路径。处理前确认文件存在，不覆盖输入。任务是给阅读器/笔记 App 的侧栏添加可点击书签（PDF outline），不是修改或改写文件正文；OCR 渲染图像只用于识别，不写回 PDF。

## 准备

```bash
python -m pip install -r "<skill目录>/requirements.txt"
```

扫描页需要 Tesseract 及对应语言包，默认 `chi_sim+eng`。OCR 缺失、语言包缺失或识别失败默认报错，不输出不完整 PDF。只有用户明确接受部分结果时才使用 `--allow-partial`；此时 JSON 标记 `partial: true`，并列出 `warnings`。Windows 用 `winget install UB-Mannheim.TesseractOCR` 安装，并将 [chi_sim.traineddata](https://github.com/tesseract-ocr/tessdata_fast/raw/87416418657359cb625c412a48b6e1d6d41c29bd/chi_sim.traineddata) 放入 Tesseract 的 `tessdata` 目录；macOS 用 `brew install tesseract tesseract-lang`；Debian/Ubuntu 用 `sudo apt install tesseract-ocr tesseract-ocr-chi-sim`。纯英文扫描可指定 `--lang eng`。

## 执行

先分析候选目录，暂不交付最终 PDF：

```bash
python "<skill目录>/scripts/add_bookmarks.py" "输入.pdf" --analyze --json
```

分析默认写入 `输入_suggested_toc.txt`。读取 `recognition_method`、`ocr_pages` 与诊断；有印刷目录时，渲染目录页逐项核对标题、层级，并抽查正文确认页码偏移。低质量扫描不要仅凭 OCR 置信度接受标题；没有可靠目录时，按正文标题建立目录。不能辨认的文字不得凭常识补全。分析失败时区分签名/文件错误与没有识别到标题；前者停止，后者可根据原文创建目录后导入。

用户需要更细正文导航时，用 `--generate-toc` 扩展候选；该模式同时生成候选 PDF，应指定临时输出路径，审核后再用目录文件生成最终输出。扩展候选不代表完整或正确。

最终 PDF 默认输出同目录下 `输入_with_bookmarks.pdf`。已有 PDF 与建议目录默认受保护；仅在用户明确要求替换时使用 `--overwrite`。输入、输出均用绝对路径；`-o` 指定输出，`--type textbook|exam|slides|article` 限定规则，默认 `auto`；`--force-ocr` 强制 OCR，`--workers N` 控制并行数，`--dpi N` 调整渲染分辨率（默认 200）。`--json` 的 stdout 仅输出一个 JSON 对象，进度在 stderr；成功退出码 0，失败 1。

审查生成的 `输入_suggested_toc.txt`，根据原文修正标题和页码，再导入：

```bash
python "<skill目录>/scripts/add_bookmarks.py" "输入.pdf" --toc "目录.txt"
```

目录每行是标题和 **从 1 开始的 PDF 页码**，必须用 TAB、至少两个空格或连续点号分隔；单空格不再接受，避免将 `ISO 9001` 猜成页码。缩进表示层级：

```text
第1章 概述  1
  1.1 背景  2
    1.1.1 历史  3
第2章 方法  5
```

印刷页码与 PDF 页码不同时，用 `--offset N` 调整。

## 验收

检查退出码为 0 后再报告成功，并告知输出路径和书签数。读取 JSON 的 `review_required`、`quality`、`warnings`、`diagnostics`；OCR 完成不能证明目录完整或正确，需要根据原 PDF 核对标题、层级与跳转页。未审核时说明候选书签需要审核，不声称准确率；`quality=provided_toc` 只表示导入了目录，不证明标题正确；必要时用修正后的 `--toc` 重试。默认验证内容流、文字、页面尺寸、链接、批注、附件与元数据；`--verify full` 额外逐页渲染对比像素。验证失败时保留已有输出。没有识别到标题或 OCR 失败时说明原因，用目录文件重试，不编造标题。

识别依赖规则和视觉证据；低质量扫描、没有可靠目录、双栏或跨行标题可能漏判或层级错误。未找到标题时停止，不把空输出当作成功；核对原文后用人工目录导入。输出替换原有书签，设置 `UseOutlines` 请求显示侧栏，不添加扫描页的可搜索文字层。

默认优先生成经正文印证的印刷目录。用户需要更细的正文导航时，用 `--generate-toc`：保留可靠目录的核心节点，将额外正文标题作为叶节点，并扩展较小加粗标题与 OCR 候选，同时写出建议目录和书签 PDF；候选更多，需逐项审查，不保证全文小标题完整。自动 JSON 的 `outline_policy` 分别为 `printed_toc_preferred` 与 `expanded_body`。

所有自动识别结果都需审核，即使 `warnings` 为空；`quality=unverified` 不表示准确率已验证。检测到数字签名标记时停止，请用户提供未签名原件，不绕过保护。`--analyze -o` 会自动创建父目录。

支持“单元/篇 → 章 → 节”结构及分散文本块。印刷目录页码获正文印证后优先采用该目录，减少正文栏目；目录未收录的细标题可能不输出。`diagnostics` 给出具体问题与 PDF 页码：`hierarchy_conflict` 编号与父章冲突、`missing_chapter_parent` 缺少父章、`fragmented_heading` 编号与标题未合并、`suspected_running_header` 可疑重复页眉、`unconfirmed_pagination` 目录页码未获正文印证、`incomplete_printed_toc` 目录行漏读。发现这些问题时，渲染目录与相关正文页，按原文修正建议目录后用 `--toc` 导入；逐项检查标题、父子层级与跳转页，不只核对几个章标题。无法确认的内容不得编造。
