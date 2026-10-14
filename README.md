# PDF Add Bookmarks

为中英文文本、扫描和混合 PDF 添加分层书签的轻量 Skill。在 PDF 阅读器或笔记 App 的侧栏生成可点击的导航目录，点击后跳到对应页面。支持标准 Agent Skills；仅写入 outline，不修改正文、图片或页面排版。

## 安装到 Agent

需要 Node.js/npm 和 Git（推荐 Node.js 24）。使用 [Vercel Skills CLI](https://github.com/vercel-labs/skills)：

```bash
# 交互选择 Agent、全局/项目安装范围及复制/链接方式
npx skills@1.7.2 add StarryCode-Lang/pdf-add-bookmarks

# Codex：全局安装，在所有项目中使用
npx skills@1.7.2 add StarryCode-Lang/pdf-add-bookmarks --agent codex --global --yes

# Codex：安装到当前项目，先进入项目目录
npx skills@1.7.2 add StarryCode-Lang/pdf-add-bookmarks --agent codex --yes

# 同时安装到多个 Agent
npx skills@1.7.2 add StarryCode-Lang/pdf-add-bookmarks --agent codex claude-code cursor opencode --global --yes
```

固定的 Skills CLI 1.7.2 将 Codex、Cursor、OpenCode 安装到共享的 `.agents/skills`（全局为 `~/.agents/skills`），Claude Code 使用 `.claude/skills`；由安装器按 Agent 规则处理路径。

`--agent` 也支持 `gemini-cli`、`github-copilot`、`qoder`、`qwen-code` 等；由安装器管理各 Agent 的目录。使用 `--copy` 可复制文件，`--all` 可选择全部支持的 Agent。全局安装不会替代已有项目级安装。

```bash
# 查看全局安装
npx skills@1.7.2 list --global --agent codex
# 更新全局 Skill
npx skills@1.7.2 update pdf-add-bookmarks --global
# 卸载 Codex 的全局安装
npx skills@1.7.2 remove pdf-add-bookmarks --agent codex --global --yes
```

也可先 `npm install -g skills@1.7.2`，再将以上 `npx skills@1.7.2` 替换为 `skills`。仓库根目录即可被安装器发现，无需 npm 包或额外插件配置。上面的仓库安装命令跟随当前仓库，**不是固定发行版**；固定安装器版本也不会固定 Skill 版本。稳定版安装使用 Release 的固定 ZIP：

```bash
npx skills@1.7.2 add https://github.com/StarryCode-Lang/pdf-add-bookmarks/releases/download/v0.3.1/pdf-add-bookmarks.zip --agent codex --global --yes
```

也可下载 ZIP，核对同一 Release 的 `SHA256SUMS.txt` 后解压到 Agent 的 Skill 目录。更新命令可能跟随上游版本；需要复现时保留发行 ZIP 与其校验值。

安装器部署 Skill 文件；Python 依赖与系统 OCR 按 [SKILL.md](SKILL.md) 准备。需要 Python **3.10–3.13**；Windows、Ubuntu、macOS 均纳入 CI。纯文字 PDF 不需要 Tesseract，中文扫描需 `chi_sim`，英文扫描需 `eng`。

## 使用

让 Agent“给这个 PDF 添加分层书签”，或在 Skill 目录运行：

```bash
python -m pip install -r requirements.txt
python scripts/add_bookmarks.py input.pdf --json
python scripts/add_bookmarks.py --version
```

默认输出 `input_with_bookmarks.pdf`，保留输入；默认拒绝覆盖已有 PDF 或建议目录，明确需要替换时加 `--overwrite`。输出的书签替换原书签，不添加 OCR 文字层；请求阅读器打开书签侧栏（是否自动展开由阅读器设置决定）。复杂版面先审查目录：

```bash
python scripts/add_bookmarks.py input.pdf --analyze --json
python scripts/add_bookmarks.py input.pdf --toc input_suggested_toc.txt -o output.pdf
```

目录使用 **从 1 开始的 PDF 页码**；标题与页码之间用 TAB、两个以上空格或连续点号，缩进表示层级。旧版单空格格式需转换；印刷页码可用 `--offset N` 调整。

```text
第1章 概述  5
  1.1 背景  6
第2章 方法  12
```

- `--overwrite`：允许替换已有输出；即使启用，验证失败仍保留旧文件。`--analyze -o review.txt` 可指定建议目录路径。
- 自动识别统一返回 `quality: "unverified"` 和 `review_required: true`；`warnings` 为空仅表示未检测到具体风险，不表示准确率已验证。用户提供目录返回 `quality: "provided_toc"`，其正确性由用户审核。
- 检测到数字签名标记时拒绝分析和写入，避免重新保存使签名失效；不验证签名真伪，也不提供绕过保护的参数。请使用未签名原件。
- `--json`：stdout 为一个 JSON 对象，进度在 stderr；成功退出码 0，失败 1。使用 Unicode 转义兼容非 UTF-8 终端。
- OCR 缺失或失败默认停止。明确接受缺失扫描页时才指定 `--allow-partial`，结果含 `partial: true` 与 `warnings`。工作进程异常仍报错。
- 默认验证内容流、文字、页面尺寸、链接、批注、附件与元数据；`--verify full` 额外逐页比较像素。验证成功后才发布输出。
- `--type textbook|exam|slides|article` 限定规则；`--generate-toc` 扩展较小加粗标题候选，导出建议目录和书签 PDF。其他选项见 `--help`。

内容校验确认页面保持一致；标题准确性由原文审核和公开评测验证。

JSON 的 `review_required` 与 `warnings` 提示结果是否需审核，`quality` 为 `unverified` 或 `provided_toc`，不把 OCR 成功当作准确率保证。所有自动 OCR 结果要求审核；`partial` 专门表示 OCR 环境缺失导致的部分处理。

逐页检测结合图像与文本覆盖率，支持带页眉、水印及内联图像的扫描页。彩色扫描的印刷目录按列、行识别，分离引导线与页码；仅当至少三个独立正文标题支持同一偏移（支持率至少 75%），或至少十个正文页码支持同一偏移（支持率至少 90%）并有正文标题交叉确认时，才采用印刷目录。没有可靠证据时回到正文候选并提示审核，不猜页码。

书签定位到页面。彩色图文背景、图框栏目、低质量扫描和公式可能漏判或误判，应审查建议目录；无法可靠识别时按原文提供 `--toc`。

## 开发与评测

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check scripts tests
python -m ruff format --check scripts tests
python -m pytest -q
# CI 强制 REQUIRE_OCR=1，缺少 OCR 时不可跳过测试
# 全部实书与压力测试，需要网络和 chi_sim+eng
python tests/network_smoke.py
# 只复测选定样本
python tests/network_smoke.py zh-text zh-scan zh-exam zh-low
```

CI 覆盖三平台 × Python 3.10–3.13，另检查 Ruff 与 npx 项目/全局安装。原始 PDF 与输出保存在忽略的 `validation/`；完整结构化结果保存在 [tests/benchmark_results.json](tests/benchmark_results.json)，并作为独立 Release 附件发布，包含来源哈希、参考目录、实际书签、漏检、额外候选与运行环境；源 PDF SHA-256 固定，原有书签清除后再识别，原书目录或预先人工标注作为参考。书籍和输出 PDF 不提交、不放入发行包。

| 样本 | 参考范围 |
| --- | --- |
| Think Python，244 页文字版 | 原书 240 项标题、页码、层级 |
| Calculus Made Easy，315 页原始扫描版 | 印刷目录 23 章目标页 |
| 人教版数学七年级上册，162 页文字版 | 4 章与 15 个编号节 |
| 北京版数学七年级上册，158 页彩色扫描版 | 3 章与 29 个编号节 |
| 冀教版数学八年级上册，177 页独立扫描版 | 印刷目录 6 章与 28 个编号节；原有逐页编号书签不作为标题标注 |
| 2025 年新高考 I 卷数学回忆版含解析，16 页扫描版 | 试题部分 4 个大题标题 |
| 北京版教材低质量派生版，158 页 | 100 DPI 灰度、JPEG 质量 30；同一教材的压力测试 |

另增加在 v0.3.1 识别算法冻结后首次评测的 Think Java（372 页文字版）和教科版物理八上（133 页混合版）。物理教材仅预先标注 6 个章标题及页码；它不是纯扫描件。首次评测后不调整识别算法，后续版本将其视为回归样本；两个样本不构成广泛的独立准确率保证。

这些样本用于开发与回归，包含据其版面改进算法的样本，不构成盲测或商业质量保证。指标只覆盖表中的参考范围，其他视觉候选单独记录，不能将范围内 precision/recall 当作全文识别准确率。中文扫描保留漏检、误检及 OCR 拼写错误，人工审查后的目录导入也单独验证。

本地实测（环境版本以结构化报告为准，200 DPI、4 个 OCR 进程）：

| 样本 | 参考严格匹配 | 范围内 precision / recall |
| --- | --- | --- |
| 英文文字书 | 240/240 | 参考召回 100%，另有 6 项未标注候选 |
| 英文扫描书 | 23/23 章目标页 | 仅页码，未评估全文标题 |
| 中文文字教材 | 19/19 | 100.0% / 100.0% |
| 中文彩色扫描教材 | 30/32 | 88.2% / 93.8% |
| 冀教版中文扫描教材 | 29/34 | 93.5% / 85.3% |
| 中文数学试卷 | 4/4 | 100.0% / 100.0% |
| 低质量派生版 | 16/32 | 59.3% / 50.0% |
| 首次盲测：Think Java 文字书 | 205/230 | 参考召回 89.1%，额外候选见报告 |
| 首次盲测：中文物理混合教材 | 1/6 章标题 | 范围内指标见报告 |

严格匹配同时要求标题（按评测代码忽略数字编号与标点，附录字母前缀仍可能造成失配）、PDF 页码和深度正确，不代表所有未标注视觉标题都正确，也不代表所有父级名称都准确。文字教材的评测仅覆盖章和一级编号节；扫描结果不适合未经审查直接交付。Think Java 的 25 项失配集中在附录，实际候选通常有正确页码和正文标题，但缺少原书签中的附录字母前缀；这不等同于 25 项完全漏检。新增物理混合教材仅匹配 1/6 个章标题，暴露原生文本与 OCR 混合版面下的明显漏检；因此当前版本不保证陌生混合教材的自动目录完整性，应审查并使用人工 `--toc`。所有自动输出均通过全部页的内容校验；中文样本的人工参考目录导入与全页校验均单独验证，结果见报告。试卷为网络回忆版，原文件的解析部分缺失印刷页 6–7，不作为完整真题来源。


## 发布

版本由脚本中的 `VERSION` 统一管理。修改版本并推送 `main` 后，全部 CI 通过才创建尚不存在的 Release；已发布版本不会自动覆盖。发布后 CI 直接下载公开 ZIP 与评测报告，校验 SHA-256 和全部源码内容，验证四个 Agent 的项目/全局安装，并用安装后的入口完成书签写入与全页校验。发行 ZIP 仅含运行 Skill：`SKILL.md`、三个脚本、`requirements.txt` 与 `LICENSE`。评测报告单独附加，ZIP 和报告均有 SHA-256 校验值。入口、标题/层级、OCR 按职责拆分，不引入额外运行依赖。

需要完全复现安装器时，可在固定仓库版本运行 `npm ci --prefix .github/skills --ignore-scripts`，再用 `node .github/skills/node_modules/skills/dist/cli.mjs add <固定发行ZIP的URL>` 安装；普通 npx 固定入口版本，传递依赖仍按上游声明解析。

Python 依赖固定到评测使用的版本；Actions 固定到提交 SHA，OCR 语言模型固定到提交，CI 安装器用 npm lock 固定版本、传递依赖与完整性哈希。这些固定项应在更新时一起复测；系统 Tesseract 仍由平台包管理器安装，版本记录在评测中。

<!-- release-notes -->
### v0.3.1

- 所有自动识别结果均要求审核；没有具体警告不等于识别准确率已验证。
- 拒绝重写带数字签名标记的 PDF，并测试输入和已有输出保留。
- `--analyze -o` 自动创建父目录，仍默认保护已有文件。
- 发布后直接验证公开 ZIP 的校验值、源码、四 Agent 项目/全局安装和实际书签写入。
- 冻结识别算法后评测未参与开发的书籍，完整结果保留漏检与额外候选；不因盲测结果调整算法。

MIT License。
