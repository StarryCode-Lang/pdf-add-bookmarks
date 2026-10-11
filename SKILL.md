---
name: pdf-add-bookmarks
description: 为 PDF 添加分层书签和导航目录。适用于用户要求添加 PDF 书签、大纲、目录或索引；支持文本、扫描和混合 PDF，扫描页使用 OCR。
---

# PDF 书签

脚本路径相对于本 Skill 的目录解析；输入、输出使用绝对路径。处理前确认文件存在，不覆盖输入。

## 准备

```bash
python -m pip install -r "<skill目录>/requirements.txt"
```

扫描页需要 Tesseract 及对应语言包，默认 `chi_sim+eng`。Windows 用 `winget install UB-Mannheim.TesseractOCR` 安装，并将 [chi_sim.traineddata](https://github.com/tesseract-ocr/tessdata/raw/main/chi_sim.traineddata) 放入 Tesseract 的 `tessdata` 目录；macOS 用 `brew install tesseract tesseract-lang`；Debian/Ubuntu 用 `sudo apt install tesseract-ocr tesseract-ocr-chi-sim`。纯英文扫描可指定 `--lang eng`。

## 执行

```bash
python "<skill目录>/scripts/add_bookmarks.py" "输入.pdf"
```

默认输出同目录下 `输入_with_bookmarks.pdf`。可用 `-o "输出.pdf"` 指定路径；`--type textbook|exam|slides|article` 限定标题规则，默认 `auto` 合并规则；`--force-ocr` 强制 OCR，`--workers N` 控制 OCR 并行数。

识别不确定或用户要求预览时，先生成建议目录：

```bash
python "<skill目录>/scripts/add_bookmarks.py" "输入.pdf" --analyze
```

审查生成的 `输入_suggested_toc.txt`，根据原文修正标题和页码，再导入：

```bash
python "<skill目录>/scripts/add_bookmarks.py" "输入.pdf" --toc "目录.txt"
```

目录每行是标题和 **从 1 开始的 PDF 页码**，缩进表示层级：

```text
第1章 概述 1
  1.1 背景 2
    1.1.1 历史 3
第2章 方法 5
```

印刷页码与 PDF 页码不同时，用 `--offset N` 调整。

## 验收

检查退出码为 0 后再报告成功，并告知输出路径和书签数。脚本逐页检查文字和渲染结果，失败时保留已有输出。没有识别到标题或 OCR 失败时说明原因，用目录文件重试，不编造标题。

识别依赖规则和视觉证据，复杂版面可能漏判，必要时人工审查。输出替换原有书签，不添加扫描页的可搜索文字层。
