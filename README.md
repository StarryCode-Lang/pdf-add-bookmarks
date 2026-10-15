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
npx skills@1.7.2 add https://github.com/StarryCode-Lang/pdf-add-bookmarks/releases/download/v0.4.2/pdf-add-bookmarks.zip --agent codex --global --yes
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
- `--type textbook|exam|slides|article` 限定规则。默认优先采用经正文印证的印刷目录；`--generate-toc` 保留其核心节点并添加正文叶节点，同时扩大较小加粗标题候选，导出建议目录和书签 PDF。扩展模式会产生更多候选，需要审核；其他选项见 `--help`。

内容校验确认页面保持一致；标题准确性由原文审核和公开评测验证。

自动结果的 `outline_policy` 区分 `printed_toc_preferred`（默认）与 `expanded_body`（`--generate-toc`）。JSON 的 `review_required`、`warnings` 与 `diagnostics` 提示审核要求及具体问题；所有自动结果仍为 `quality=unverified`，不把 OCR 成功当作准确率保证。诊断包含编号层级冲突、缺少父章、标题碎片、重复结构标题、未确认页码及目录漏读，并给出 PDF 页码。`partial` 仅表示 OCR 环境缺失导致的部分处理。

按语义构建“单元/篇 → 章 → 节”，缺少中间层时直接连接实际父节点。原生标题按位置合并分散的编号、标题与不同字号；原生目录支持同一行左右页码、点线引导符与前置页码；确认印刷目录后抑制额外视觉栏目，扫描目录配对标题行和对齐的页码列，并单独处理彩色文字及页码。只有正文标题或多个正文页码支持一致偏移时才采用印刷目录；不能确认时提示审核，不猜目标页。复杂彩色扫描仍可能漏字、错字，必要时核对原文后用 `--toc` 导入。

## 开发与评测

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check scripts tests
python -m ruff format --check scripts tests
python -m pytest -q
# pytest 仅收集 tests/，临时工具和依赖库的测试不计入项目测试数
# CI 强制 REQUIRE_OCR=1，缺少 OCR 时不可跳过测试
# 全部实书与压力测试，需要网络和 chi_sim+eng
python tests/network_smoke.py
# 只复测选定样本
python tests/network_smoke.py zh-text zh-scan zh-exam zh-low
```

CI 覆盖三平台 × Python 3.10–3.13，另检查 Ruff 与 npx 项目/全局安装。原始 PDF 与输出保存在忽略的 `validation/`；完整结构化结果保存在 [tests/benchmark_results.json](tests/benchmark_results.json)，并作为独立 Release 附件发布，包含来源哈希、参考目录、实际书签、漏检、额外候选与运行环境；源 PDF SHA-256 固定，原有书签清除后再识别，原书目录或预先人工标注作为参考。书籍和输出 PDF 不提交、不放入发行包。

<!-- benchmark-summary-start -->
本版共 18 个样本、2,767 页；结果包含失败样本。严格匹配与内容保真分开核验，参考范围见 JSON。

| 样本 | 页数 | 严格匹配 / 参考项 | 输出书签 |
| --- | --- | --- | --- |
| Think Python（回归） | 244 | 240/240 | 246 |
| Think Java（回归） | 372 | 230/230 | 240 |
| 人教版数学七上（回归） | 162 | 19/19 | 70 |
| 教科版物理八上（章级回归） | 133 | 6/6 | 147 |
| 苏科版物理八上（章级回归） | 134 | 5/5 | 105 |
| 济南版生物七上（回归） | 140 | 32/32 | 32 |
| 沪教版化学九上（回归） | 154 | 35/35 | 41 |
| 粤教粤人版地理七上（回归） | 109 | 22/22 | 23 |
| 北京版化学九下（现为回归） | 122 | 22/22 | 22 |
| 人教版地理八上（现为回归） | 120 | 19/19 | 20 |
| BERT 双栏论文（独立测试） | 16 | 0/29 | 0 |
| 北京版数学七上（扫描回归） | 158 | 30/32 | 34 |
| 冀教版数学八上（扫描回归） | 177 | 29/34 | 32 |
| 数学试卷（回归） | 16 | 4/4 | 5 |
| 湘教版地理七上（扫描回归） | 121 | 20/24 | 24 |
| 北京版低质量派生扫描（压力测试） | 158 | 17/32 | 27 |
| Calculus Made Easy（扫描回归） | 315 | 23/23 章目标页 | 29 |
| Flatland 旧扫描书（独立测试） | 116 | 1/24 | 69 |

低质量派生扫描从 16/32 改善到 17/32，仍有明显 OCR 错字和漏检。其余既有样本的严格匹配数保持；完整印刷目录样本的输出数未增加。生物 32/32、32 项，化学 35/35、41 项，粤教地理 22/22、23 项；对应 precision 为 100%、85.4%、95.7%。部分参考只覆盖章或编号节，不能据此声称完整输出精确率。

两份新独立测试暴露了适用边界：Flatland 的印刷目录没有可用页码，保留原有隐形 OCR 层并对 116 页强制 OCR，默认仅匹配 1/24；BERT 无印刷目录，默认未找到标题，未生成 PDF。扩展模式 BERT 为 12/29、24 项，仍有跨行、阅读顺序和附录父节点错误。这些失败未用于本版定向调优，初次候选与被拒绝的开发结果一并保留；不把它们算作识别成功。

`--generate-toc` 面向更细正文导航：化学由默认 41 项扩展为 90 项，35 个核心参考节点及其父子路径保留，但额外候选仍需审核，不能拿印刷目录 precision 评价其全部导航价值。低质量扫描的 32 项人工审核目录已通过独立六文件 Skill 的 CLI 导入及全页校验；这证明回退路径可用，不代表自动 OCR 达到 32/32。

受控 Linux 新进程交替运行两版各两次，固定依赖、语言模型与 200 DPI；以下是均值，不宣称普遍提速：

| 测量范围 | v0.4.1 → v0.4.2 耗时 | 父进程峰值 MiB | 最大子进程峰值 MiB |
| --- | --- | --- | --- |
| 244 页文字书提取与识别 | 1.86 → 1.72 秒 | 52.5 → 52.5 | 0.0 → 0.0 |
| 两页低质量目录 OCR | 49.94 → 53.95 秒 | 115.7 → 115.8 | 115.7 → 115.8 |

额外目录 OCR 备选有处理成本；各进程峰值不能相加当作同时总内存。整书最终输出均重新生成并逐页校验；提取指纹未变化的原始 OCR 缓存可以复用，缓存内的提取耗时不作为提速证据。原始测量、实现哈希与比较范围见 JSON 的 `maintenance_comparison`。
<!-- benchmark-summary-end -->

严格匹配要求归一化后的标题、PDF 页码与深度一致。完整印刷目录样本评分全部输出；目录之外也可能有合法正文子标题，不能一概视为无效。其他样本只评价明确标注的章、节或目标页范围，不代表全文准确率。每份实际生成的自动 PDF 和人工目录回退 PDF 都逐页验证内容一致；识别正确性与页面保真分别核验。

已参与调优的教材均标记为回归样本；v0.3.3 与 v0.4.0 的首次失败数据、实际目录和实现哈希保存在报告 `prior_independent_evaluations`。苏科版早期首次 0/5 保存在 `independent_first_pass`。本轮独立样本先标注正文目录，再运行首个候选；首轮失败和候选哈希保留。后续仅针对既有回归样本修正，未针对新样本失败调整本版规则。历史分数和各样本范围详见 JSON，不以回归成绩代替独立泛化证据。

`tests/fixtures/signed_pdf.b64` 是 6,455 字节真实 RSA/CMS 签名 PDF 的 Base64，不是仅填充签名标记的文件。签署使用专门的自签名测试证书；独立验证确认签名完整、有效，CI 用 OpenSSL CMS 每次校验签名和内容摘要，并测试拒绝处理后原件逐字节不变。不宣称该证书受公共 CA 信任。创建样本的私钥、签署工具和输入 PDF 均不提交，不加入运行依赖。


## 发布

版本由脚本中的 `VERSION` 统一管理。修改版本并推送 `main` 后，全部 CI 通过才创建尚不存在的 Release；已发布版本不会自动覆盖。发布后 CI 直接下载公开 ZIP 与评测报告，校验 SHA-256 和全部源码内容，验证四个 Agent 的项目/全局安装，并用安装后的入口完成书签写入与全页校验。发行 ZIP 仅含运行 Skill：`SKILL.md`、三个脚本、`requirements.txt` 与 `LICENSE`。评测报告单独附加，ZIP 和报告均有 SHA-256 校验值。入口、标题/层级、OCR 按职责拆分，不引入额外运行依赖。

需要完全复现安装器时，可在固定仓库版本运行 `npm ci --prefix .github/skills --ignore-scripts`，再用 `node .github/skills/node_modules/skills/dist/cli.mjs add <固定发行ZIP的URL>` 安装；普通 npx 固定入口版本，传递依赖仍按上游声明解析。

Python 依赖固定到评测使用的版本；Actions 固定到提交 SHA，OCR 语言模型固定到提交，CI 安装器用 npm lock 固定版本、传递依赖与完整性哈希。这些固定项应在更新时一起复测；Windows CI 直接安装官方发布的固定 Tesseract 5.5.0 安装包并校验 SHA-256，避免最新 Chocolatey 包下载故障；其他平台由系统包管理器安装。评测环境版本单独记录。

<!-- release-notes -->
### v0.4.2

- 保留低置信数字目录的多视图 OCR 备选，按目录行隔离；只采用目标正文精确印证的备选，不按词表猜字。
- 低置信目录行补充一次原始行分割识别，作为备选而非直接替换主结果；统一两个目录读取器的文本/置信度提取，修复小字号 OCR 的空中位数异常。
- 修复 `--generate-toc` 的扩展候选被印刷目录策略过滤的问题；保留可靠目录父节点，额外正文标题作为叶节点。JSON 添加 `outline_policy`，CLI 参数不变。
- 重新验证真实 PDF 并保留被拒绝的开发候选与独立测试失败证据。无输出明确记录识别失败，不声称通过内容校验；人工目录回退仍逐页验证。
- 运行包仍为六个文件，无新增依赖；复杂扫描、无可靠目录与双栏排版仍需人工审核。

MIT License。
